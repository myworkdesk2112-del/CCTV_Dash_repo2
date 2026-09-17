"""LL-HLS proxy transparency for routes_stream.py's hls_playlist (2026-09-17).

No live LL-HLS-producing origin is reachable to test against for real, so
this mocks catalogue.authenticated_get/get to simulate an upstream CDN
serving LL-HLS tags, and verifies the proxy rewrites/forwards correctly.
AUTOMATED-TEST VERIFIED, not LIVE/REAL VERIFIED — see RESEARCH.md.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.api.auth import Principal
from app.api.routes_stream import hls_playlist


def _fake_camera(hls_url="https://cdn.example/hls/cam01/index.m3u8"):
    return SimpleNamespace(id="cam01", hls_url=hls_url)


def test_playlist_rewrites_uri_on_every_tag_not_just_ext_x_key(session):
    playlist = (
        "#EXTM3U\n"
        '#EXT-X-MAP:URI="init.mp4"\n'
        '#EXT-X-KEY:METHOD=AES-128,URI="enc.key"\n'
        "#EXT-X-PART:DURATION=0.5,URI=\"part1.m4s\"\n"
        "#EXT-X-PRELOAD-HINT:TYPE=PART,URI=\"part2.m4s\"\n"
        "seg1.ts\n"
    )
    fake_resp = SimpleNamespace(text=playlist)
    admin = Principal("viewer1", "viewer", None)

    with patch("app.api.routes_stream.catalogue") as mock_catalogue:
        mock_catalogue.get.return_value = _fake_camera()
        mock_catalogue.authenticated_get.return_value = fake_resp
        result = hls_playlist("cam01", db=session, principal=admin)

    body = result.body.decode()
    assert 'URI="/live/cam01/seg?u=https://cdn.example/hls/cam01/init.mp4"' in body
    assert 'URI="/live/cam01/seg?u=https://cdn.example/hls/cam01/enc.key"' in body
    assert 'URI="/live/cam01/seg?u=https://cdn.example/hls/cam01/part1.m4s"' in body
    assert 'URI="/live/cam01/seg?u=https://cdn.example/hls/cam01/part2.m4s"' in body
    assert "/live/cam01/seg?u=https://cdn.example/hls/cam01/seg1.ts" in body


def test_blocking_reload_params_forwarded_upstream_with_longer_timeout(session):
    fake_resp = SimpleNamespace(text="#EXTM3U\n")
    admin = Principal("viewer1", "viewer", None)

    with patch("app.api.routes_stream.catalogue") as mock_catalogue:
        mock_catalogue.get.return_value = _fake_camera()
        mock_catalogue.authenticated_get.return_value = fake_resp
        hls_playlist("cam01", db=session, principal=admin, _HLS_msn=42, _HLS_part=3)

    _, kwargs = mock_catalogue.authenticated_get.call_args
    assert kwargs["params"] == {"_HLS_msn": 42, "_HLS_part": 3}
    assert kwargs["timeout"] == 30


def test_normal_reload_has_no_params_and_default_timeout(session):
    fake_resp = SimpleNamespace(text="#EXTM3U\n")
    admin = Principal("viewer1", "viewer", None)

    with patch("app.api.routes_stream.catalogue") as mock_catalogue:
        mock_catalogue.get.return_value = _fake_camera()
        mock_catalogue.authenticated_get.return_value = fake_resp
        hls_playlist("cam01", db=session, principal=admin)

    _, kwargs = mock_catalogue.authenticated_get.call_args
    assert kwargs["params"] is None
    assert kwargs["timeout"] == 10
