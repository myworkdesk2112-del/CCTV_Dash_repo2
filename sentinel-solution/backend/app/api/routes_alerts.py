from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import (
    ALERT_STATUS_ACKNOWLEDGED,
    ALERT_STATUS_NEW,
    ALERT_STATUSES,
    ALERT_TRANSITIONS,
    Alert,
    CameraRegistry,
)
from .auth import Principal, department_scope, require_role
from .deps import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _serialize(a: Alert) -> dict:
    return {
        "id": a.id,
        "plate": a.plate,
        "camera_id": a.camera_id,
        "reason": a.reason,
        "alert_type": a.alert_type or "watchlist",
        # created_at has a Python default so ORM-created alerts always have
        # it; guard anyway so a legacy/raw-inserted row with a NULL timestamp
        # can't crash the whole alerts list.
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "acknowledged": a.acknowledged,
        "evidence_class": a.evidence_class,
        "evidence_class_reason": a.evidence_class_reason,
        "status": a.status or ALERT_STATUS_NEW,
        "status_updated_by": a.status_updated_by,
        "status_updated_at": a.status_updated_at.isoformat() if a.status_updated_at else None,
        # Advertise the legal next moves so the UI never offers an invalid
        # transition (and the governance rule lives in ONE place — the model).
        "allowed_transitions": sorted(ALERT_TRANSITIONS.get(a.status or ALERT_STATUS_NEW, set())),
    }


@router.get("")
def list_alerts(
    db: Session = Depends(get_db),
    limit: int = 100,
    camera_id: str | None = None,
    principal: Principal = Depends(require_role("investigator")),
):
    query = db.query(Alert)
    department = department_scope(principal)
    if department is not None:
        query = query.join(CameraRegistry, Alert.camera_id == CameraRegistry.id).filter(
            CameraRegistry.department == department
        )
    if camera_id is not None:
        query = query.filter(Alert.camera_id == camera_id)
    alerts = query.order_by(Alert.created_at.desc()).limit(min(max(limit, 1), 500)).all()
    return [_serialize(a) for a in alerts]


def _load_alert_scoped(db: Session, alert_id: int, principal: Principal) -> Alert:
    """Fetch an alert for a state change, refusing other departments' alerts.

    Previously a department-scoped investigator could move ANY alert through
    its lifecycle, including dismissing another department's live stolen-
    vehicle alert (dismissed is terminal), with `purpose` defaulting to
    "unspecified" (security review 2026-09-26). Acting on an alert is the
    owning department's call; admin and unscoped keys remain unrestricted.

    404 rather than 403, matching list_alerts (which already hides these
    rows) and the registry's non-enumerating boundary.
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    department = department_scope(principal)
    if department is not None:
        camera = db.get(CameraRegistry, alert.camera_id)
        if camera is None or camera.department != department:
            raise HTTPException(status_code=404, detail="alert not found")
    return alert


def _apply_status(alert: Alert, target: str, principal: Principal) -> None:
    """Enforce the governed lifecycle: only transitions declared in
    ALERT_TRANSITIONS are allowed. Keeps the legacy `acknowledged` boolean in
    sync (True once the alert leaves 'new') and records who/when for the
    accountability trail."""
    current = alert.status or ALERT_STATUS_NEW
    if target not in ALERT_STATUSES:
        raise HTTPException(status_code=400, detail=f"unknown status '{target}'")
    if target not in ALERT_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=409,
            detail=f"illegal transition {current} -> {target} "
            f"(allowed: {sorted(ALERT_TRANSITIONS.get(current, set())) or 'none, terminal state'})",
        )
    alert.status = target
    alert.acknowledged = target != ALERT_STATUS_NEW
    alert.status_updated_by = principal.user_id
    alert.status_updated_at = dt.datetime.utcnow()


class StatusUpdate(BaseModel):
    status: str


@router.post("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    alert = _load_alert_scoped(db, alert_id, principal)
    _apply_status(alert, body.status, principal)
    db.commit()
    return _serialize(alert)


@router.post("/{alert_id}/ack")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Legacy convenience endpoint — kept so existing clients keep working.
    Equivalent to a status transition new -> acknowledged."""
    alert = _load_alert_scoped(db, alert_id, principal)
    # Idempotent: acking an already-advanced alert is a no-op, not a 409.
    if (alert.status or ALERT_STATUS_NEW) == ALERT_STATUS_NEW:
        _apply_status(alert, ALERT_STATUS_ACKNOWLEDGED, principal)
        db.commit()
    return _serialize(alert)
