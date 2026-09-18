from __future__ import annotations

import csv
import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from .. import config
from ..analytics.anpr_suitability import anpr_suitability_by_camera
from ..analytics.calibration import MIN_CALIBRATION_POINTS, CalibrationPoint, compute_homography_json
from ..catalogue import catalogue
from ..db.models import CameraAuditLog, CameraRegistry, VehicleEvent
from .auth import Principal, department_scope, require_role
from .deps import get_db

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _registered_cameras(db: Session, principal: Principal | None = None) -> list[CameraRegistry]:
    """Same recording-only scope as catalogue.py's filter (see config.py's
    DEMO_CAMERA_SCOPE) — applied here too so a scoped recording doesn't show
    the rest of this environment's real onboarded cameras as "offline"
    decoys alongside the demo's actual 5. No-op when unset.

    Also applies department-scoped RBAC (see auth.py's `department_scope`):
    a non-admin key tied to a department only sees THAT department's
    registered cameras — cameras with no department set yet (unregistered/
    ungap-analyzed) are excluded from a department-scoped view, since
    showing "unknown department" cameras to every department's
    investigators would leak the existence of other departments'
    unclaimed cameras. `principal=None` (internal callers, e.g. the health-
    sync loop) means unrestricted, same as an admin principal."""
    query = db.query(CameraRegistry)
    if config.DEMO_CAMERA_SCOPE is not None:
        query = query.filter(CameraRegistry.id.in_(config.DEMO_CAMERA_SCOPE))
    if principal is not None:
        dept = department_scope(principal)
        if dept is not None:
            query = query.filter(CameraRegistry.department == dept)
    return query.all()

# Camera health is considered stale (and reported unhealthy) if no frame has
# arrived in this long, even if the worker's socket still looks "connected"
# — matches the sandbox guide's own note that feeds can stall mid-stream.
HEALTH_STALE_S = 90.0


def _merged_camera_view(
    cam_id: str, registry, live_info, include_raw_urls: bool = False, anpr_suitability: dict | None = None,
) -> dict:
    """Model 1's registry is metadata-first (see HACKATHON_DETAILS.md §7):
    a camera can be "registered" (in CameraRegistry, with department/GIS
    metadata) independently of whether it's currently live in the
    catalogue. Earlier versions of this endpoint only read the live
    catalogue and silently dropped department/lat/lon/health — merging both
    sources here is the actual fix for that.

    Takes an already-fetched `registry` row rather than fetching it itself:
    `list_cameras` used to call this once per camera, each doing its own
    `session.get()` — an N+1 that's harmless at 30 cameras but directly
    undercuts the 80k-camera scalability story. Batch-fetching once in the
    caller and passing the row in fixes both that AND a redundant second
    fetch `get_camera` was doing (fetch once, then call this, which fetched
    again). Found by software-engineering review 2026-09-04.

    `include_raw_urls` gates `rtsp_url`/`whep_url`: both embed the real
    sandbox login (`email:password@`, see catalogue.py) directly in the
    URL. The frontend never reads either field — it plays video through
    the authenticated HLS proxy (routes_stream.py) via `hls_url` only — so
    a `viewer`-role key has no legitimate need for them. Found by security
    review 2026-09-04: any viewer key could extract the actual government
    sandbox credentials through this endpoint. Restricted to admin."""
    return {
        "id": cam_id,
        "location": (live_info.location if live_info else None) or (registry.location_name if registry else None),
        "codec": live_info.codec if live_info else None,
        "live": bool(live_info),
        "rtsp_url": (live_info.rtsp_url if live_info else None) if include_raw_urls else None,
        "whep_url": (live_info.whep_url if live_info else None) if include_raw_urls else None,
        "hls_url": live_info.hls_url if live_info else None,
        "department": registry.department if registry else None,
        "vendor": registry.vendor if registry else None,
        "camera_type": registry.camera_type if registry else None,
        "latitude": registry.latitude if registry else None,
        "longitude": registry.longitude if registry else None,
        "is_healthy": registry.is_healthy if registry else None,
        # Distinct from is_healthy on purpose: is_healthy is stream
        # connectivity only. A camera can be "connected, not stale" while
        # its analytics calls are all failing (found 2026-09-13) — that
        # must be visible here, not folded into is_healthy's single bool
        # (CLAUDE.md 24.11: a polished UI must not conceal degraded
        # backend state).
        "analytics_degraded": registry.analytics_degraded if registry else None,
        "last_analytics_success_at": (
            registry.last_analytics_success_at.isoformat()
            if registry and registry.last_analytics_success_at
            else None
        ),
        "last_seen_live_at": registry.last_seen_live_at.isoformat() if registry and registry.last_seen_live_at else None,
        "under_maintenance": registry.under_maintenance if registry else False,
        "maintenance_reason": registry.maintenance_reason if registry else None,
        "maintenance_until": (
            registry.maintenance_until.isoformat() if registry and registry.maintenance_until else None
        ),
        "is_restricted_zone": registry.is_restricted_zone if registry else False,
        "expected_direction_deg": registry.expected_direction_deg if registry else None,
        "install_date": registry.install_date.isoformat() if registry and registry.install_date else None,
        "coverage_radius_m": registry.coverage_radius_m if registry else None,
        # Whether VehicleEvent.speed_kmh is real for this camera's future
        # sightings (analytics/calibration.py) — never the matrix itself,
        # which is internal-only inference input, not investigator-facing
        # data.
        "homography_calibrated": bool(registry.homography_json) if registry else False,
        "homography_calibrated_at": (
            registry.homography_calibrated_at.isoformat()
            if registry and registry.homography_calibrated_at
            else None
        ),
        "homography_reference_note": registry.homography_reference_note if registry else None,
        "onboarded": registry is not None,
        "anpr_suitability": anpr_suitability,
        # Model 2's "unified viewer connecting >=2 different systems": null
        # source_system = a real Gujarat sandbox camera; a non-null value
        # marks a row onboarded from a genuinely independent external
        # system (see external_camera_source.py). snapshot_image_url is
        # only ever set for such rows and must be rendered as a
        # periodically-refreshed still image, never as live HLS video.
        "source_system": registry.source_system if registry else None,
        "snapshot_image_url": registry.snapshot_image_url if registry else None,
    }


@router.get("")
def list_cameras(
    department: str | None = None,
    camera_type: str | None = None,
    is_healthy: bool | None = None,
    live: bool | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Model 1 view: union of the live catalogue AND the onboarded registry
    — a camera that's registered but currently offline (a real gap-analysis
    case) still shows up, just with live=false.

    Department-scoped (see auth.py's `department_scope`): a non-admin key
    tied to a department only sees that department's registered cameras.
    Live-but-not-yet-onboarded cameras (department unknown) are excluded
    from a department-scoped view entirely — they carry no department
    attribution to scope by, and showing them would leak the existence of
    other departments' unclaimed cameras to every department equally.
    That global "what's live but unregistered" view stays available via
    gap-analysis, which is investigator+ AND still department-scoped the
    same way.

    Optional query-param filters (found missing — client-side-only before,
    see TASKS.md's P3 list — a real fix needed at 80k-camera scale, not
    just the pilot's 30): department/camera_type/is_healthy/live are exact
    matches, `q` is a case-insensitive substring match against id or
    location name."""
    live_cams = catalogue.cameras
    registered = _registered_cameras(db, principal)
    registry_by_id = {r.id: r for r in registered}
    dept = department_scope(principal)
    all_ids = set(registry_by_id.keys()) if dept is not None else (set(live_cams.keys()) | set(registry_by_id.keys()))
    include_raw_urls = principal.role == "admin"
    suitability = anpr_suitability_by_camera(db, list(all_ids))
    rows = [
        _merged_camera_view(
            cam_id, registry_by_id.get(cam_id), live_cams.get(cam_id), include_raw_urls, suitability.get(cam_id)
        )
        for cam_id in sorted(all_ids)
    ]
    if department is not None:
        rows = [r for r in rows if r["department"] == department]
    if camera_type is not None:
        rows = [r for r in rows if r["camera_type"] == camera_type]
    if is_healthy is not None:
        rows = [r for r in rows if r["is_healthy"] == is_healthy]
    if live is not None:
        rows = [r for r in rows if r["live"] == live]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["id"].lower() or (r["location"] and needle in r["location"].lower())]
    return rows


def _compute_gap_analysis(db: Session, principal: Principal) -> dict:
    """Shared by the JSON endpoint and the PDF export below so the two
    never drift — the PDF is a rendering of the same numbers, not a
    second, independently-computed report."""
    dept = department_scope(principal)
    live = catalogue.cameras  # full catalogue — needed to correctly tell whether THIS department's own cameras are live
    registered = {r.id: r for r in _registered_cameras(db, principal)}

    # "live but not onboarded ANYWHERE" is a global, cross-department fact
    # (we don't know which department an unregistered live camera belongs
    # to) — hide it for a department-scoped principal rather than leak
    # other departments' unclaimed cameras; still fully visible to admin.
    live_not_onboarded = [] if dept is not None else sorted(set(live) - set(registered))
    onboarded_not_live = sorted(set(registered) - set(live))
    missing_department = sorted(cid for cid, r in registered.items() if not r.department)
    missing_gis = sorted(cid for cid, r in registered.items() if r.latitude is None or r.longitude is None)
    # A camera deliberately taken down for servicing must not read as the
    # same "unexpected failure" signal as a camera that's actually broken
    # (REQUIREMENTS_COVERAGE.md's named Model 1 gap: "maintenance status"
    # as a concept distinct from is_healthy). Reported separately below
    # instead, so gap-analysis stays a genuine anomaly list, not a mix of
    # real problems and expected, human-acknowledged downtime.
    under_maintenance = sorted(cid for cid, r in registered.items() if r.under_maintenance)
    unhealthy = sorted(
        cid for cid, r in registered.items() if r.is_healthy is False and not r.under_maintenance
    )
    missing_install_date = sorted(cid for cid, r in registered.items() if r.install_date is None)
    ageing_cutoff = dt.datetime.utcnow() - dt.timedelta(days=365.25 * config.CAMERA_AGEING_THRESHOLD_YEARS)
    ageing = sorted(cid for cid, r in registered.items() if r.install_date is not None and r.install_date < ageing_cutoff)

    by_department: dict[str, int] = {}
    for r in registered.values():
        key = r.department or "unassigned"
        by_department[key] = by_department.get(key, 0) + 1

    return {
        "catalogue_size": len(live),
        "registered_size": len(registered),
        "live_not_onboarded": live_not_onboarded,
        "onboarded_not_live": onboarded_not_live,
        "missing_department": missing_department,
        "missing_gis_coordinates": missing_gis,
        "unhealthy": unhealthy,
        "under_maintenance": under_maintenance,
        "missing_install_date": missing_install_date,
        "ageing": ageing,
        "ageing_threshold_years": config.CAMERA_AGEING_THRESHOLD_YEARS,
        "cameras_by_department": by_department,
    }


@router.get("/gap-analysis")
def gap_analysis(db: Session = Depends(get_db), principal: Principal = Depends(require_role("investigator"))):
    """Model 1 explicitly requires a 'gap-analysis report' deliverable:
    which cameras are known but not onboarded with metadata, which are
    onboarded but not currently live, and department coverage — the
    concrete gaps a real rollout would need to close next.

    Department-scoped like list_cameras above: a non-admin key tied to a
    department sees only that department's registered/missing/unhealthy
    counts, not the whole state's."""
    return _compute_gap_analysis(db, principal)


@router.get("/gap-analysis/export.pdf")
def gap_analysis_export_pdf(
    db: Session = Depends(get_db), principal: Principal = Depends(require_role("investigator"))
):
    """Model 1's 'gap-analysis report' deliverable, as an actual exportable
    document (found missing entirely — see TASKS.md P1) rather than just
    the JSON `gap_analysis` endpoint consumed by `GapAnalysisPanel.jsx`.
    Same data, same department scoping — this is a rendering, not a
    second report."""
    pdf_bytes = _render_gap_analysis_pdf(_compute_gap_analysis(db, principal), principal)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=sentinel_gap_analysis.pdf"},
    )


def _render_gap_analysis_pdf(report: dict, principal: Principal) -> bytes:
    """Split out from the route so tests can get the raw bytes directly
    instead of reaching into a StreamingResponse's async body_iterator."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="Sentinel Gap-Analysis Report")
    styles = getSampleStyleSheet()
    scope_note = f"Department scope: {department_scope(principal) or 'all (admin/unscoped)'}"
    elements = [
        Paragraph("Sentinel — Camera Registry Gap-Analysis Report", styles["Title"]),
        Paragraph(f"Generated {dt.datetime.utcnow().isoformat()}Z · {scope_note}", styles["Normal"]),
        Spacer(1, 16),
    ]

    summary_rows = [
        ["Metric", "Count"],
        ["Live cameras in catalogue", report["catalogue_size"]],
        ["Registered in this scope", report["registered_size"]],
        ["Live but not onboarded", len(report["live_not_onboarded"])],
        ["Onboarded but not currently live", len(report["onboarded_not_live"])],
        ["Missing department attribution", len(report["missing_department"])],
        ["Missing GIS coordinates", len(report["missing_gis_coordinates"])],
        ["Unhealthy", len(report["unhealthy"])],
        ["Under maintenance", len(report["under_maintenance"])],
        ["Missing install date", len(report["missing_install_date"])],
        [f"Ageing (installed >{report['ageing_threshold_years']:g}y ago)", len(report["ageing"])],
    ]
    summary_table = Table(summary_rows, colWidths=[260, 100])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements += [summary_table, Spacer(1, 16)]

    elements.append(Paragraph("Cameras by department", styles["Heading2"]))
    dept_rows = [["Department", "Count"]] + (
        [[dept, count] for dept, count in sorted(report["cameras_by_department"].items())]
        or [["(none registered)", ""]]
    )
    dept_table = Table(dept_rows, colWidths=[260, 100])
    dept_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements += [dept_table, Spacer(1, 16)]

    def _id_list_section(title: str, ids: list[str]) -> None:
        elements.append(Paragraph(title, styles["Heading2"]))
        elements.append(Paragraph(", ".join(ids) if ids else "(none)", styles["Normal"]))
        elements.append(Spacer(1, 12))

    _id_list_section("Live but not onboarded", report["live_not_onboarded"])
    _id_list_section("Onboarded but not currently live", report["onboarded_not_live"])
    _id_list_section("Missing department attribution", report["missing_department"])
    _id_list_section("Missing GIS coordinates", report["missing_gis_coordinates"])
    _id_list_section("Unhealthy", report["unhealthy"])
    _id_list_section("Under maintenance", report["under_maintenance"])
    _id_list_section("Missing install date", report["missing_install_date"])
    _id_list_section(f"Ageing (installed >{report['ageing_threshold_years']:g}y ago)", report["ageing"])

    doc.build(elements)
    return buf.getvalue()


class CameraOnboard(BaseModel):
    id: str
    department: str | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    vendor: str | None = None
    camera_type: str | None = None  # PTZ / dome / fixed / bullet, free text
    is_restricted_zone: bool = False
    expected_direction_deg: float | None = None
    install_date: dt.datetime | None = None
    coverage_radius_m: float | None = None


def _apply_onboard_fields(existing: CameraRegistry, body: CameraOnboard) -> None:
    existing.department = body.department
    existing.location_name = body.location_name
    existing.latitude = body.latitude
    existing.longitude = body.longitude
    existing.vendor = body.vendor
    existing.camera_type = body.camera_type
    existing.is_restricted_zone = body.is_restricted_zone
    existing.expected_direction_deg = body.expected_direction_deg
    existing.install_date = body.install_date
    existing.coverage_radius_m = body.coverage_radius_m


def _record_onboard_audit(db: Session, camera_id: str, user_id: str, is_new: bool) -> None:
    db.add(CameraAuditLog(camera_id=camera_id, user_id=user_id, action="onboarded" if is_new else "updated"))


@router.post("")
def onboard_camera(
    body: CameraOnboard,
    db: Session = Depends(get_db),
    admin: Principal = Depends(require_role("admin")),
):
    """Model 1's 'API-based onboarding' / 'manual onboarding' deliverable.
    Upsert: onboarding an already-known camera updates its metadata rather
    than erroring, since re-running a bulk import with corrected data is a
    normal workflow, not an edge case."""
    existing = db.get(CameraRegistry, body.id)
    is_new = existing is None
    if existing is None:
        existing = CameraRegistry(id=body.id)
        db.add(existing)
    _apply_onboard_fields(existing, body)
    _record_onboard_audit(db, body.id, admin.user_id, is_new)
    db.commit()
    return {"status": "onboarded", "id": body.id}


@router.post("/bulk")
def onboard_cameras_bulk(
    bodies: list[CameraOnboard],
    db: Session = Depends(get_db),
    admin: Principal = Depends(require_role("admin")),
):
    """Bulk-import deliverable — same upsert semantics as onboard_camera,
    looped in one transaction so a 50-camera CSV-derived import is one call."""
    ids = []
    for body in bodies:
        existing = db.get(CameraRegistry, body.id)
        is_new = existing is None
        if existing is None:
            existing = CameraRegistry(id=body.id)
            db.add(existing)
        _apply_onboard_fields(existing, body)
        _record_onboard_audit(db, body.id, admin.user_id, is_new)
        ids.append(body.id)
    db.commit()
    return {"status": "onboarded", "count": len(ids), "ids": ids}


@router.get("/{camera_id}/audit-log")
def camera_audit_log(
    camera_id: str, db: Session = Depends(get_db), _admin: Principal = Depends(require_role("admin"))
):
    """Model 1's onboarding-audit-trail deliverable: who onboarded/edited
    this camera's registry metadata, and when. Admin-only, matching that
    onboarding itself (the write side) is already admin-only."""
    entries = (
        db.query(CameraAuditLog)
        .filter(CameraAuditLog.camera_id == camera_id)
        # Two edits in the same request/transaction can share an identical
        # created_at (default's resolution can tie) — id DESC as a
        # tiebreak keeps ordering deterministic instead of falling back to
        # SQLite's unspecified row order for ties (real bug caught by
        # test_camera_registry_model1.py's re-onboard test).
        .order_by(CameraAuditLog.created_at.desc(), CameraAuditLog.id.desc())
        .limit(2000)
        .all()
    )
    return [
        {"user_id": e.user_id, "action": e.action, "created_at": e.created_at.isoformat()}
        for e in entries
    ]


class MaintenanceUpdate(BaseModel):
    under_maintenance: bool
    reason: str | None = None
    until: dt.datetime | None = None


@router.post("/{camera_id}/maintenance")
def set_maintenance_status(
    camera_id: str,
    body: MaintenanceUpdate,
    db: Session = Depends(get_db),
    admin: Principal = Depends(require_role("admin")),
):
    """Model 1's maintenance-status deliverable (REQUIREMENTS_COVERAGE.md's
    one named open gap: is_healthy/analytics_degraded are OBSERVED stream/
    analytics state, not a human decision that a camera is deliberately
    offline for servicing). Admin-only, same as onboarding — this is a
    registry-metadata write, not an observed signal, so it must be a
    deliberate human action, never inferred from health state.

    Setting under_maintenance=True does not touch is_healthy/
    analytics_degraded themselves (those stay real observed signals); it
    only changes how gap-analysis interprets an unhealthy reading for this
    camera — see _compute_gap_analysis above."""
    # No department-scope check here: this route is admin-only
    # (require_role("admin")), and department_scope() always returns None
    # for role=="admin" regardless of that key's own department field
    # (see auth.py's department_scope docstring) — same reason
    # onboard_camera/camera_audit_log above don't scope either.
    registry = db.get(CameraRegistry, camera_id)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"camera {camera_id} is not registered — onboard it first")

    registry.under_maintenance = body.under_maintenance
    registry.maintenance_reason = body.reason if body.under_maintenance else None
    registry.maintenance_until = body.until if body.under_maintenance else None
    db.add(CameraAuditLog(
        camera_id=camera_id,
        user_id=admin.user_id,
        action="maintenance_set" if body.under_maintenance else "maintenance_cleared",
    ))
    db.commit()
    return {
        "id": camera_id,
        "under_maintenance": registry.under_maintenance,
        "maintenance_reason": registry.maintenance_reason,
        "maintenance_until": registry.maintenance_until.isoformat() if registry.maintenance_until else None,
    }


class CalibrationPointIn(BaseModel):
    image_x: float
    image_y: float
    world_x: float  # metres, arbitrary local ground-plane origin (e.g. a surveyed lane edge)
    world_y: float


class CalibrationSubmit(BaseModel):
    points: list[CalibrationPointIn] = Field(min_length=MIN_CALIBRATION_POINTS)
    # Required, not optional: a stored calibration with no stated provenance
    # is indistinguishable from a fabricated one to a later investigator —
    # see homography_reference_note's docstring on db/models.py.
    reference_note: str = Field(min_length=1)


@router.post("/{camera_id}/calibration")
def set_camera_calibration(
    camera_id: str,
    body: CalibrationSubmit,
    db: Session = Depends(get_db),
    admin: Principal = Depends(require_role("admin")),
):
    """Model 2's homography-calibration deliverable: turns a real physical
    survey (>=4 image-pixel <-> ground-metre point pairs) into the stored
    matrix that VehicleEvent.speed_kmh is computed from going forward (see
    analytics/calibration.py, analytics/pipeline.py). Admin-only, same
    reasoning as maintenance-status above — this is a deliberate human
    attestation that a camera was actually surveyed, never something the
    system should infer or guess at.

    Does not touch existing VehicleEvent rows: calibrating a camera only
    affects sightings finalized AFTER this call, matching the append-only
    evidence stance elsewhere in this project (an event's speed_kmh is
    frozen at the confidence level the system actually had when it was
    written, not silently upgraded later)."""
    registry = db.get(CameraRegistry, camera_id)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"camera {camera_id} is not registered — onboard it first")

    points = [CalibrationPoint(p.image_x, p.image_y, p.world_x, p.world_y) for p in body.points]
    try:
        homography_json = compute_homography_json(points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    registry.homography_json = homography_json
    registry.homography_calibrated_at = dt.datetime.utcnow()
    registry.homography_reference_note = body.reference_note
    db.add(CameraAuditLog(camera_id=camera_id, user_id=admin.user_id, action="calibration_set"))
    db.commit()
    return {
        "id": camera_id,
        "homography_calibrated": True,
        "homography_calibrated_at": registry.homography_calibrated_at.isoformat(),
        "homography_reference_note": registry.homography_reference_note,
    }


@router.get("/export.csv")
def export_cameras_csv(
    db: Session = Depends(get_db), principal: Principal = Depends(require_role("investigator"))
):
    """Model 1's registry export deliverable (found missing entirely in
    MODULE_GAP_ANALYSIS.md 2026-09-05). Registry metadata only — never
    includes rtsp_url/whep_url (see _merged_camera_view's docstring on why
    those are admin-only in the JSON view too; a CSV export is an even
    easier way to leak the sandbox's embedded credentials if this were
    careless about it). Department-scoped the same way as list_cameras."""
    dept = department_scope(principal)
    live = catalogue.cameras
    registered = _registered_cameras(db, principal)
    registry_by_id = {r.id: r for r in registered}
    all_ids = sorted(set(registry_by_id.keys()) if dept is not None else (set(live.keys()) | set(registry_by_id.keys())))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "location", "department", "vendor", "camera_type", "latitude", "longitude",
        "is_healthy", "last_seen_live_at", "under_maintenance", "maintenance_reason",
        "is_restricted_zone", "expected_direction_deg",
        "install_date", "coverage_radius_m", "onboarded", "live",
    ])
    for cam_id in all_ids:
        registry = registry_by_id.get(cam_id)
        live_info = live.get(cam_id)
        row = _merged_camera_view(cam_id, registry, live_info, include_raw_urls=False)
        writer.writerow([
            row["id"], row["location"], row["department"], row["vendor"], row["camera_type"],
            row["latitude"], row["longitude"], row["is_healthy"], row["last_seen_live_at"],
            row["under_maintenance"], row["maintenance_reason"],
            row["is_restricted_zone"], row["expected_direction_deg"], row["install_date"],
            row["coverage_radius_m"], row["onboarded"], row["live"],
        ])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sentinel_camera_registry.csv"},
    )


@router.get("/{camera_id}")
def get_camera(camera_id: str, db: Session = Depends(get_db), principal: Principal = Depends(require_role("viewer"))):
    live_info = catalogue.get(camera_id)
    registry = db.get(CameraRegistry, camera_id)
    dept = department_scope(principal)
    if dept is not None and (registry is None or registry.department != dept):
        # Same 404 message/shape as "doesn't exist" — a department-scoped
        # principal shouldn't be able to distinguish "this camera exists
        # but isn't mine" from "this camera doesn't exist" (see
        # department_scope's docstring for why this is scoped to the
        # registry, not vehicle search).
        raise HTTPException(status_code=404, detail=f"camera {camera_id} not found")
    if live_info is None and registry is None:
        raise HTTPException(status_code=404, detail=f"camera {camera_id} not found")
    return _merged_camera_view(
        camera_id, registry, live_info, include_raw_urls=principal.role == "admin",
        anpr_suitability=anpr_suitability_by_camera(db, [camera_id]).get(camera_id),
    )


@router.get("/{camera_id}/last-detection")
def last_detection(
    camera_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Most recent real detection at this camera. Not a live video overlay —
    the pipeline processes sampled frames server-side, it doesn't composite
    boxes back onto the HLS stream — but it IS the real bbox/plate/attributes
    from the latest processed frame, meant to be polled and shown alongside
    the live player as a periodically-refreshed "last seen" panel."""
    registry = db.get(CameraRegistry, camera_id)
    dept = department_scope(principal)
    if dept is not None and (registry is None or registry.department != dept):
        # Keep the same non-enumerating response as get_camera().
        raise HTTPException(status_code=404, detail=f"camera {camera_id} not found")

    event = (
        db.query(VehicleEvent)
        .filter(VehicleEvent.camera_id == camera_id)
        .order_by(VehicleEvent.observed_at.desc())
        .first()
    )
    if event is None:
        return {"camera_id": camera_id, "detection": None}
    return {
        "camera_id": camera_id,
        "detection": {
            "event_id": event.id,
            "observed_at": event.observed_at.isoformat(),
            "plate": event.plate,
            "plate_confidence": event.plate_confidence,
            "vehicle_type": event.vehicle_type,
            "color": event.color,
            "confidence": event.confidence,
            "has_evidence_image": event.crop_path is not None,
            "bbox": (
                {"x1": event.bbox_x1, "y1": event.bbox_y1, "x2": event.bbox_x2, "y2": event.bbox_y2}
                if event.bbox_x1 is not None else None
            ),
        },
    }


@router.get("/{camera_id}/stats")
def camera_stats(
    camera_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Bounded recent-sighting summary for the camera detail panel.

    The count covers at most the latest 1,000 events observed in the last
    24 hours.  The explicit cap keeps an info-panel open from becoming an
    unbounded scan on a high-volume camera; ``truncated`` tells the client
    when it is a lower bound rather than a complete 24-hour count.
    """
    registry = db.get(CameraRegistry, camera_id)
    dept = department_scope(principal)
    if dept is not None and (registry is None or registry.department != dept):
        raise HTTPException(status_code=404, detail=f"camera {camera_id} not found")
    if registry is None and catalogue.get(camera_id) is None:
        raise HTTPException(status_code=404, detail=f"camera {camera_id} not found")

    window_started_at = dt.datetime.utcnow() - dt.timedelta(hours=24)
    events = (
        db.query(VehicleEvent)
        .filter(VehicleEvent.camera_id == camera_id, VehicleEvent.observed_at >= window_started_at)
        .order_by(VehicleEvent.observed_at.desc())
        .limit(1000)
        .all()
    )
    breakdown = {"CONFIRMED": 0, "PROBABLE": 0, "LEAD_ONLY": 0}
    from ..analytics import evidence_class as ec
    for event in events:
        breakdown[ec.classify(event.plate, event.link_method)] += 1
    return {
        "camera_id": camera_id,
        "window_hours": 24,
        "window_started_at": window_started_at.isoformat(),
        "sighting_count": len(events),
        "by_evidence_class": breakdown,
        "truncated": len(events) == 1000,
    }
