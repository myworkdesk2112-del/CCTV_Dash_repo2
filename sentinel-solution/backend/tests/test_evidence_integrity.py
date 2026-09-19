"""Coverage for write-time evidence integrity and the §63-oriented export
(analytics/evidence_integrity.py, api/routes_evidence.py).

The behaviour these tests exist to pin down, in priority order:

1. A hash recorded at write time must actually detect a later change to
   the file. That is the whole point of storing it — a check that only
   ever returns VERIFIED would be decoration. `test_altered_file_is_
   reported_as_hash_mismatch` is the load-bearing test here.
2. A row with no recorded hash must report NO_HASH_RECORDED, never
   VERIFIED and never a tamper alarm. ~12,280 rows in the real
   sentinel.db predate this feature; treating them as either "fine" or
   "tampered" would both be lies.
3. Only CONFIRMED may be exported. PROBABLE is refused too — deliberate,
   per evidence_class.EXPORTABLE_CLASSES — while *verification* stays
   open to every class, because checking whether an image was altered is
   not an evidentiary claim.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi import HTTPException

from app.analytics import evidence_class as evclass
from app.analytics import evidence_integrity as integrity
from app.api.auth import Principal
from app.api.routes_evidence import (
    _render_certificate_pdf,
    evidence_certificate_pdf,
    evidence_package,
    verify_event_evidence,
)
from app.db.models import AuditLog, CameraRegistry, VehicleEvent, VehicleIdentity

_PURPOSE = "stolen_vehicle_investigation"


# ------------------------------------------- hash-at-write, in the pipeline

def test_pipeline_hashes_the_crop_it_just_wrote(monkeypatch, tmp_path):
    """The claim this whole feature rests on: the hash is taken at write
    time by the real pipeline, not bolted on at export.

    Drives AnalyticsPipeline._finalize_tracks with a genuine crop array
    and asserts the stored hash matches a hash computed independently
    from the file on disk. Uses the isolated on-disk engine technique
    from test_pipeline_speed_calibration.py, because pipeline.py resolves
    SessionLocal itself rather than taking a session.
    """
    import numpy as np
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config
    from app.analytics import pipeline as pipeline_module
    from app.analytics.pipeline import AnalyticsPipeline
    from app.analytics.tracker import Track
    from app.db.models import Base

    crops = tmp_path / "crops"
    crops.mkdir()
    monkeypatch.setattr(config, "CROPS_DIR", str(crops))

    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(pipeline_module, "SessionLocal", test_session_local)

    pipeline = AnalyticsPipeline(detector_factory=lambda: None, plate_reader=None)
    track = Track(
        track_id=1,
        bbox=(0.0, 0.0, 20.0, 20.0),
        last_pts_ms=1000.0,
        first_pts_ms=0.0,
        vehicle_type="car",
        # A real, non-uniform image so the JPEG encodes to stable bytes
        # rather than a degenerate all-zero buffer.
        best_crop=np.tile(np.arange(20, dtype=np.uint8), (20, 3)).reshape(20, 20, 3),
    )

    pipeline._finalize_tracks("cam06", [track])

    db = test_session_local()
    event = db.query(VehicleEvent).filter_by(camera_id="cam06").one()
    assert event.crop_path, "pipeline did not save a crop — test setup is wrong"
    assert event.crop_sha256, "crop was written but not hashed at write time"
    assert event.crop_hashed_at is not None
    assert event.production_stamp and "detector=" in event.production_stamp

    independent = integrity.sha256_file(str(crops / event.crop_path))
    assert event.crop_sha256 == independent
    assert integrity.verify_crop(event.crop_path, event.crop_sha256)["status"] == integrity.VERIFIED
    db.close()


@pytest.fixture()
def crops_dir(tmp_path, monkeypatch):
    """Point both the module under test and the route at a temp crops dir.

    `config` is imported as a module by evidence_integrity, so patching
    the attribute on the shared config module is enough for both.
    """
    from app import config

    monkeypatch.setattr(config, "CROPS_DIR", str(tmp_path))
    return tmp_path


def _seed(session, crops_dir, *, plate="GJ01RP6128", link_method="plate_continuation",
          department="Police", write_crop=True, record_hash=True):
    camera = CameraRegistry(id="cam06", department=department, location_name="Test Road Junction")
    identity = VehicleIdentity(plate=plate)
    session.add_all([camera, identity])
    session.commit()

    crop_name = "1.jpg"
    if write_crop:
        (crops_dir / crop_name).write_bytes(b"original-evidence-bytes")

    event = VehicleEvent(
        identity_id=identity.id,
        camera_id=camera.id,
        pts_ms=1234.0,
        plate=plate,
        plate_confidence=0.81,
        link_method=link_method,
        crop_path=crop_name if write_crop else None,
        observed_at=dt.datetime(2026, 9, 19, 10, 0, 0),
    )
    if write_crop and record_hash:
        event.crop_sha256 = integrity.sha256_file(str(crops_dir / crop_name))
        event.crop_hashed_at = dt.datetime(2026, 9, 19, 10, 0, 1)
        event.production_stamp = integrity.production_stamp()
    session.add(event)
    session.commit()
    return event


# --------------------------------------------------------------- integrity

def test_unmodified_file_verifies(session, crops_dir):
    event = _seed(session, crops_dir)

    result = integrity.verify_crop(event.crop_path, event.crop_sha256)

    assert result["status"] == integrity.VERIFIED
    assert result["recorded_sha256"] == result["current_sha256"]


def test_altered_file_is_reported_as_hash_mismatch(session, crops_dir):
    """The core guarantee: a post-write edit must be detected, and both
    hashes surfaced so a reviewer sees what changed, not just that it
    did."""
    event = _seed(session, crops_dir)
    (crops_dir / event.crop_path).write_bytes(b"tampered-evidence-bytes")

    result = integrity.verify_crop(event.crop_path, event.crop_sha256)

    assert result["status"] == integrity.HASH_MISMATCH
    assert result["recorded_sha256"] != result["current_sha256"]
    assert result["current_sha256"] is not None


def test_missing_file_with_recorded_hash_is_file_missing(session, crops_dir):
    event = _seed(session, crops_dir)
    (crops_dir / event.crop_path).unlink()

    result = integrity.verify_crop(event.crop_path, event.crop_sha256)

    assert result["status"] == integrity.FILE_MISSING
    assert result["recorded_sha256"] is not None


def test_legacy_row_without_hash_is_not_treated_as_verified_or_tampered(session, crops_dir):
    event = _seed(session, crops_dir, record_hash=False)

    result = integrity.verify_crop(event.crop_path, event.crop_sha256)

    assert result["status"] == integrity.NO_HASH_RECORDED
    assert result["status"] not in (integrity.VERIFIED, integrity.HASH_MISMATCH)


def test_production_stamp_records_real_vs_stub_component_names():
    """Config alone can't show which implementation ran, so the stamp
    records concrete class names — that distinction is the reason this
    field exists."""
    class YoloPlateDetector:  # stand-in with the real class's name
        pass

    class StubPlateDetector:
        pass

    real = integrity.production_stamp(plate_detector=YoloPlateDetector())
    stub = integrity.production_stamp(plate_detector=StubPlateDetector())

    assert "plate_detector=YoloPlateDetector" in real
    assert "plate_detector=StubPlateDetector" in stub
    assert real != stub


def test_production_stamp_roundtrips_through_parse():
    parsed = integrity.parse_production_stamp(integrity.production_stamp())

    assert parsed["schema"] == integrity.PACKAGE_SCHEMA_VERSION
    assert "plate_min_conf" in parsed


def test_parse_production_stamp_tolerates_empty_and_malformed():
    assert integrity.parse_production_stamp(None) == {}
    assert integrity.parse_production_stamp("") == {}
    assert integrity.parse_production_stamp("garbage")["_unparsed"] == ["garbage"]


# ------------------------------------------------------------ export gating

def test_lead_only_export_is_refused_but_verification_is_allowed(session, crops_dir):
    """Viewing/verifying a lead is legitimate; exporting it as evidence is
    not. Both halves asserted together so a future change can't quietly
    swap which one is gated."""
    event = _seed(session, crops_dir, plate=None, link_method="appearance_match")
    assert evclass.classify(event.plate, event.link_method) == evclass.LEAD_ONLY
    investigator = Principal("i1", "investigator", "Police")

    with pytest.raises(HTTPException) as excinfo:
        evidence_package(event.id, purpose=_PURPOSE, case_id=None, db=session, principal=investigator)
    assert excinfo.value.status_code == 409
    assert excinfo.value.detail["evidence_class"] == evclass.LEAD_ONLY

    verified = verify_event_evidence(event.id, db=session, principal=investigator)
    assert verified["status"] == integrity.VERIFIED


def test_probable_export_is_also_refused(session, crops_dir):
    """PROBABLE is a strong lead but the sighting never read the plate
    itself — deliberately non-exportable (evidence_class.py)."""
    event = _seed(session, crops_dir, plate=None, link_method="plate_upgrade")
    assert evclass.classify(event.plate, event.link_method) == evclass.PROBABLE

    with pytest.raises(HTTPException) as excinfo:
        evidence_package(
            event.id, purpose=_PURPOSE, case_id="FIR/2026/1",
            db=session, principal=Principal("i1", "investigator", "Police"),
        )

    assert excinfo.value.status_code == 409


def test_confirmed_export_returns_package_with_provenance(session, crops_dir):
    event = _seed(session, crops_dir)

    pkg = evidence_package(
        event.id, purpose=_PURPOSE, case_id="FIR/2026/1",
        db=session, principal=Principal("i1", "investigator", "Police"),
    )

    assert pkg["sighting"]["evidence_class"] == evclass.CONFIRMED
    assert pkg["sighting"]["plate"] == "GJ01RP6128"
    assert pkg["image"]["integrity"]["status"] == integrity.VERIFIED
    assert pkg["device"]["camera_id"] == "cam06"
    assert pkg["device"]["owning_department"] == "Police"
    # Guards the getattr-default bug this test originally caught: a
    # mistyped column name would make this field silently None.
    assert pkg["device"]["location_name"] == "Test Road Junction"
    assert pkg["production_method"]["schema"] == integrity.PACKAGE_SCHEMA_VERSION
    assert pkg["case_id"] == "FIR/2026/1"
    # Conservative wording is part of the contract, not decoration.
    assert "NOT A CERTIFICATE OF ADMISSIBILITY" in pkg["legal_review_notice"]
    assert "part_a" in pkg["declarations"] and "part_b" in pkg["declarations"]


def test_export_of_tampered_image_still_reports_the_mismatch(session, crops_dir):
    """An export must not paper over a failed integrity check — the
    package carries the mismatch rather than refusing to say."""
    event = _seed(session, crops_dir)
    (crops_dir / event.crop_path).write_bytes(b"tampered")

    pkg = evidence_package(
        event.id, purpose=_PURPOSE, case_id=None,
        db=session, principal=Principal("i1", "investigator", "Police"),
    )

    assert pkg["image"]["integrity"]["status"] == integrity.HASH_MISMATCH


def test_export_is_audit_logged_before_the_artefact_is_returned(session, crops_dir):
    event = _seed(session, crops_dir)

    evidence_package(
        event.id, purpose=_PURPOSE, case_id="FIR/2026/7",
        db=session, principal=Principal("i9", "investigator", "Police"),
    )

    rows = session.query(AuditLog).all()
    assert len(rows) == 1
    assert rows[0].user_id == "i9"
    assert rows[0].purpose == _PURPOSE
    assert rows[0].case_id == "FIR/2026/7"
    assert f"event={event.id}" in rows[0].query


def test_package_includes_its_own_export_in_the_audit_trail(session, crops_dir):
    event = _seed(session, crops_dir)
    principal = Principal("i1", "investigator", "Police")

    evidence_package(event.id, purpose=_PURPOSE, case_id=None, db=session, principal=principal)
    second = evidence_package(event.id, purpose=_PURPOSE, case_id=None, db=session, principal=principal)

    trail = second["access_and_export_audit_trail"]
    assert len(trail) >= 1
    assert any("evidence-export" in entry["action"] for entry in trail)


# ------------------------------------------------------------------- RBAC

def test_cross_department_scoped_investigator_gets_404_not_403(session, crops_dir):
    """404 so a scoped caller can't enumerate other departments' events by
    id — same reasoning as routes_vehicle.py's crop endpoint."""
    event = _seed(session, crops_dir, department="Police")

    with pytest.raises(HTTPException) as excinfo:
        evidence_package(
            event.id, purpose=_PURPOSE, case_id=None,
            db=session, principal=Principal("i2", "investigator", "Health"),
        )

    assert excinfo.value.status_code == 404


def test_unscoped_principal_may_export(session, crops_dir):
    """department=None means "no department filter", not "no access" —
    department_scope's documented contract."""
    event = _seed(session, crops_dir, department="Police")

    pkg = evidence_package(
        event.id, purpose=_PURPOSE, case_id=None,
        db=session, principal=Principal("admin", "admin", None),
    )

    assert pkg["sighting"]["event_id"] == event.id


def test_unknown_event_is_404(session, crops_dir):
    with pytest.raises(HTTPException) as excinfo:
        verify_event_evidence(999999, db=session, principal=Principal("v1", "viewer", None))

    assert excinfo.value.status_code == 404


# -------------------------------------------------------------- HTTP layer

def _http_app(session):
    """Real router + real auth dependency over a TestClient.

    Direct function calls (everything above) bypass FastAPI's `Query`
    validation and `require_role`, so the purpose floor and the role gate
    are only actually exercised here. StaticPool per
    test_session_auth.py: TestClient runs the app in a worker thread, and
    a normal in-memory engine would hand that thread an empty database.
    """
    from fastapi import FastAPI

    from app.api import routes_evidence
    from app.api.deps import get_db

    app = FastAPI()
    app.include_router(routes_evidence.router)
    app.dependency_overrides[get_db] = lambda: session
    return app


@pytest.fixture()
def http_session():
    import hashlib

    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker

    from app.db.models import ApiKeyEntry, Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for raw, role in (("inv-key", "investigator"), ("view-key", "viewer")):
        db.add(ApiKeyEntry(
            key_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            user_id=f"{role}1",
            role=role,
            department=None,
        ))
    db.commit()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture()
def client(http_session):
    from fastapi.testclient import TestClient

    return TestClient(_http_app(http_session))


def test_http_export_rejects_a_too_short_purpose(client, http_session, crops_dir):
    """The purpose floor is the control that keeps purpose-binding from
    being a decorative field — and it only exists at the Query layer."""
    event = _seed(http_session, crops_dir)

    response = client.get(
        f"/evidence/event/{event.id}/package",
        params={"purpose": "x"},
        headers={"X-Sentinel-API-Key": "inv-key"},
    )

    assert response.status_code == 422


def test_http_export_requires_a_purpose_at_all(client, http_session, crops_dir):
    event = _seed(http_session, crops_dir)

    response = client.get(
        f"/evidence/event/{event.id}/package",
        headers={"X-Sentinel-API-Key": "inv-key"},
    )

    assert response.status_code == 422


def test_http_export_requires_authentication(client, http_session, crops_dir):
    event = _seed(http_session, crops_dir)

    response = client.get(
        f"/evidence/event/{event.id}/package", params={"purpose": _PURPOSE}
    )

    assert response.status_code == 401


def test_http_viewer_cannot_export_but_can_verify(client, http_session, crops_dir):
    """Export is investigator+; verification is deliberately viewer-level."""
    event = _seed(http_session, crops_dir)
    viewer = {"X-Sentinel-API-Key": "view-key"}

    export = client.get(
        f"/evidence/event/{event.id}/package", params={"purpose": _PURPOSE}, headers=viewer
    )
    verify = client.get(f"/evidence/event/{event.id}/verify", headers=viewer)

    assert export.status_code == 403
    assert verify.status_code == 200
    assert verify.json()["status"] == integrity.VERIFIED


def test_http_confirmed_export_succeeds_end_to_end(client, http_session, crops_dir):
    event = _seed(http_session, crops_dir)

    response = client.get(
        f"/evidence/event/{event.id}/package",
        params={"purpose": _PURPOSE, "case_id": "FIR/2026/9"},
        headers={"X-Sentinel-API-Key": "inv-key"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sighting"]["evidence_class"] == evclass.CONFIRMED
    assert body["image"]["integrity"]["status"] == integrity.VERIFIED
    assert body["case_id"] == "FIR/2026/9"


def test_http_lead_only_export_returns_409(client, http_session, crops_dir):
    event = _seed(http_session, crops_dir, plate=None, link_method="appearance_match")

    response = client.get(
        f"/evidence/event/{event.id}/package",
        params={"purpose": _PURPOSE},
        headers={"X-Sentinel-API-Key": "inv-key"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["evidence_class"] == evclass.LEAD_ONLY


def test_http_certificate_returns_pdf_bytes(client, http_session, crops_dir):
    event = _seed(http_session, crops_dir)

    response = client.get(
        f"/evidence/event/{event.id}/certificate.pdf",
        params={"purpose": _PURPOSE},
        headers={"X-Sentinel-API-Key": "inv-key"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


# -------------------------------------------------------------------- PDF

def test_certificate_pdf_renders_real_pdf_bytes(session, crops_dir):
    """Renderer tested directly, matching test_gap_analysis_pdf.py — the
    StreamingResponse wrapper is framework plumbing, the bytes are ours."""
    event = _seed(session, crops_dir)
    pkg = evidence_package(
        event.id, purpose=_PURPOSE, case_id="FIR/2026/1",
        db=session, principal=Principal("i1", "investigator", "Police"),
    )

    pdf_bytes = _render_certificate_pdf(pkg)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000  # a broken/empty render would be tiny


def test_certificate_route_returns_pdf_attachment(session, crops_dir):
    event = _seed(session, crops_dir)

    response = evidence_certificate_pdf(
        event.id, purpose=_PURPOSE, case_id="FIR/2026/1",
        db=session, principal=Principal("i1", "investigator", "Police"),
    )

    assert response.media_type == "application/pdf"
    assert f"sentinel_evidence_event_{event.id}.pdf" in response.headers["content-disposition"]


def test_certificate_export_is_refused_for_lead_only(session, crops_dir):
    """The PDF path must carry the same gate as the JSON path — a second
    export route is a second place the tier check could be forgotten."""
    event = _seed(session, crops_dir, plate=None, link_method="appearance_match")

    with pytest.raises(HTTPException) as excinfo:
        evidence_certificate_pdf(
            event.id, purpose=_PURPOSE, case_id=None,
            db=session, principal=Principal("i1", "investigator", "Police"),
        )

    assert excinfo.value.status_code == 409
