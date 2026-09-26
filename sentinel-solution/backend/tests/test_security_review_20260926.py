"""Regression coverage for the five fixes from the 2026-09-26 security review.

Each finding was first reproduced against the unfixed route code (a
department-scoped caller crossing a boundary it should not); these tests
lock in the refusal:

1. /live/{id}/seg fetched any URL on the shared CDN host, so a viewer
   scoped to cam01 could pull another department's cam02 through it.
2. Cross-department vehicle history / attribute search left no explicit
   audit trace, and an unfiltered attribute search dumped recent plates.
3. A scoped investigator could dismiss another department's alert.
4. Minting a viewer/investigator key without a department produced an
   unrestricted key; viewers could fetch evidence crops.
5. (.gitignore for sentinel.db-wal/-shm is covered by
   test_gitignore_covers_sqlite_sidecar_files below.)
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api import routes_alerts, routes_stream
from app.api.auth import Principal
from app.api.routes_auth import ApiKeyCreate, create_api_key
from app.api.routes_vehicle import search_by_attributes, vehicle_history
from app.db.models import (
    ALERT_STATUS_NEW,
    Alert,
    ApiKeyEntry,
    AuditLog,
    CameraRegistry,
    VehicleEvent,
    VehicleIdentity,
)

HEALTH_VIEWER = Principal("hv", "viewer", "Health")
HEALTH_INVESTIGATOR = Principal("hi", "investigator", "Health")
POLICE_INVESTIGATOR = Principal("pi", "investigator", "Police")
ADMIN = Principal("admin1", "admin", None)


def _seed(session, tmp_path=None):
    session.add_all([
        CameraRegistry(id="cam01", department="Health"),
        CameraRegistry(id="cam02", department="Police"),
    ])
    identity = VehicleIdentity(plate="GJ01AB1234")
    session.add(identity)
    session.commit()
    crop_path = None
    if tmp_path is not None:
        crop_path = str(tmp_path / "crop.jpg")
        pathlib.Path(crop_path).write_bytes(b"jpeg")
    event = VehicleEvent(
        identity_id=identity.id, camera_id="cam02", pts_ms=0.0, plate="GJ01AB1234",
        vehicle_type="car", link_method="plate_continuation", crop_path=crop_path,
    )
    session.add(event)
    session.commit()
    alert = Alert(plate="GJ01AB1234", camera_id="cam02", reason="stolen",
                  vehicle_event_id=event.id, status=ALERT_STATUS_NEW)
    session.add(alert)
    session.commit()
    return event, alert


# ------------------------------------------------ 1. HLS segment proxy scope

def _cameras():
    return {
        cid: MagicMock(hls_url=f"https://cctv.example/{cid}/index.m3u8")
        for cid in ("cam01", "cam02")
    }


@pytest.mark.parametrize("u", [
    "https://cctv.example/cam02/index.m3u8",           # sibling camera, same host
    "https://cctv.example/cam01/../cam02/index.m3u8",  # dot-segment climb
    "https://cctv.example/cam01/%2e%2e/cam02/seg.ts",  # encoded climb
    "https://cctv.example/cam01x/seg.ts",              # prefix without the slash
    "http://cctv.example/cam01/seg.ts",                # scheme downgrade
    "https://cctv.example/admin",                      # any other CDN path
    "https://evil.example/cam01/seg.ts",               # other host
])
def test_segment_proxy_refuses_urls_outside_the_camera_directory(session, u):
    _seed(session)
    with patch.object(routes_stream, "catalogue") as catalogue:
        catalogue.get.side_effect = _cameras().get
        with pytest.raises(HTTPException) as exc_info:
            routes_stream.hls_segment("cam01", u=u, db=session, principal=HEALTH_VIEWER)
        assert exc_info.value.status_code == 400
        catalogue.authenticated_get.assert_not_called()


def test_segment_proxy_still_serves_the_cameras_own_segments(session):
    _seed(session)
    with patch.object(routes_stream, "catalogue") as catalogue:
        catalogue.get.side_effect = _cameras().get
        catalogue.authenticated_get.return_value = MagicMock(content=b"ts", headers={"Content-Type": "video/mp2t"})
        response = routes_stream.hls_segment(
            "cam01", u="https://cctv.example/cam01/sub/seg1.ts?token=abc", db=session, principal=HEALTH_VIEWER,
        )
    assert response.status_code == 200
    catalogue.authenticated_get.assert_called_once_with("https://cctv.example/cam01/sub/seg1.ts?token=abc")


# --------------------------------- 2. cross-department search audit + no dump

def test_cross_department_history_writes_an_explicit_audit_row(session):
    _seed(session)
    result = vehicle_history("GJ01AB1234", purpose="stolen_vehicle_check", case_id="C-9",
                             db=session, principal=HEALTH_INVESTIGATOR)
    assert [s["camera_id"] for s in result["sightings"]] == ["cam02"]
    cross = session.query(AuditLog).filter(AuditLog.query.like("cross-department access:%")).all()
    assert len(cross) == 1
    assert "Police" in cross[0].query and cross[0].purpose == "stolen_vehicle_check"
    assert cross[0].case_id == "C-9"


def test_own_department_history_writes_no_cross_department_row(session):
    _seed(session)
    vehicle_history("GJ01AB1234", purpose="stolen_vehicle_check", db=session, principal=POLICE_INVESTIGATOR)
    assert session.query(AuditLog).filter(AuditLog.query.like("cross-department access:%")).count() == 0


def test_cross_department_attribute_search_is_audited(session):
    _seed(session)
    search_by_attributes(purpose="stolen_vehicle_check", vehicle_type="car", color=None,
                         partial_plate=None, case_id=None, db=session, principal=HEALTH_INVESTIGATOR)
    assert session.query(AuditLog).filter(AuditLog.query.like("cross-department access:%")).count() == 1


@pytest.mark.parametrize("partial_plate", [None, "", "%", "--"])
def test_attribute_search_without_a_real_filter_is_refused(session, partial_plate):
    _seed(session)
    with pytest.raises(HTTPException) as exc_info:
        search_by_attributes(purpose="stolen_vehicle_check", vehicle_type=None, color=None,
                             partial_plate=partial_plate, case_id=None, db=session, principal=ADMIN)
    assert exc_info.value.status_code == 400
    assert session.query(AuditLog).count() == 0


def test_attribute_search_refuses_a_too_short_partial_plate(session):
    _seed(session)
    with pytest.raises(HTTPException) as exc_info:
        search_by_attributes(purpose="stolen_vehicle_check", vehicle_type="car", color=None,
                             partial_plate="1", case_id=None, db=session, principal=ADMIN)
    assert exc_info.value.status_code == 400


# ------------------------------------------- 3. cross-department alert changes

@pytest.mark.parametrize("action", ["status", "ack"])
def test_investigator_cannot_change_another_departments_alert(session, action):
    _, alert = _seed(session)
    with pytest.raises(HTTPException) as exc_info:
        if action == "status":
            routes_alerts.update_alert_status(alert.id, routes_alerts.StatusUpdate(status="dismissed"),
                                              db=session, principal=HEALTH_INVESTIGATOR)
        else:
            routes_alerts.acknowledge_alert(alert.id, db=session, principal=HEALTH_INVESTIGATOR)
    assert exc_info.value.status_code == 404
    session.refresh(alert)
    assert alert.status == ALERT_STATUS_NEW


def test_owning_department_and_admin_can_still_act_on_the_alert(session):
    _, alert = _seed(session)
    acked = routes_alerts.acknowledge_alert(alert.id, db=session, principal=POLICE_INVESTIGATOR)
    assert acked["status"] == "acknowledged" and acked["status_updated_by"] == "pi"
    resolved = routes_alerts.update_alert_status(alert.id, routes_alerts.StatusUpdate(status="resolved"),
                                                 db=session, principal=ADMIN)
    assert resolved["status"] == "resolved"


# ------------------------------------- 4. key minting default + viewer crops

@pytest.mark.parametrize("role", ["viewer", "investigator"])
@pytest.mark.parametrize("department", [None, "", "   "])
def test_non_admin_key_requires_a_department(session, role, department):
    with pytest.raises(HTTPException) as exc_info:
        create_api_key(ApiKeyCreate(user_id="u1", role=role, department=department), session, ADMIN)
    assert exc_info.value.status_code == 400
    assert session.query(ApiKeyEntry).count() == 0


def test_admin_key_may_still_be_unscoped_and_department_is_trimmed(session):
    create_api_key(ApiKeyCreate(user_id="a2", role="admin"), session, ADMIN)
    create_api_key(ApiKeyCreate(user_id="v1", role="viewer", department="  Police "), session, ADMIN)
    stored = {e.user_id: e.department for e in session.query(ApiKeyEntry).all()}
    assert stored == {"a2": None, "v1": "Police"}


@pytest.fixture()
def http_client(tmp_path):
    """Real router + real X-Sentinel-API-Key auth: the role gate lives in
    the route's Depends(), which direct function calls bypass."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.api import routes_vehicle
    from app.api.deps import get_db
    from app.db.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    event, _ = _seed(db, tmp_path)
    for raw, role, dept in (("view-unscoped", "viewer", None), ("view-police", "viewer", "Police"),
                            ("inv-health", "investigator", "Health")):
        db.add(ApiKeyEntry(key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                           user_id=raw, role=role, department=dept))
    db.commit()
    app = FastAPI()
    app.include_router(routes_vehicle.router)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db, event
    db.close()
    engine.dispose()


@pytest.mark.parametrize("key", ["view-unscoped", "view-police"])
def test_viewer_keys_cannot_fetch_evidence_crops(http_client, key):
    client, db, event = http_client
    response = client.get(f"/vehicle/event/{event.id}/crop", headers={"X-Sentinel-API-Key": key})
    assert response.status_code == 403


def test_cross_department_crop_over_http_needs_purpose_then_is_audited(http_client):
    client, db, event = http_client
    headers = {"X-Sentinel-API-Key": "inv-health"}
    refused = client.get(f"/vehicle/event/{event.id}/crop", headers=headers)
    assert refused.status_code == 400
    allowed = client.get(f"/vehicle/event/{event.id}/crop",
                         params={"purpose": "stolen_vehicle_check", "case_id": "C-9"}, headers=headers)
    assert allowed.status_code == 200
    rows = db.query(AuditLog).filter(AuditLog.user_id == "inv-health").all()
    assert len(rows) == 1 and rows[0].purpose == "stolen_vehicle_check"


# ------------------------------------------------ 5. SQLite sidecar files

@pytest.mark.parametrize("name", ["sentinel.db", "sentinel.db-wal", "sentinel.db-shm", "sentinel.db-journal"])
def test_gitignore_covers_sqlite_sidecar_files(name):
    backend_dir = pathlib.Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(backend_dir / name)],
        cwd=backend_dir, capture_output=True,
    )
    if result.returncode == 128:
        pytest.skip("not inside a git checkout")
    assert result.returncode == 0, f"{name} is not ignored by .gitignore"
