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
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..catalogue import catalogue
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
