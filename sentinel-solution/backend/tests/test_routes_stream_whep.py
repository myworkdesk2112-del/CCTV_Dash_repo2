"""WHEP signaling proxy (2026-09-18) — see routes_stream.py's whep_offer/
whep_teardown docstrings for the design rationale (credentials embedded in
the upstream URL, never forwarded to the browser; only signaling proxied,
not ongoing media, so this adds no per-frame relay load).

No live WHEP-producing origin is reachable here to test against for real,
so this mocks `requests.post`/`requests.delete` and `catalogue.get` to
simulate an upstream media server. AUTOMATED-TEST VERIFIED, not LIVE/REAL
VERIFIED.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import Principal
from app.api.routes_stream import whep_offer, whep_teardown


def _fake_camera(whep_url="http://user%40example.com:secret@103.250.160.189:8889/stream/cam01/whep"):
    return SimpleNamespace(id="cam01", whep_url=whep_url)


def _fake_request(body: bytes = b"v=0\r\n...offer...\r\n"):
    request = MagicMock()

    async def _body():
        return body

    request.body = _body
    return request


def test_whep_offer_forwards_sdp_and_rewrites_location(session):
    viewer = Principal("viewer1", "viewer", None)
    upstream_resp = SimpleNamespace(
        status_code=201,
        content=b"v=0\r\n...answer...\r\n",
        headers={"Location": "/stream/cam01/whep/abc123"},
    )

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests:
        mock_catalogue.get.return_value = _fake_camera()
        mock_requests.post.return_value = upstream_resp

        result = asyncio.run(
            whep_offer("cam01", _fake_request(), db=session, principal=viewer)
        )

    post_args, post_kwargs = mock_requests.post.call_args
    assert post_args[0] == _fake_camera().whep_url
    assert post_kwargs["data"] == b"v=0\r\n...offer...\r\n"
    assert post_kwargs["headers"] == {"Content-Type": "application/sdp"}

    assert result.status_code == 201
    assert result.body == b"v=0\r\n...answer...\r\n"
    assert result.headers["location"] == (
        "/live/cam01/whep/session?"
        "u=http%3A%2F%2F103.250.160.189%3A8889%2Fstream%2Fcam01%2Fwhep%2Fabc123"
    )
    # The rewritten Location must never contain the upstream credential.
    assert "secret" not in result.headers["location"]


def test_whep_offer_502s_on_upstream_failure(session):
    viewer = Principal("viewer1", "viewer", None)

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests:
        mock_catalogue.get.return_value = _fake_camera()
        mock_requests.post.side_effect = ConnectionError("refused")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(whep_offer("cam01", _fake_request(), db=session, principal=viewer))

    assert exc_info.value.status_code == 502


def test_whep_offer_failure_never_leaks_credentials_to_the_client(session, caplog):
    """The embedded email:password credential must never reach an HTTP
    response body or a log line, even when the underlying exception's own
    message happens to embed the full credentialed URL (confirmed real
    behavior for e.g. requests' HTTPError — see routes_stream.py's
    _sanitize_upstream_error docstring)."""
    viewer = Principal("viewer1", "viewer", None)
    cam = _fake_camera()

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests:
        mock_catalogue.get.return_value = cam
        mock_requests.post.side_effect = Exception(f"502 Server Error: None for url: {cam.whep_url}")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(whep_offer("cam01", _fake_request(), db=session, principal=viewer))

    assert "secret" not in exc_info.value.detail
    assert "user%40example.com" not in exc_info.value.detail
    assert "secret" not in caplog.text


def test_whep_offer_404_for_unknown_camera(session):
    viewer = Principal("viewer1", "viewer", None)

    with patch("app.api.routes_stream.catalogue") as mock_catalogue:
        mock_catalogue.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(whep_offer("cam99", _fake_request(), db=session, principal=viewer))

    assert exc_info.value.status_code == 404


def test_whep_teardown_forwards_delete_with_reattached_auth(session):
    viewer = Principal("viewer1", "viewer", None)
    session_url = "http://103.250.160.189:8889/stream/cam01/whep/abc123"

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests, \
            patch("app.api.routes_stream.with_stream_auth") as mock_with_auth:
        mock_catalogue.get.return_value = _fake_camera()
        mock_with_auth.return_value = "http://user%40example.com:secret@103.250.160.189:8889/stream/cam01/whep/abc123"
        mock_requests.delete.return_value = SimpleNamespace(status_code=200)

        result = whep_teardown("cam01", u=session_url, db=session, principal=viewer)

    mock_with_auth.assert_called_once_with(session_url)
    mock_requests.delete.assert_called_once()
    assert mock_requests.delete.call_args[0][0] == mock_with_auth.return_value
    assert result.status_code == 200


def test_whep_teardown_rejects_mismatched_host(session):
    """`u` is client-supplied and round-trips through the browser — fetching
    it without a host check would be an open SSRF proxy using the sandbox's
    embedded WHEP credentials (same class of bug hls_segment already guards
    against for the HLS proxy)."""
    viewer = Principal("viewer1", "viewer", None)

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests:
        mock_catalogue.get.return_value = _fake_camera()

        with pytest.raises(HTTPException) as exc_info:
            whep_teardown(
                "cam01", u="http://attacker.example/steal", db=session, principal=viewer
            )

    assert exc_info.value.status_code == 400
    mock_requests.delete.assert_not_called()


def test_whep_teardown_failure_never_leaks_credentials_to_logs(session, caplog):
    viewer = Principal("viewer1", "viewer", None)
    session_url = "http://103.250.160.189:8889/stream/cam01/whep/abc123"
    authed_url = "http://user%40example.com:secret@103.250.160.189:8889/stream/cam01/whep/abc123"

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests, \
            patch("app.api.routes_stream.with_stream_auth") as mock_with_auth:
        mock_catalogue.get.return_value = _fake_camera()
        mock_with_auth.return_value = authed_url
        mock_requests.delete.side_effect = Exception(f"502 Server Error: None for url: {authed_url}")

        result = whep_teardown("cam01", u=session_url, db=session, principal=viewer)

    assert result.status_code == 204
    assert "secret" not in caplog.text


def test_whep_teardown_degrades_quietly_on_upstream_failure(session):
    """Best-effort teardown: the browser is already done with the session,
    so an upstream hiccup here must not surface as a client-visible error —
    the media server's own idle timeout is the real backstop."""
    viewer = Principal("viewer1", "viewer", None)
    session_url = "http://103.250.160.189:8889/stream/cam01/whep/abc123"

    with patch("app.api.routes_stream.catalogue") as mock_catalogue, \
            patch("app.api.routes_stream.requests") as mock_requests:
        mock_catalogue.get.return_value = _fake_camera()
        mock_requests.delete.side_effect = ConnectionError("refused")

        result = whep_teardown("cam01", u=session_url, db=session, principal=viewer)

    assert result.status_code == 204
