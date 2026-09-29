"""Regression coverage for Model 1 production-hardening pass, 2026-09-27:
real input validation on CameraOnboard that was previously entirely
absent — an empty/blank id, an out-of-range lat/lon, a negative coverage
radius, a >=360 direction, or a future install_date all used to onboard
successfully and corrupt the GIS/gap-analysis views silently. Pure
pydantic-validation tests (ValidationError), no DB/session needed for
most of these — the model raises before a route ever sees the request.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.auth import Principal
from app.api.routes_cameras import MAX_BULK_ONBOARD_SIZE, CameraOnboard, onboard_cameras_bulk


def test_blank_id_is_rejected():
    with pytest.raises(ValidationError):
        CameraOnboard(id="")


def test_whitespace_only_id_is_rejected():
    """Field(min_length=1) alone would let this through — it counts
    characters, not non-whitespace content."""
    with pytest.raises(ValidationError):
        CameraOnboard(id="   ")


def test_id_is_stripped():
    body = CameraOnboard(id="  cam01  ")
    assert body.id == "cam01"


@pytest.mark.parametrize("lat", [90.1, -90.1, 999.0])
def test_out_of_range_latitude_is_rejected(lat):
    with pytest.raises(ValidationError):
        CameraOnboard(id="cam01", latitude=lat)


@pytest.mark.parametrize("lon", [180.1, -180.1, 500.0])
def test_out_of_range_longitude_is_rejected(lon):
    with pytest.raises(ValidationError):
        CameraOnboard(id="cam01", longitude=lon)


def test_boundary_lat_lon_are_accepted():
    body = CameraOnboard(id="cam01", latitude=90.0, longitude=-180.0)
    assert body.latitude == 90.0 and body.longitude == -180.0


def test_negative_coverage_radius_is_rejected():
    with pytest.raises(ValidationError):
        CameraOnboard(id="cam01", coverage_radius_m=-50.0)


def test_zero_coverage_radius_is_accepted():
    """Zero is a legitimate 'no meaningful coverage claimed' value, distinct
    from a nonsensical negative one."""
    body = CameraOnboard(id="cam01", coverage_radius_m=0.0)
    assert body.coverage_radius_m == 0.0


@pytest.mark.parametrize("deg", [360.0, 400.0, -1.0])
def test_out_of_range_direction_is_rejected(deg):
    with pytest.raises(ValidationError):
        CameraOnboard(id="cam01", expected_direction_deg=deg)


def test_future_install_date_is_rejected():
    with pytest.raises(ValidationError):
        CameraOnboard(id="cam01", install_date=dt.datetime.utcnow() + dt.timedelta(days=1))


def test_past_install_date_is_accepted():
    body = CameraOnboard(id="cam01", install_date=dt.datetime(2018, 1, 1))
    assert body.install_date == dt.datetime(2018, 1, 1)


def test_bulk_onboard_rejects_an_oversized_payload(session):
    admin = Principal("admin1", "admin", None)
    # Constructing MAX_BULK_ONBOARD_SIZE + 1 real (valid) bodies would work
    # but is slow and unnecessary — the route checks len() before touching
    # any body's fields, so a list of cheap placeholders proves the same
    # guard without paying for real validation on each one.
    oversized = [CameraOnboard(id=f"cam{i}") for i in range(MAX_BULK_ONBOARD_SIZE + 1)]
    with pytest.raises(HTTPException) as exc_info:
        onboard_cameras_bulk(oversized, session, admin)
    assert exc_info.value.status_code == 400
