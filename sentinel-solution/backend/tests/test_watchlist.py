"""Regression coverage for watchlist/service.py:

1. `add()` upserts — a second `POST /watchlist` for an already-listed
   plate updates the reason instead of raising an IntegrityError.
2. `raise_alert_if_matched()`'s dedup only clears once an alert is
   RESOLVED or DISMISSED, not merely ACKNOWLEDGED — acknowledging doesn't
   let the next track chunk of a still-present vehicle raise a duplicate.
"""
from __future__ import annotations

from app.api.auth import Principal
from app.api.routes_alerts import _apply_status
from app.db.models import (
    ALERT_STATUS_DISMISSED,
    ALERT_STATUS_NEW,
    ALERT_STATUS_RESOLVED,
    Alert,
    CameraRegistry,
    VehicleEvent,
    VehicleIdentity,
)
from app.analytics import evidence_class as evclass
from app.analytics.anpr import _best_pattern_match
from app.watchlist.service import WatchlistService


def _seed_event(session, *, identity_plate=None, event_plate=None, link_method=None):
    camera = session.get(CameraRegistry, "cam01")
    if camera is None:
        camera = CameraRegistry(id="cam01")
        session.add(camera)
        session.commit()
    identity = VehicleIdentity(plate=identity_plate)
    session.add(identity)
    session.commit()
    event = VehicleEvent(
        identity_id=identity.id,
        camera_id=camera.id,
        pts_ms=0.0,
        plate=event_plate,
        link_method=link_method,
    )
    session.add(event)
    session.commit()
    return event


def _raise_like_pipeline(session, service, event, camera_id="cam01"):
    """Mirrors the exact gating pipeline.py performs before calling
    raise_alert_if_matched — kept in sync deliberately so a regression in
    the real gate (e.g. reverting to `identity.plate`) fails this test."""
    sighting_class = evclass.classify(event.plate, event.link_method)
    if sighting_class != evclass.CONFIRMED:
        return None
    return service.raise_alert_if_matched(
        session,
        event.plate,
        camera_id,
        event.id,
        evidence_class=sighting_class,
        evidence_class_reason=evclass.describe(sighting_class, event.link_method),
    )


def test_lead_only_appearance_match_never_raises_alert_even_if_identity_has_plate(session):
    """The real bug found in the live database: identity.plate was set by
    an earlier CONFIRMED sighting on another camera. A later LEAD_ONLY
    appearance-match sighting on a DIFFERENT camera (this event's own
    plate is None) must never raise a plate-matched watchlist alert."""
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")

    event = _seed_event(
        session,
        identity_plate="GJ01AB1234",  # set by a prior, different sighting
        event_plate=None,             # THIS sighting never read a plate
        link_method="appearance_match",
    )

    alert = _raise_like_pipeline(session, service, event)

    assert alert is None
    assert session.query(Alert).count() == 0


def test_confirmed_sighting_raises_alert_with_evidence_class_persisted(session):
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")

    event = _seed_event(session, identity_plate="GJ01AB1234", event_plate="GJ01AB1234", link_method=None)

    alert = _raise_like_pipeline(session, service, event)

    assert alert is not None
    assert alert.evidence_class == evclass.CONFIRMED
    assert alert.evidence_class_reason


def test_add_upserts_reason_instead_of_raising_on_duplicate_plate(session):
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")
    service.add(session, "GJ01AB1234", "wanted_person_vehicle")  # must not raise

    from app.db.models import WatchlistEntry

    rows = session.query(WatchlistEntry).filter_by(plate="GJ01AB1234").all()
    assert len(rows) == 1
    assert rows[0].reason == "wanted_person_vehicle"
    assert service.check("GJ01AB1234") == "wanted_person_vehicle"


def test_add_is_case_and_format_normalized_for_upsert(session):
    service = WatchlistService()
    service.add(session, "gj01 ab1234", "stolen")
    service.add(session, "GJ01AB1234", "updated_reason")

    from app.db.models import WatchlistEntry

    assert session.query(WatchlistEntry).count() == 1
    assert service.check("GJ01AB1234") == "updated_reason"


def test_second_sighting_while_alert_still_new_does_not_duplicate(session):
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")
    event1 = _seed_event(session)
    event2 = _seed_event(session)

    first = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event1.id)
    second = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event2.id)

    assert first is not None
    assert second is None
    assert session.query(Alert).count() == 1


def test_lingering_vehicle_does_not_duplicate_alert_right_after_acknowledge(session):
    """The actual bug: acknowledging an alert ("I've seen this") must not
    immediately reopen the dedup window for the SAME ongoing sighting —
    only resolving/dismissing the case should."""
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")
    event1 = _seed_event(session)
    event2 = _seed_event(session)

    alert = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event1.id)
    assert alert.status == ALERT_STATUS_NEW

    investigator = Principal("inv1", "investigator", None)
    from app.db.models import ALERT_STATUS_ACKNOWLEDGED

    _apply_status(alert, ALERT_STATUS_ACKNOWLEDGED, investigator)
    session.commit()

    duplicate = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event2.id)

    assert duplicate is None  # the fix: still suppressed, not a new "new" alert
    assert session.query(Alert).count() == 1


def test_new_alert_allowed_after_resolving_the_previous_one(session):
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")
    event1 = _seed_event(session)
    event2 = _seed_event(session)

    alert = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event1.id)
    investigator = Principal("inv1", "investigator", None)
    from app.db.models import ALERT_STATUS_ACKNOWLEDGED

    _apply_status(alert, ALERT_STATUS_ACKNOWLEDGED, investigator)
    _apply_status(alert, ALERT_STATUS_RESOLVED, investigator)
    session.commit()

    second = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event2.id)

    assert second is not None  # a genuinely new visit after resolution
    assert session.query(Alert).count() == 2


def test_new_alert_allowed_after_dismissing_as_false_positive(session):
    service = WatchlistService()
    service.add(session, "GJ01AB1234", "stolen")
    event1 = _seed_event(session)
    event2 = _seed_event(session)

    alert = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event1.id)
    investigator = Principal("inv1", "investigator", None)
    _apply_status(alert, ALERT_STATUS_DISMISSED, investigator)
    session.commit()

    second = service.raise_alert_if_matched(session, "GJ01AB1234", "cam01", event2.id)

    assert second is not None
    assert session.query(Alert).count() == 2


def test_bh_series_plate_completes_the_whole_watchlist_chain(session):
    """End-to-end proof for the 2026-09-19 BH-series fix.

    Before the fix this chain was broken in a way that produced no error
    anywhere: `add()` and the search paths only call `normalize_plate`, which
    does no format validation, so a BH plate could be watchlisted and searched
    for quite happily. What could never happen was a BH plate reaching the
    database in the first place — `PLATE_PATTERN` rejected every OCR read of
    one — so the alert could never fire and the watchlist entry sat there
    looking correct and matching nothing.

    This asserts the read gate, the evidence class and the alert together,
    because the defect was only visible when all three were considered at
    once. See RESEARCH_ANPR_DEEP_2026-09-19.md §A1.
    """
    bh_plate = "23BH1234AA"

    # 1. The OCR gate now admits it — this is the step that used to fail.
    assert _best_pattern_match(bh_plate) == bh_plate

    # 2. A sighting carrying it is CONFIRMED, exactly like a state plate.
    event = _seed_event(session, identity_plate=bh_plate, event_plate=bh_plate)
    assert evclass.classify(event.plate, event.link_method) == evclass.CONFIRMED

    # 3. The alert fires through the real pipeline gating.
    service = WatchlistService()
    service.add(session, bh_plate, "stolen vehicle")
    alert = _raise_like_pipeline(session, service, event)

    assert alert is not None
    assert alert.plate == bh_plate
    assert alert.evidence_class == evclass.CONFIRMED
