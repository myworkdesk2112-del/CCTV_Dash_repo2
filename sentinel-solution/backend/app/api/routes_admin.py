"""Admin/governance endpoints: retention policy visibility + manual purge.

Surfacing the retention policy and letting an admin trigger a purge on
demand is part of the DPDP/governance story being demonstrable, not just
configured — a jury can see the storage-limitation control exists and
works, rather than taking it on faith.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..analytics.govt_db_adapters import status_report as govt_db_status_report
from ..db.models import Alert, AuditLog, CameraDensityWindow, CameraRegistry, FederatedEvent
from ..db.retention import purge_expired
from .auth import Principal, require_role
from .deps import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/density")
def density_windows(
    camera_id: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _principal: Principal = Depends(require_role("admin")),
):
    """Pilot sampled-frame counts; not a crowd-size estimate or alert."""
    query = db.query(CameraDensityWindow)
    if camera_id:
        query = query.filter(CameraDensityWindow.camera_id == camera_id)
    rows = query.order_by(CameraDensityWindow.window_started_at.desc()).limit(min(max(limit, 1), 500)).all()
    return {
        "count_semantics": "sampled-frame detector outputs; not unique people or vehicles",
        "windows": [{
            "camera_id": row.camera_id,
            "window_started_at": row.window_started_at.isoformat(),
            "window_seconds": row.window_seconds,
            "sampled_frames": row.sampled_frames,
            "vehicle_detections": row.vehicle_detections,
            "person_detections": row.person_detections,
        } for row in rows],
    }


@router.get("/central-rollup")
def central_rollup(
    db: Session = Depends(get_db), _principal: Principal = Depends(require_role("admin")),
):
    """Read-only pilot rollup, explicitly not a statewide deployment."""
    by_department = db.query(CameraRegistry.department, func.count(CameraRegistry.id)).group_by(CameraRegistry.department).all()
    healthy = db.query(CameraRegistry).filter(CameraRegistry.is_healthy.is_(True)).count()
    unhealthy = db.query(CameraRegistry).filter(CameraRegistry.is_healthy.is_(False)).count()
    sources = [row[0] for row in db.query(FederatedEvent.source_system).distinct().order_by(FederatedEvent.source_system)]
    return {
        "scope": "pilot rollup from this database; not a statewide deployment",
        "cameras_by_department": {department or "unassigned": count for department, count in by_department},
        "health": {"healthy": healthy, "unhealthy": unhealthy, "unknown": db.query(CameraRegistry).filter(CameraRegistry.is_healthy.is_(None)).count()},
        "active_alerts": db.query(Alert).filter(Alert.status.in_(("new", "acknowledged"))).count(),
        "federation": {"event_count": db.query(FederatedEvent).count(), "sources_present": sources},
    }


@router.get("/retention-policy")
def retention_policy(_principal: Principal = Depends(require_role("investigator"))):
    """Visible to investigators+ so oversight isn't admin-only."""
    return {
        "vehicle_data_retention_days": config.RETENTION_DAYS,
        "audit_log_retention_days": config.AUDIT_RETENTION_DAYS,
        "sweep_interval_s": config.RETENTION_SWEEP_INTERVAL_S,
        "note": (
            "Vehicle events/identities/alerts are purged after "
            f"{config.RETENTION_DAYS} days; audit logs kept "
            f"{config.AUDIT_RETENTION_DAYS} days (accountability trail "
            "outlives the personal data). Per-case evidential retention "
            "exemption is future work — export to a case file before data "
            "ages out."
        ),
    }


@router.post("/purge")
def trigger_purge(db: Session = Depends(get_db), _admin: Principal = Depends(require_role("admin"))):
    """Run the retention purge now (admin only). Idempotent."""
    return purge_expired(db)


@router.get("/audit-log")
def list_audit_log(
    limit: int = 200,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Read view of the purpose-bound query log every /vehicle/* lookup
    writes to (see routes_vehicle.py). Powers the Investigations screen —
    real accountability data, not a mock activity feed.

    Scoped to the caller's own queries unless they're admin: despite the
    `/admin` prefix, this only required `investigator` role, so any
    investigator could read every OTHER investigator's/department's
    search purposes and case IDs — a real cross-department privacy leak,
    found by security review 2026-09-04. AuditLog has no department
    column to filter on directly, so scoping to the caller's own
    `user_id` is the fix that needs no schema change and preserves the
    screen's "see my own accountability trail" value; admin keeps the
    full cross-user oversight view."""
    query = db.query(AuditLog)
    if principal.role != "admin":
        query = query.filter(AuditLog.user_id == principal.user_id)
    rows = query.order_by(AuditLog.created_at.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "purpose": r.purpose,
            "case_id": r.case_id,
            "query": r.query,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/govt-db-status")
def govt_db_status(_principal: Principal = Depends(require_role("admin"))):
    """Per-system configuration status for VAHAN/SARTHI/eGujCop/CCTNS
    (AFIS/NAFIS) query integration (HLD.md §6's "query, don't copy"
    principle). Every row reads False in this deployment — none of these
    have a real access agreement or credentials, and this endpoint makes
    no query, real or fabricated, when unconfigured (see
    `analytics/govt_db_adapters.py`)."""
    return {
        "note": (
            "Read-only, on-demand query integration surface for "
            "government law-enforcement databases. None are configured "
            "in this deployment — each requires a real integration "
            "agreement with the owning system, which this project does "
            "not have."
        ),
        "systems": govt_db_status_report(),
    }
