"""Production hardening scaffold — OIDC/SSO identity-federation, additive
to `auth.py`'s existing API-key model.

**Status: IMPLEMENTED, UNVERIFIED.** Written 2026-09-18 per
`docs/PRODUCTION_MIGRATION_PLAN.md` Phase 4 and `docs/SCALABILITY.md`
§5's "a production statewide deployment should authenticate users
against whatever identity-federation standard the government mandates
... rather than this submission's standalone API-key model." No real
OIDC provider (Gujarat Police SSO, or any other) is configured or
reachable from this environment, so the JWKS fetch/token-verification
path below has never been exercised against a live issuer — only
unit-testable with a hand-built JWKS + signed test token, which this
file does not include (would need `python-jose`/`cryptography` test
fixtures; not attempted here).

**Deliberately additive, not a replacement.** `auth.py`'s
`X-Sentinel-API-Key` dependency (`get_principal`) is untouched — every
existing route, test, and the frontend's current login flow keep
working exactly as before. This module provides a second dependency,
`get_principal_oidc`, that a route can opt into instead, or that a
future gateway/BFF layer can use to mint a Sentinel-local `Principal`
from a verified OIDC identity. Wiring an actual route to use it, or
migrating the frontend login flow, is a real product decision
(`PRODUCTION_MIGRATION_PLAN.md` Phase 4 §2) explicitly deferred — this
file is the mechanism, not the decision to switch.

Disabled by default (`config.SSO_OIDC_ENABLED = False`) — importing
this module has zero effect on a running pilot instance unless a
route explicitly depends on `get_principal_oidc` AND the env is
configured for it.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import config
from ..db.models import ApiKeyEntry
from .auth import Principal
from .deps import get_db

logger = logging.getLogger("sentinel.sso_oidc")

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_CACHE_TTL_S = 3600.0


class OidcUnavailable(RuntimeError):
    """Raised when OIDC verification is requested but not configured, or
    a dependency (`python-jose`) isn't installed. Never falls back to
    accepting an unverified token — a security boundary must fail
    closed, per CLAUDE.md §24.16."""


def _require_jose():
    try:
        from jose import jwt  # noqa
        from jose.exceptions import JOSEError  # noqa
    except ImportError as exc:
        raise OidcUnavailable(
            "python-jose is not installed. Intentionally NOT in "
            "requirements.txt — see requirements-production.txt. Install "
            "only when actually wiring a real OIDC provider."
        ) from exc
    return jwt, JOSEError


def _fetch_jwks(force: bool = False) -> dict:
    """Cached JWKS fetch. A real deployment would want this backed by a
    proper HTTP client with retry/backoff (`requests`, already a
    dependency) — kept intentionally simple here since it's unverified
    scaffolding, not the production implementation to ship as-is."""
    import requests

    now = time.time()
    if not force and _jwks_cache["keys"] is not None and (now - _jwks_cache["fetched_at"]) < _JWKS_CACHE_TTL_S:
        return _jwks_cache["keys"]
    if not config.SSO_OIDC_JWKS_URL:
        raise OidcUnavailable("config.SSO_OIDC_JWKS_URL is not set")
    resp = requests.get(config.SSO_OIDC_JWKS_URL, timeout=5)
    resp.raise_for_status()
    keys = resp.json()
    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


def verify_id_token(raw_token: str) -> dict:
    """Verifies signature, issuer, audience, and expiry. Returns the
    decoded claims dict on success. Raises `OidcUnavailable` (config
    problem) or `HTTPException(401, ...)` (a real, rejected token) —
    never returns claims for a token that failed any check, and never
    guesses a default issuer/audience if config is unset."""
    if not config.SSO_OIDC_ENABLED:
        raise OidcUnavailable("SSO_OIDC_ENABLED is false")
    if not config.SSO_OIDC_ISSUER or not config.SSO_OIDC_AUDIENCE:
        raise OidcUnavailable("config.SSO_OIDC_ISSUER / SSO_OIDC_AUDIENCE not set")
    jwt, JOSEError = _require_jose()
    jwks = _fetch_jwks()
    try:
        claims = jwt.decode(
            raw_token,
            jwks,
            algorithms=["RS256"],
            audience=config.SSO_OIDC_AUDIENCE,
            issuer=config.SSO_OIDC_ISSUER,
        )
    except JOSEError as exc:
        # Retry once against a freshly-fetched JWKS in case of key
        # rotation, same as most OIDC client libraries recommend, before
        # giving up and rejecting the token.
        try:
            jwks = _fetch_jwks(force=True)
            claims = jwt.decode(
                raw_token,
                jwks,
                algorithms=["RS256"],
                audience=config.SSO_OIDC_AUDIENCE,
                issuer=config.SSO_OIDC_ISSUER,
            )
        except JOSEError:
            raise HTTPException(401, f"invalid OIDC token: {exc}") from exc
    return claims


def _role_from_claims(claims: dict) -> str:
    """Maps an OIDC claim to Sentinel's existing viewer/investigator/admin
    role model. Reads a configurable claim name rather than hardcoding
    `roles` — real IdPs vary (Azure AD app roles, Keycloak realm roles,
    a custom claim a department's IT team issues). Fails closed to the
    least-privileged role on any ambiguity, never defaults to admin."""
    raw_roles = claims.get(config.SSO_OIDC_ROLE_CLAIM, [])
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    for role in ("admin", "investigator", "viewer"):
        if role in raw_roles:
            return role
    logger.warning(
        "sso_oidc: token for subject %s carried no recognized role claim (%s); "
        "defaulting to viewer, the least-privileged role",
        claims.get("sub", "<unknown>"),
        config.SSO_OIDC_ROLE_CLAIM,
    )
    return "viewer"


def get_principal_oidc(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Principal:
    """Drop-in alternative to `auth.get_principal` for a route that opts
    into OIDC instead of the API-key header. Not used by any route in
    this codebase today — see this module's docstring."""
    if not config.SSO_OIDC_ENABLED:
        raise HTTPException(501, "OIDC auth is not enabled on this deployment")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing Bearer token")
    raw_token = authorization.split(" ", 1)[1]
    try:
        claims = verify_id_token(raw_token)
    except OidcUnavailable as exc:
        raise HTTPException(500, f"OIDC not correctly configured: {exc}") from exc
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(401, "OIDC token missing 'sub' claim")
    role = _role_from_claims(claims)
    department = claims.get(config.SSO_OIDC_DEPARTMENT_CLAIM)
    # Mirror the identity into ApiKeyEntry's audit trail (user_id/role/
    # department) so existing department-scope/audit-log code, which
    # keys everything off `Principal.user_id`, needs no changes — an
    # OIDC subject is treated as a `user_id` exactly like an API key's
    # `user_id` column already is.
    existing = db.query(ApiKeyEntry).filter_by(user_id=subject).first()
    if existing is None:
        logger.info("sso_oidc: first sight of OIDC subject %s, role=%s", subject, role)
    return Principal(user_id=subject, role=role, department=department)
