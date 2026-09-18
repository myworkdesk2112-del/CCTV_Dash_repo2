"""Minimal, real role-based access control.

Model 1's spec lists "department-wise RBAC" as a required deliverable, not
a bonus — this is not a stub in the "seam ready, weights not installed"
sense (see analytics/*.py). It's a genuine, working access-control layer:
every route below declares which role(s) it accepts, and a request without
a valid API key for that role is actually rejected with 401/403, not
logged-and-allowed.

Deliberately simple for a hackathon timeframe: a single header
(`X-Sentinel-API-Key`) maps to a role via a DB-backed key table, not a full
OAuth/session flow. That's an honest scope choice, not a hidden gap — see
STRATEGY.md's OUT list philosophy: build the real minimal thing, not a fake
elaborate one.

**2026-09-18 addition (`SEC-4`, `docs/PRODUCTION_MIGRATION_PLAN.md` Phase
4):** `get_principal` now also accepts `session_auth.py`'s httpOnly
session cookie + CSRF token as a fallback when no `X-Sentinel-API-Key`
header is present. Every existing route/test that uses the header key
is completely unaffected — the header path is checked first and
behaves identically. This is what lets the frontend migrate off
`localStorage` (see `frontend/src/api.js`) without every route needing
its own auth dependency.

Roles (least to most privileged):
  viewer       — read cameras/GIS/live view only
  investigator — + purpose-bound vehicle search, watchlist read, alerts
  admin        — + camera onboarding, watchlist writes, alert ack
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..db.models import ApiKeyEntry
from .deps import get_db

logger = logging.getLogger("sentinel.auth")

ROLE_RANK = {"viewer": 0, "investigator": 1, "admin": 2}


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class Principal:
    def __init__(self, user_id: str, role: str, department: Optional[str]):
        self.user_id = user_id
        self.role = role
        self.department = department


def get_principal(
    request: Request,
    x_sentinel_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Principal:
    if x_sentinel_api_key:
        entry = db.query(ApiKeyEntry).filter_by(key_hash=hash_key(x_sentinel_api_key)).first()
        if entry is None:
            raise HTTPException(401, "invalid API key")
        return Principal(entry.user_id, entry.role, entry.department)

    # No header key — fall back to the session-cookie path (SEC-4, see
    # this module's docstring). Local import: session_auth.py imports
    # Principal/hash_key from this module at load time, so a top-level
    # import here would be circular.
    from .session_auth import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, get_principal_session

    if not request.cookies.get(SESSION_COOKIE_NAME):
        raise HTTPException(401, "missing X-Sentinel-API-Key header or session cookie")
    return get_principal_session(
        request=request,
        db=db,
        sentinel_session=request.cookies.get(SESSION_COOKIE_NAME),
        x_sentinel_csrf_token=request.headers.get(CSRF_HEADER_NAME),
    )


def department_scope(principal: Principal) -> Optional[str]:
    """Model 1 explicitly lists 'department-wise RBAC' as required, not a
    bonus (see this module's docstring) — previously only role (viewer/
    investigator/admin) was enforced, not department. `admin` and any key
    with no department set (department=None, e.g. the bootstrap key) are
    unrestricted — `None` return means "no department filter", not "no
    access". A non-admin key WITH a department only sees that department's
    cameras (see routes_cameras.py's `_registered_cameras`).

    Deliberately scoped to the CAMERA REGISTRY (Model 1) only, not vehicle
    movement history (Model 2) — cross-camera correlation across
    departments is this project's core differentiator (STRATEGY.md), and
    restricting an investigator's plate search to their own department's
    cameras would defeat exactly the feature that makes cross-department
    vehicle tracking possible in the first place. Department-scoping the
    registry (which cameras you can see/manage) is the deliverable Model 1
    actually asks for; department-scoping investigative search results is a
    different, NOT requested, restriction this project deliberately does
    not add.
    """
    if principal.role == "admin":
        return None
    return principal.department


def require_role(minimum_role: str):
    """Usage: `principal: Principal = Depends(require_role("admin"))`.
    Roles are ranked (viewer < investigator < admin) so `require_role
    ("investigator")` also accepts admin — same convention as most RBAC
    systems, higher privilege satisfies a lower-privilege requirement."""

    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if ROLE_RANK.get(principal.role, -1) < ROLE_RANK[minimum_role]:
            raise HTTPException(403, f"role '{principal.role}' cannot access this endpoint (requires '{minimum_role}'+)")
        return principal

    return dependency


def ensure_default_admin_key(session: Session) -> None:
    """First-run bootstrap: if no API keys exist at all, mint one admin key
    and log it once so the demo isn't locked out of its own backend. Real
    keys after that are provisioned by an admin via POST /auth/api-keys."""
    if session.query(ApiKeyEntry).first() is not None:
        return
    raw_key = secrets.token_urlsafe(24)
    session.add(ApiKeyEntry(key_hash=hash_key(raw_key), user_id="bootstrap-admin", role="admin"))
    session.commit()
    # Deliberately NOT logger.warning(...): the logging framework is a
    # permanent record (any log aggregation/shipping keeps it forever),
    # but this key is only ever meant to be visible once, at mint time —
    # same one-shot-visibility intent as POST /auth/api-keys' response.
    # Bypass logging and write straight to the console. Found by security
    # review 2026-09-04.
    print(
        f"No API keys existed — minted a bootstrap admin key (SAVE THIS, shown only once): {raw_key}",
        flush=True,
    )
