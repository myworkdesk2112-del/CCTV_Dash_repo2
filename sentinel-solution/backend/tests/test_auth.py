"""Regression coverage for routes_auth.py's create_api_key role validation.
Confirmed 2026-09-10 (P1 re-research pass) that an invalid role returned
HTTP 200 with an {"error": ...} body instead of a proper 400 — this locks
in the fix."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.auth import Principal
from app.api.routes_auth import ApiKeyCreate, create_api_key


def test_invalid_role_raises_400(session):
    admin = Principal("admin1", "admin", None)
    body = ApiKeyCreate(user_id="u1", role="superuser")
    with pytest.raises(HTTPException) as exc_info:
        create_api_key(body, session, admin)
    assert exc_info.value.status_code == 400


def test_valid_role_creates_key(session):
    admin = Principal("admin1", "admin", None)
    body = ApiKeyCreate(user_id="u1", role="investigator", department="Police")
    result = create_api_key(body, session, admin)
    assert result["role"] == "investigator"
    assert result["user_id"] == "u1"
    assert "api_key" in result
