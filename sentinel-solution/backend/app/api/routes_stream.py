"""Authenticated HLS proxy for the frontend live-view feature.

Why this exists: per HACKATHON_DETAILS.md §13a, HLS is served from the CDN
host behind the sandbox access password (a session cookie), not a bearer
token a browser can attach itself. The backend already holds that
authenticated session (catalogue.py, used to poll cameras.json). Rather than
handing the sandbox password to every browser tab, the frontend requests
`/live/{camera_id}/index.m3u8` from US, and we fetch+relay it through the
session we already have — rewriting any relative segment URLs in the
playlist to route back through this same proxy.

This is exactly the "WebRTC/HLS relay" piece the hackathon's own suggested
Model 2 stack lists — not a new middleware layer, just what's needed to make
a password-gated feed playable in a browser at all.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, urljoin, urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..catalogue import catalogue, with_stream_auth
from ..db.models import CameraRegistry
from .auth import Principal, department_scope, require_role
from .deps import get_db

logger = logging.getLogger("sentinel.stream")

router = APIRouter(prefix="/live", tags=["live"])


def _scoped_camera_or_404(camera_id: str, db: Session, principal: Principal) -> None:
    """Apply the registry's non-enumerating department boundary to video.

    A scoped principal gets the same response for an unknown camera and a
    camera owned by another department.  Do this before consulting the live
    catalogue, which otherwise leaks cross-department stream availability.
    """
    department = department_scope(principal)
    if department is None:
        return
    camera = db.get(CameraRegistry, camera_id)
    if camera is None or camera.department != department:
        raise HTTPException(status_code=404, detail=f"camera {camera_id} not found")


@router.get("/{camera_id}/index.m3u8")
def hls_playlist(
    camera_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
    _HLS_msn: int | None = None,
    _HLS_part: int | None = None,
):
    """Transparently proxies LL-HLS if the upstream CDN serves it: forwards
    the client's blocking-reload directives (`_HLS_msn`/`_HLS_part`) and
    rewrites URI attributes on any tag line, not just EXT-X-KEY, so
    EXT-X-PART/EXT-X-PRELOAD-HINT/EXT-X-MAP route through our segment
    proxy instead of 404ing. IMPLEMENTED, UNVERIFIED — no LL-HLS-producing
    origin is reachable here to confirm the sandbox CDN actually emits
    these tags. Known gap: BYTERANGE-based partial segments aren't
    forwarded, only URI-per-part delivery."""
    _scoped_camera_or_404(camera_id, db, principal)
    cam = catalogue.get(camera_id)
    if cam is None:
        raise HTTPException(404, "unknown camera id — check /cameras")

    upstream_params = {}
    if _HLS_msn is not None:
        upstream_params["_HLS_msn"] = _HLS_msn
    if _HLS_part is not None:
        upstream_params["_HLS_part"] = _HLS_part
    # A blocking reload can legitimately take longer than a normal one —
    # the origin may hold the connection until the requested part exists.
    fetch_timeout = 30 if upstream_params else 10

    try:
        resp = catalogue.authenticated_get(cam.hls_url, params=upstream_params or None, timeout=fetch_timeout)
    except Exception as exc:  # noqa: BLE001 — surface as a clean 502, not a stack trace
        logger.warning("HLS playlist fetch failed for %s: %s", camera_id, exc)
        raise HTTPException(502, f"upstream HLS fetch failed: {exc}") from None

    rewritten_lines = []
    for line in resp.text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and "URI=" in stripped:
            # Any tag's URI attribute (EXT-X-KEY/MAP/PART/PRELOAD-HINT)
            # references a file relative to the CDN — rewrite it through
            # our segment proxy or the browser 404s against our own origin.
            def _rewrite_uri_attr(match: "re.Match[str]") -> str:
                absolute = urljoin(cam.hls_url, match.group(1))
                return f'URI="/live/{camera_id}/seg?u={absolute}"'

            rewritten_lines.append(re.sub(r'URI="([^"]+)"', _rewrite_uri_attr, line))
        elif stripped and not stripped.startswith("#") and "://" not in stripped:
            # Relative segment/sub-playlist reference — route it back through
            # our proxy, resolved against the original playlist URL so
            # nested relative paths (subdirectories) still work.
            absolute = urljoin(cam.hls_url, stripped)
            rewritten_lines.append(f"/live/{camera_id}/seg?u={absolute}")
        else:
            rewritten_lines.append(line)

    return Response(
        content="\n".join(rewritten_lines),
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/{camera_id}/seg")
def hls_segment(
    camera_id: str,
    u: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Proxies one HLS segment (or nested sub-playlist) — `u` is the absolute
    upstream URL captured by hls_playlist() above, kept on our own /live
    path so the browser never needs the CDN session directly.

    `u` is client-supplied (it round-trips through the browser's playlist
    fetch), so it MUST be restricted to the camera's own HLS host before
    we fetch it with our authenticated session — otherwise this endpoint is
    an open SSRF proxy that fetches ANY url using the sandbox credentials.
    """
    _scoped_camera_or_404(camera_id, db, principal)
    cam = catalogue.get(camera_id)
    if cam is None:
        raise HTTPException(404, "unknown camera id")

    expected_host = urlparse(cam.hls_url).netloc
    if urlparse(u).netloc != expected_host:
        raise HTTPException(400, "segment url host does not match this camera's HLS host")

    try:
        resp = catalogue.authenticated_get(u)
    except Exception as exc:  # noqa: BLE001
        logger.warning("HLS segment fetch failed for %s (%s): %s", camera_id, u, exc)
        raise HTTPException(502, f"upstream segment fetch failed: {exc}") from None

    content_type = resp.headers.get("Content-Type", "video/mp2t")
    return Response(content=resp.content, media_type=content_type)


# WHEP timeout: signaling only (SDP offer/answer exchange), so this should
# resolve in well under a second on a healthy media server — 10s just
# bounds a genuinely stuck upstream, same as the HLS proxy's default.
_WHEP_TIMEOUT_S = 10

# Matches the userinfo portion of a URL (scheme://user:pass@host/...).
# `requests`/urllib3 exception messages don't consistently omit it — e.g.
# `Response.raise_for_status()`'s HTTPError embeds `response.url` verbatim,
# credentials and all, and other request-construction failures can too.
# The HLS proxy above can safely log/return `exc` as-is because CDN URLs
# never carry credentials (cookie-session auth); WHEP URLs DO
# (email:password@, see catalogue.py), so every WHEP error path must
# sanitize before it reaches a log line or an HTTP response body — never
# assume a particular exception type is "safe" (CLAUDE.md 15.5).
_URL_USERINFO_RE = re.compile(r"://[^/@\s]+@")


def _sanitize_upstream_error(exc: Exception) -> str:
    return _URL_USERINFO_RE.sub("://<redacted>@", str(exc))


def _whep_host(whep_url: str) -> tuple[str | None, int | None]:
    parsed = urlparse(whep_url)
    return parsed.hostname, parsed.port


@router.post("/{camera_id}/whep")
async def whep_offer(
    camera_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Proxies only the WHEP signaling exchange (SDP offer in, SDP answer
    out). Unlike the HLS proxy above, this adds no ONGOING per-segment
    relay load: once the answer is returned, the actual SRTP media flows
    directly browser<->media-server (WebRTC's own nature — the CDN/backend
    cannot sit in that path anyway), so this satisfies "don't load the
    system" by construction, not by tuning.

    RTSP/WHEP require `email:password@` embedded in the URL
    (catalogue.py's `_rtsp_auth_prefix`) — a different auth model from
    HLS's CDN cookie session, so this cannot reuse
    `catalogue.authenticated_get`. `requests` extracts and sends that
    embedded userinfo as HTTP Basic auth automatically and strips it from
    the wire URL, so the credential is used but never logged or returned.

    Known gap: no PATCH trickle-ICE support — only the initial offer/
    answer and DELETE teardown are proxied (see `whep_teardown` below).
    Most WHEP media servers (e.g. MediaMTX) also support "vanilla" ICE
    (all candidates gathered before the answer is sent), so this still
    connects, just without trickle's faster connection setup. IMPLEMENTED,
    UNVERIFIED — no live WHEP-producing origin is reachable here to
    confirm end-to-end against a real media server, same caveat as the
    LL-HLS proxy above."""
    _scoped_camera_or_404(camera_id, db, principal)
    cam = catalogue.get(camera_id)
    if cam is None:
        raise HTTPException(404, "unknown camera id — check /cameras")

    offer_sdp = await request.body()
    try:
        resp = requests.post(
            cam.whep_url,
            data=offer_sdp,
            headers={"Content-Type": "application/sdp"},
            timeout=_WHEP_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — surface as a clean 502, not a stack trace
        safe_detail = _sanitize_upstream_error(exc)
        logger.warning("WHEP offer failed for %s: %s", camera_id, safe_detail)
        raise HTTPException(502, f"upstream WHEP offer failed: {safe_detail}") from None

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"upstream WHEP endpoint returned {resp.status_code}")

    response_headers = {}
    location = resp.headers.get("Location")
    if location:
        # urljoin(cam.whep_url, location) resolves a path-absolute Location
        # against cam.whep_url's full authority, WHICH INCLUDES the
        # embedded email:password userinfo — strip it back out before this
        # ever reaches the browser. The credential is re-attached
        # server-side by with_stream_auth() when whep_teardown proxies the
        # DELETE, so the browser only ever needs the stripped form to
        # round-trip the session identity.
        upstream_session_url = urljoin(cam.whep_url, location)
        parsed_session_url = urlparse(upstream_session_url)
        if "@" in parsed_session_url.netloc:
            stripped_netloc = parsed_session_url.netloc.rsplit("@", 1)[1]
            upstream_session_url = parsed_session_url._replace(netloc=stripped_netloc).geturl()
        response_headers["Location"] = (
            f"/live/{camera_id}/whep/session?u={quote(upstream_session_url, safe='')}"
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type="application/sdp",
        headers=response_headers,
    )


@router.delete("/{camera_id}/whep/session")
def whep_teardown(
    camera_id: str,
    u: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    """Ends a WHEP session the browser is finished with. `u` is client-
    supplied (round-tripped from `whep_offer`'s rewritten Location), so it
    MUST be restricted to this camera's own WHEP host before being fetched
    — same SSRF guard as `hls_segment`'s `u` param above. Best-effort: a
    failed teardown here just means the media server's own idle timeout
    cleans up the session later, not a client-visible error worth failing
    loudly over."""
    _scoped_camera_or_404(camera_id, db, principal)
    cam = catalogue.get(camera_id)
    if cam is None:
        raise HTTPException(404, "unknown camera id")

    expected_host, expected_port = _whep_host(cam.whep_url)
    parsed_u = urlparse(u)
    if parsed_u.hostname != expected_host or parsed_u.port != expected_port:
        raise HTTPException(400, "session url host does not match this camera's WHEP host")

    try:
        resp = requests.delete(with_stream_auth(u), timeout=_WHEP_TIMEOUT_S)
        return Response(status_code=resp.status_code)
    except Exception as exc:  # noqa: BLE001
        # `u` itself is already credential-free (see whep_offer's Location
        # rewrite) — only `exc`'s own text needs sanitizing here.
        logger.warning("WHEP teardown failed for %s (%s): %s", camera_id, u, _sanitize_upstream_error(exc))
        return Response(status_code=204)
