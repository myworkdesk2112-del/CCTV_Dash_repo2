"""§63-oriented evidence packaging for a single vehicle sighting.

Three endpoints, deliberately separated because they carry different
risk:

  GET /evidence/event/{id}/verify      — integrity check, any evidence class
  GET /evidence/event/{id}/package     — the provenance package (JSON)
  GET /evidence/event/{id}/certificate.pdf — printable Part A/Part B form

`verify` is available for any sighting because checking whether a file
still matches its write-time hash is an integrity question, not an
evidentiary claim: an investigator evaluating a LEAD_ONLY lead is
entitled to know whether the image they're looking at has been altered.
The two *export* paths are gated on evidence class — only CONFIRMED may
leave the system as evidence (evidence_class.EXPORTABLE_CLASSES), which
is the same gate pipeline.py applies to watchlist alerts, so a LEAD_ONLY
appearance match cannot be packaged as though a plate had been read.

Both export paths are purpose-bound and audit-logged before the artefact
is produced, not after: if the export fails midway, the fact that it was
attempted is still on the record. Exports are also logged for
same-department access, unlike routes_vehicle.py's crop viewer which
only logs cross-department reads — an export leaves the system entirely,
so every one of them is worth a row (CLAUDE.md §5.3).

Wording note: every legal caveat comes from
evidence_integrity.legal_review_notice() rather than being written here,
so the JSON and the PDF cannot drift into different-strength claims
about the same artefact.
"""
from __future__ import annotations

import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..analytics import evidence_class as ec
from ..analytics import evidence_integrity as integrity
from ..db.models import AuditLog, CameraRegistry, VehicleEvent
from .auth import Principal, department_scope, require_role
from .deps import get_db

router = APIRouter(prefix="/evidence", tags=["evidence"])

# Same floor as routes_vehicle.py — a stated purpose has to actually say
# something for the purpose-binding to be a control rather than a field.
_PURPOSE_MIN_LENGTH = 8


def _load_event_scoped(db: Session, event_id: int, principal: Principal) -> tuple[VehicleEvent, CameraRegistry | None]:
    """Fetch the event with object-level department authorisation applied.

    404 (not 403) when a department-scoped principal asks for another
    department's event: a 403 would confirm the event exists, letting a
    scoped caller enumerate other departments' sightings by id. Mirrors
    routes_vehicle.py's crop endpoint.
    """
    event = db.get(VehicleEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="no such event")

    camera = db.get(CameraRegistry, event.camera_id)
    department = department_scope(principal)
    if department is not None and (camera is None or camera.department != department):
        raise HTTPException(status_code=404, detail="no such event")
    return event, camera


def _evidence_gate(event: VehicleEvent) -> str:
    """Refuse to export anything that isn't CONFIRMED, and say why.

    409 rather than 403: the caller's credentials are fine, the artefact's
    evidentiary status is what forbids the export. The reason string is
    the same investigator-facing text the UI badge shows, so a blocked
    export explains itself in the same vocabulary as the rest of the app.
    """
    sighting_class = ec.classify(event.plate, event.link_method)
    if not ec.is_exportable(sighting_class):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "not exportable as evidence",
                "evidence_class": sighting_class,
                "reason": ec.describe(sighting_class, event.link_method),
                "exportable_classes": sorted(ec.EXPORTABLE_CLASSES),
            },
        )
    return sighting_class


def _log_export(db: Session, principal: Principal, event: VehicleEvent, purpose: str, case_id: str | None, artefact: str) -> None:
    db.add(AuditLog(
        user_id=principal.user_id,
        purpose=purpose,
        case_id=case_id,
        query=f"evidence-export:{artefact} event={event.id} camera={event.camera_id} plate={event.plate}",
    ))
    db.commit()


def _access_history(db: Session, event_id: int) -> list[dict]:
    """Prior audit rows naming this event — the package's access trail.

    Matched on the `evidence-export:... event=<id>` substring this module
    writes, plus the `event <id>` phrasing routes_vehicle.py's
    cross-department crop log uses, so the trail covers both paths that
    can reach this artefact rather than only this module's own exports.
    """
    like_export = f"%event={event_id} %"
    like_crop = f"%event {event_id} %"
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.query.like(like_export) | AuditLog.query.like(like_crop))
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    return [
        {
            "user_id": r.user_id,
            "purpose": r.purpose,
            "case_id": r.case_id,
            "action": r.query,
            "at": r.created_at.isoformat() + "Z" if r.created_at else None,
        }
        for r in rows
    ]


def _build_package(db: Session, event: VehicleEvent, camera: CameraRegistry | None, sighting_class: str, purpose: str, case_id: str | None, principal: Principal) -> dict:
    verification = integrity.verify_crop(event.crop_path, event.crop_sha256)
    return {
        "schema": integrity.PACKAGE_SCHEMA_VERSION,
        "legal_review_notice": integrity.legal_review_notice(),
        "generated_at": integrity.utc_now_iso(),
        "generated_by": {
            "user_id": principal.user_id,
            "role": principal.role,
            "department": principal.department,
        },
        "purpose": purpose,
        "case_id": case_id,
        "sighting": {
            "event_id": event.id,
            "identity_id": event.identity_id,
            "plate": event.plate,
            "plate_confidence": event.plate_confidence,
            "evidence_class": sighting_class,
            "evidence_class_reason": ec.describe(sighting_class, event.link_method),
            "link_method": event.link_method,
            "link_score": event.link_score,
            "link_time_gap_s": event.link_time_gap_s,
            # Source timestamp and ingest timestamp kept separate per
            # CLAUDE.md §24.9 — a reviewer must be able to tell when the
            # vehicle was seen from when the row landed.
            "observed_at": event.observed_at.isoformat() + "Z" if event.observed_at else None,
            "ingested_at": event.ingested_at.isoformat() + "Z" if event.ingested_at else None,
            "stream_pts_ms": event.pts_ms,
        },
        # Device identity for the §63 record. Attribute names are the real
        # CameraRegistry columns — `location_name`, not `name` (a wrong
        # name behind a getattr default would silently emit None forever,
        # which is exactly the kind of quietly-empty provenance field this
        # package must not ship; caught by test_evidence_integrity.py).
        "device": {
            "camera_id": event.camera_id,
            "location_name": camera.location_name if camera else None,
            "camera_type": camera.camera_type if camera else None,
            "vendor": camera.vendor if camera else None,
            "owning_department": camera.department if camera else None,
            "latitude": camera.latitude if camera else None,
            "longitude": camera.longitude if camera else None,
            "source_system": camera.source_system if camera else None,
        },
        "image": {
            "crop_path": event.crop_path,
            "bbox": {
                "x1": event.bbox_x1, "y1": event.bbox_y1,
                "x2": event.bbox_x2, "y2": event.bbox_y2,
            },
            "hashed_at_write_time": event.crop_hashed_at.isoformat() + "Z" if event.crop_hashed_at else None,
            "integrity": verification,
        },
        "production_method": integrity.parse_production_stamp(event.production_stamp),
        "access_and_export_audit_trail": _access_history(db, event.id),
        "declarations": {
            "part_a": {
                "description": (
                    "Part A — declaration by the person producing the "
                    "electronic record. To be completed and signed by the "
                    "authorised person."
                ),
                "name": None, "designation": None, "signed_at": None,
            },
            "part_b": {
                "description": (
                    "Part B — declaration by the person in charge of the "
                    "computer/device. To be completed and signed by the "
                    "authorised person."
                ),
                "name": None, "designation": None, "signed_at": None,
            },
        },
    }


@router.get("/event/{event_id}/verify")
def verify_event_evidence(
    event_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Recompute the stored image's hash and compare it to the write-time
    value. Not gated on evidence class — see this module's docstring."""
    event, _camera = _load_event_scoped(db, event_id, principal)
    result = integrity.verify_crop(event.crop_path, event.crop_sha256)
    return {
        "event_id": event.id,
        "evidence_class": ec.classify(event.plate, event.link_method),
        "hashed_at_write_time": event.crop_hashed_at.isoformat() + "Z" if event.crop_hashed_at else None,
        **result,
    }


@router.get("/event/{event_id}/package")
def evidence_package(
    event_id: int,
    purpose: str = Query(..., min_length=_PURPOSE_MIN_LENGTH),
    case_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """The §63-oriented provenance package for one CONFIRMED sighting."""
    event, camera = _load_event_scoped(db, event_id, principal)
    sighting_class = _evidence_gate(event)
    _log_export(db, principal, event, purpose, case_id, "package")
    return _build_package(db, event, camera, sighting_class, purpose, case_id, principal)


@router.get("/event/{event_id}/certificate.pdf")
def evidence_certificate_pdf(
    event_id: int,
    purpose: str = Query(..., min_length=_PURPOSE_MIN_LENGTH),
    case_id: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("investigator")),
):
    """Printable form of the same package — renders it, never recomputes
    it, so the PDF and the JSON cannot disagree about one artefact."""
    event, camera = _load_event_scoped(db, event_id, principal)
    sighting_class = _evidence_gate(event)
    _log_export(db, principal, event, purpose, case_id, "certificate.pdf")
    package = _build_package(db, event, camera, sighting_class, purpose, case_id, principal)
    pdf_bytes = _render_certificate_pdf(package)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=sentinel_evidence_event_{event.id}.pdf"
            )
        },
    )


def _kv_table(rows: list[list], col_widths=(170, 320)) -> Table:
    table = Table(rows, colWidths=list(col_widths))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1628")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _render_certificate_pdf(pkg: dict) -> bytes:
    """Same reportlab pattern as the gap-analysis and federation PDFs —
    no new dependency, and "render, don't recompute" as in those."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title=f"Sentinel Evidence Package — event {pkg['sighting']['event_id']}")
    styles = getSampleStyleSheet()
    integrity_block = pkg["image"]["integrity"]

    elements = [
        Paragraph("Sentinel — §63-Oriented Evidence Package", styles["Title"]),
        Paragraph(f"Generated {pkg['generated_at']} · schema {pkg['schema']}", styles["Normal"]),
        Spacer(1, 10),
        Paragraph(pkg["legal_review_notice"], styles["Italic"]),
        Spacer(1, 14),
    ]

    elements.append(Paragraph("1. Sighting", styles["Heading2"]))
    s = pkg["sighting"]
    elements.append(_kv_table([
        ["Field", "Value"],
        ["Event id", s["event_id"]],
        ["Registration number", s["plate"] or "(not read)"],
        ["Plate confidence", s["plate_confidence"]],
        ["Evidence class", s["evidence_class"]],
        ["Basis", Paragraph(s["evidence_class_reason"], styles["BodyText"])],
        ["Observed at (UTC)", s["observed_at"]],
        ["Ingested at (UTC)", s["ingested_at"]],
        ["Stream PTS (ms)", s["stream_pts_ms"]],
    ]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("2. Device of origin", styles["Heading2"]))
    d = pkg["device"]
    elements.append(_kv_table([
        ["Field", "Value"],
        ["Camera id", d["camera_id"]],
        ["Location name", d["location_name"]],
        ["Camera type", d["camera_type"]],
        ["Vendor", d["vendor"]],
        ["Owning department", d["owning_department"]],
        ["Latitude / Longitude", f"{d['latitude']} / {d['longitude']}"],
        ["Source system", d["source_system"]],
    ]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("3. Image integrity", styles["Heading2"]))
    elements.append(_kv_table([
        ["Field", "Value"],
        ["Stored image", pkg["image"]["crop_path"] or "(none)"],
        ["Hashed at write time (UTC)", pkg["image"]["hashed_at_write_time"] or "(not hashed)"],
        ["SHA-256 recorded at write", Paragraph(str(integrity_block["recorded_sha256"]), styles["BodyText"])],
        ["SHA-256 recomputed now", Paragraph(str(integrity_block["current_sha256"]), styles["BodyText"])],
        ["Status", integrity_block["status"]],
        ["Interpretation", Paragraph(integrity_block["reason"], styles["BodyText"])],
    ]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("4. Production method", styles["Heading2"]))
    method = pkg["production_method"]
    method_rows = [["Component", "Value"]] + (
        [[k, str(v)] for k, v in method.items()] or [["(none recorded)", ""]]
    )
    elements.append(_kv_table(method_rows))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("5. Access and export audit trail", styles["Heading2"]))
    trail = pkg["access_and_export_audit_trail"]
    trail_rows = [["At (UTC)", "User", "Purpose", "Case", "Action"]] + (
        [
            [
                r["at"], r["user_id"],
                Paragraph(str(r["purpose"]), styles["BodyText"]),
                r["case_id"] or "—",
                Paragraph(str(r["action"]), styles["BodyText"]),
            ]
            for r in trail
        ] or [["(no prior entries)", "", "", "", ""]]
    )
    trail_table = Table(trail_rows, colWidths=[95, 70, 110, 55, 160])
    trail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1628")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(trail_table)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("6. Declarations (to be completed by hand)", styles["Heading2"]))
    for key in ("part_a", "part_b"):
        block = pkg["declarations"][key]
        elements.append(Paragraph(block["description"], styles["BodyText"]))
        elements.append(Spacer(1, 6))
        elements.append(_kv_table([
            ["Field", "Entry"],
            ["Name", ""],
            ["Designation", ""],
            ["Signature", ""],
            ["Date", ""],
        ], col_widths=(170, 320)))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return buf.getvalue()
