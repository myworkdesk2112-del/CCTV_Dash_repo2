"""Regression coverage for api/session_auth.py — SEC-4's httpOnly-cookie
+ CSRF session auth, additive to auth.py's API-key header model.

Uses a real FastAPI TestClient/ASGI app (this test suite's other files
call route functions directly instead — this module needs the real
HTTP layer because the behavior under test IS the Set-Cookie/CSRF
header mechanics, which a direct function call can't exercise."""
from __future__ import annotations

import hashlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import session_auth
from app.api.auth import Principal, require_role
from app.api.deps import get_db
from app.db.models import ApiKeyEntry, Base


@pytest.fixture()
def session():
    """A dedicated StaticPool engine, not this suite's usual `conftest.py`
    fixture: TestClient's ASGI transport runs the app in a worker thread,
    and the default per-thread-connection pool for a `sqlite:///:memory:`
    engine hands that thread a brand-new, empty database — StaticPool
    keeps a single real connection shared across threads, matching how a
    real (file-based or Postgres) deployment behaves."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    engine.dispose()


def _make_app(session):
    app = FastAPI()
    app.include_router(session_auth.router)

    @app.get("/whoami")
    def whoami(principal: Principal = Depends(session_auth.get_principal_session)):
        return {"user_id": principal.user_id, "role": principal.role}

    @app.post("/mutate")
    def mutate(principal: Principal = Depends(session_auth.get_principal_session)):
        return {"ok": True}

    # A route using the REAL production dependency (auth.require_role /
    # auth.get_principal) — proves the merged header-key/session-cookie
    # fallback in auth.py itself, not just session_auth.py's own
    # dependency. Every real route in the app (routes_cameras.py etc.)
    # is built on exactly this dependency.
    @app.get("/real-protected-route")
    def real_protected_route(principal: Principal = Depends(require_role("viewer"))):
        return {"user_id": principal.user_id, "role": principal.role}

    @app.post("/real-protected-mutation")
    def real_protected_mutation(principal: Principal = Depends(require_role("admin"))):
        return {"ok": True}

    app.dependency_overrides[get_db] = lambda: session
    return app


def _seed_api_key(session, raw_key="real-key-123", role="investigator", department="Police"):
    session.add(
        ApiKeyEntry(
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            user_id="inv1",
            role=role,
            department=department,
        )
    )
    session.commit()
    return raw_key


def _https_client(session):
    """Both cookies are `secure=True` (correctly — never send a session
    over plain HTTP), so httpx's cookie jar drops them unless the test
    client actually addresses the app over https://. This is the real
    browser behavior, not a workaround for a bug."""
    return TestClient(_make_app(session), base_url="https://testserver")


def test_login_with_invalid_api_key_is_rejected(session):
    client = _https_client(session)
    resp = client.post("/auth/session/login", json={"api_key": "not-a-real-key"})
    assert resp.status_code == 401


def test_login_with_valid_api_key_sets_httponly_session_and_readable_csrf_cookie(session):
    raw_key = _seed_api_key(session)
    client = _https_client(session)
    resp = client.post("/auth/session/login", json={"api_key": raw_key})
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "inv1", "role": "investigator", "department": "Police"}

    session_cookie = next(c for c in client.cookies.jar if c.name == session_auth.SESSION_COOKIE_NAME)
    csrf_cookie = next(c for c in client.cookies.jar if c.name == session_auth.CSRF_COOKIE_NAME)
    assert session_cookie._rest.get("HttpOnly") is not None or session_cookie.has_nonstandard_attr("HttpOnly")
    # The CSRF cookie must NOT be httpOnly — the frontend needs to read it
    # to echo it back in the CSRF header (double-submit pattern).
    assert not (csrf_cookie._rest.get("HttpOnly") is not None or csrf_cookie.has_nonstandard_attr("HttpOnly"))


def test_get_request_does_not_require_csrf_header(session):
    raw_key = _seed_api_key(session)
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "inv1"


def test_mutating_request_without_csrf_header_is_rejected(session):
    raw_key = _seed_api_key(session)
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    resp = client.post("/mutate")
    assert resp.status_code == 403


def test_mutating_request_with_wrong_csrf_header_is_rejected(session):
    raw_key = _seed_api_key(session)
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    resp = client.post("/mutate", headers={"X-Sentinel-CSRF-Token": "wrong-token"})
    assert resp.status_code == 403


def test_mutating_request_with_correct_csrf_header_succeeds(session):
    raw_key = _seed_api_key(session)
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    csrf_cookie = next(c for c in client.cookies.jar if c.name == session_auth.CSRF_COOKIE_NAME)
    resp = client.post("/mutate", headers={"X-Sentinel-CSRF-Token": csrf_cookie.value})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_no_session_cookie_is_rejected(session):
    client = _https_client(session)
    resp = client.get("/whoami")
    assert resp.status_code == 401


def test_logout_clears_session_and_subsequent_request_is_rejected(session):
    raw_key = _seed_api_key(session)
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    assert client.get("/whoami").status_code == 200

    logout_resp = client.post("/auth/session/logout")
    assert logout_resp.status_code == 200
    assert client.get("/whoami").status_code == 401


def test_expired_session_is_rejected_and_purged(session):
    import datetime as dt

    from app.db.models import SessionToken

    raw_session = "expired-session-raw"
    session.add(
        SessionToken(
            session_hash=session_auth._hash_session(raw_session),
            csrf_token="whatever",
            user_id="inv1",
            role="investigator",
            department=None,
            expires_at=dt.datetime.utcnow() - dt.timedelta(hours=1),
        )
    )
    session.commit()

    client = _https_client(session)
    client.cookies.set(session_auth.SESSION_COOKIE_NAME, raw_session)
    resp = client.get("/whoami")
    assert resp.status_code == 401
    # Purged, not just rejected — confirms the expired-session cleanup path.
    assert session.query(SessionToken).count() == 0


def test_purge_expired_sessions_removes_only_expired_rows(session):
    import datetime as dt

    from app.db.models import SessionToken

    session.add(
        SessionToken(
            session_hash="expired-hash",
            csrf_token="x",
            user_id="u1",
            role="viewer",
            department=None,
            expires_at=dt.datetime.utcnow() - dt.timedelta(hours=1),
        )
    )
    session.add(
        SessionToken(
            session_hash="live-hash",
            csrf_token="y",
            user_id="u2",
            role="viewer",
            department=None,
            expires_at=dt.datetime.utcnow() + dt.timedelta(hours=1),
        )
    )
    session.commit()

    deleted = session_auth.purge_expired_sessions(session)
    assert deleted == 1
    remaining = session.query(SessionToken).all()
    assert len(remaining) == 1
    assert remaining[0].session_hash == "live-hash"


# --- Coverage for the merged fallback in auth.get_principal / auth.require_role
# (2026-09-18b) — every real route in the app depends on these, not on
# session_auth.get_principal_session directly. ---


def test_real_route_rejects_a_request_with_neither_header_nor_cookie(session):
    client = _https_client(session)
    resp = client.get("/real-protected-route")
    assert resp.status_code == 401


def test_real_route_still_accepts_the_header_key_unchanged(session):
    """The original, pre-existing auth path — confirms the SEC-4 addition
    didn't regress it."""
    raw_key = _seed_api_key(session, role="viewer")
    client = _https_client(session)
    resp = client.get("/real-protected-route", headers={"X-Sentinel-API-Key": raw_key})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "inv1"


def test_real_route_accepts_a_session_cookie_with_no_header_at_all(session):
    raw_key = _seed_api_key(session, role="viewer")
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    resp = client.get("/real-protected-route")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "inv1", "role": "viewer"}


def test_real_role_gate_still_enforced_over_a_session_cookie(session):
    """A viewer-role session must still fail an admin-only real route —
    proves require_role's rank-check runs identically regardless of
    which auth path supplied the Principal."""
    raw_key = _seed_api_key(session, role="viewer")
    client = _https_client(session)
    csrf_login = client.post("/auth/session/login", json={"api_key": raw_key})
    csrf_cookie = next(c for c in client.cookies.jar if c.name == session_auth.CSRF_COOKIE_NAME)
    resp = client.post("/real-protected-mutation", headers={"X-Sentinel-CSRF-Token": csrf_cookie.value})
    assert resp.status_code == 403


def test_real_mutating_route_over_session_cookie_still_needs_csrf(session):
    raw_key = _seed_api_key(session, role="admin")
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    resp = client.post("/real-protected-mutation")
    assert resp.status_code == 403


def test_real_mutating_route_over_session_cookie_succeeds_with_csrf(session):
    raw_key = _seed_api_key(session, role="admin")
    client = _https_client(session)
    client.post("/auth/session/login", json={"api_key": raw_key})
    csrf_cookie = next(c for c in client.cookies.jar if c.name == session_auth.CSRF_COOKIE_NAME)
    resp = client.post("/real-protected-mutation", headers={"X-Sentinel-CSRF-Token": csrf_cookie.value})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
