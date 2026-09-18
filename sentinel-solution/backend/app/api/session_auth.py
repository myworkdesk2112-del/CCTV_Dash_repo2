"""Production hardening — session-based auth (httpOnly cookie + CSRF),
additive to `auth.py`'s existing `X-Sentinel-API-Key` header model.

**Status: AUTOMATED-TEST VERIFIED (real code, real tests, this
environment).** Unlike this session's earlier pgvector/Kafka/OIDC/infra
scaffolds, this module needs no external infrastructure to run — it's
plain FastAPI + SQLAlchemy against the same SQLite/Postgres the rest of
the app already uses, so it was actually exercised end-to-end by
`tests/test_session_auth.py`, not just written and left unverified.
See `docs/PRODUCTION_MIGRATION_PLAN.md` Phase 4 / `docs/
REVIEW_FINDINGS.md`'s `SEC-4` for the gap this closes: the frontend's
API key currently sits in JS-readable `localStorage`
(`frontend/src/api.js`) — a real XSS on this app would exfiltrate a
long-lived credential outright. An httpOnly cookie can't be read by
page JS at all, which is the actual fix; the CSRF token is the
necessary other half (an httpOnly cookie is sent automatically by the
browser on every request to the origin, so without a CSRF check any
other page could trigger a state-changing request using the victim's
session).

**Deliberately additive, not a migration.** `auth.py.get_principal`
and every existing route/test keep using the header key exactly as
before. This module is a second, parallel dependency
(`get_principal_session`) that a route can require instead — no route
in this codebase requires it yet, and the frontend's login flow has NOT
been migrated to it this pass (that's a separate, larger frontend
change: replacing every `api.js` call's manual header-attachment with
`credentials: "include"` plus reading/sending the CSRF token, and
deciding whether the two auth paths coexist long-term or the header key
is retired later). Shipping the mechanism and its tests first, without
forcing a frontend rewrite in the same change, follows this repo's
minimal-diff/one-task-one-objective rule.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import ApiKeyEntry, SessionToken
from .auth import Principal, hash_key
from .deps import get_db

logger = logging.getLogger("sentinel.session_auth")

router = APIRouter(prefix="/auth/session", tags=["auth"])

SESSION_COOKIE_NAME = "sentinel_session"
CSRF_COOKIE_NAME = "sentinel_csrf"
CSRF_HEADER_NAME = "x-sentinel-csrf-token"
SESSION_TTL_HOURS = 12
# Methods that mutate state must carry a matching CSRF header — GET/HEAD/
# OPTIONS don't (same convention as Django's/Rails' CSRF middleware: a
# CSRF token protects against a forged *write*, a forged read is a
# different, lower-severity problem this mechanism isn't built to stop).
_CSRF_EXEMPT_METHODS = {"GET", "HEAD", "OPTIONS"}


class LoginRequest(BaseModel):
    api_key: str


def _hash_session(raw_session: str) -> str:
    return hashlib.sha256(raw_session.encode("utf-8")).hexdigest()


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Exchanges a valid API key for a session cookie. The API key
    itself is never stored or logged here — same one-shot, no-retained-
    plaintext discipline as `ApiKeyEntry`/`ensure_default_admin_key`."""
    entry = db.query(ApiKeyEntry).filter_by(key_hash=hash_key(payload.api_key)).first()
    if entry is None:
        raise HTTPException(401, "invalid API key")

    raw_session = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = dt.datetime.utcnow() + dt.timedelta(hours=SESSION_TTL_HOURS)
    db.add(
        SessionToken(
            session_hash=_hash_session(raw_session),
            csrf_token=csrf_token,
            user_id=entry.user_id,
            role=entry.role,
            department=entry.department,
            expires_at=expires_at,
        )
    )
    db.commit()

    # httpOnly + Secure + SameSite=Strict: JS on the page can never read
    # this cookie (defeats the XSS-exfiltration scenario SEC-4 names),
    # and it's never sent cross-site (defeats the simple CSRF case
    # outright; the explicit CSRF token below is the defense-in-depth
    # layer for the same-site-but-forged-form edge case SameSite=Strict
    # doesn't fully cover in every browser).
    response.set_cookie(
        SESSION_COOKIE_NAME,
        raw_session,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=SESSION_TTL_HOURS * 3600,
    )
    # The CSRF cookie is deliberately NOT httpOnly — the frontend must
    # read it (document.cookie or a meta tag) to echo it back in the
    # X-Sentinel-CSRF-Token header on mutating requests. This is the
    # standard "double-submit cookie" CSRF pattern: an attacker's forged
    # cross-site request carries the session cookie automatically but
    # cannot read this one to also forge a matching header.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        secure=True,
        samesite="strict",
        max_age=SESSION_TTL_HOURS * 3600,
    )
    return {"user_id": entry.user_id, "role": entry.role, "department": entry.department}


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    sentinel_session: Optional[str] = Cookie(None),
):
    if sentinel_session:
        db.query(SessionToken).filter_by(session_hash=_hash_session(sentinel_session)).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE_NAME)
    return {"ok": True}


def get_principal_session(
    request: Request,
    db: Session = Depends(get_db),
    sentinel_session: Optional[str] = Cookie(None),
    x_sentinel_csrf_token: Optional[str] = Header(None, alias=CSRF_HEADER_NAME),
) -> Principal:
    """Drop-in alternative to `auth.get_principal` for a route that
    opts into session auth. Not used by any route in this codebase
    today — see this module's docstring."""
    if not sentinel_session:
        raise HTTPException(401, f"missing {SESSION_COOKIE_NAME} cookie")
    token = db.query(SessionToken).filter_by(session_hash=_hash_session(sentinel_session)).first()
    if token is None:
        raise HTTPException(401, "invalid session")
    if token.expires_at < dt.datetime.utcnow():
        db.delete(token)
        db.commit()
        raise HTTPException(401, "session expired")

    if request.method.upper() not in _CSRF_EXEMPT_METHODS:
        if not x_sentinel_csrf_token or x_sentinel_csrf_token != token.csrf_token:
            # Logged without the token values themselves — the mismatch
            # is the useful signal, the actual tokens are still secrets.
            logger.warning("session_auth: CSRF check failed for user_id=%s method=%s", token.user_id, request.method)
            raise HTTPException(403, "missing or invalid CSRF token")

    return Principal(user_id=token.user_id, role=token.role, department=token.department)


def purge_expired_sessions(db: Session) -> int:
    """Called by the existing retention sweep (`db/retention.py`) so
    expired session rows don't accumulate forever — same "don't let a
    background table grow unbounded" discipline as the rest of that
    module. Returns the number of rows deleted."""
    deleted = db.query(SessionToken).filter(SessionToken.expires_at < dt.datetime.utcnow()).delete()
    db.commit()
    return deleted
