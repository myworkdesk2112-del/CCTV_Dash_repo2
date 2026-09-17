"""Camera catalogue client.

Per the integration guide: "Always start from the catalogue rather than
hard-coding endpoints" — camera ids and the set of available cameras can
change, the catalogue is the contract, not the URL pattern.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import quote

import requests

from . import config

logger = logging.getLogger("sentinel.catalogue")


def _rtsp_auth_prefix() -> str:
    """`email:password@` for RTSP/WHEP URLs, percent-encoded (the `@` in an
    email must become `%40` or it breaks URL parsing). RTSP/WHEP now require
    per-connection credentials in the URL itself — this is separate from the
    CDN's cookie-session login used for HLS/the catalogue. Empty string (no
    prefix) if either credential is unset, so the URL degrades to the old
    unauthenticated form rather than embedding a stray "@" with nothing
    before it.
    """
    if not config.SENTINEL_ACCESS_EMAIL or not config.SENTINEL_ACCESS_TOKEN:
        return ""
    email = quote(config.SENTINEL_ACCESS_EMAIL, safe="")
    password = quote(config.SENTINEL_ACCESS_TOKEN, safe="")
    return f"{email}:{password}@"


@dataclass
class CameraInfo:
    id: str
    location: Optional[str]
    codec: Optional[str]
    live: bool
    rtsp_url: str
    whep_url: str
    hls_url: str
    raw: dict

    @classmethod
    def from_api(cls, entry: dict) -> "CameraInfo":
        # Real cameras.json entries are just {"id": "cam04", "name": "..."}
        # — no location/codec/live fields. Treat catalogue presence as live
        # (StreamManager will find out for real when it opens the RTSP URL).
        cam_id = str(entry.get("id"))
        auth = _rtsp_auth_prefix()
        return cls(
            id=cam_id,
            location=entry.get("location") or entry.get("name"),
            codec=entry.get("codec"),
            live=bool(entry.get("live", True)),
            # RTSP/WHEP: public IP, direct (CDN can't proxy raw TCP/UDP media).
            # Both now require email:password embedded in the URL (percent-
            # encoded) — the integrator's guide was updated to require this
            # per-connection credential on top of the CDN's cookie session.
            rtsp_url=entry.get("rtsp_url") or f"rtsp://{auth}{config.STREAM_HOST}:{config.RTSP_PORT}/stream/{cam_id}",
            whep_url=entry.get("whep_url") or f"http://{auth}{config.STREAM_HOST}:{config.WHEP_PORT}/stream/{cam_id}/whep",
            # HLS: CDN host, password-protected, works from anywhere.
            hls_url=entry.get("hls_url") or f"https://{config.CDN_HOST}/{cam_id}/index.m3u8",
            raw=entry,
        )


class CatalogueClient:
    """Polls cameras.json on an interval and keeps an in-memory snapshot.

    Auth is cookie-based, not header-based: the CDN portal
    (cctv.corp8.cloud) issues a session cookie from POST /auth/login with
    form fields `email` AND `password` (both required — the login page has
    an email input too; sending password alone silently 200s back to the
    login form instead of erroring, which looks like success if you only
    check the status code). This client logs in once, reuses the session,
    and re-logs-in on 401/302.

    Thread-safe: StreamManager and API routes read `.cameras` concurrently.
    """

    def __init__(
        self,
        url: str = config.CATALOGUE_URL,
        password: str = config.SENTINEL_ACCESS_TOKEN,
        email: str = config.SENTINEL_ACCESS_EMAIL,
        login_url: str = f"https://{config.CDN_HOST}/auth/login",
    ):
        self._url = url
        self._password = password
        self._email = email
        self._login_url = login_url
        self._session = requests.Session()
        # The CDN gates the HLS playlist/segment endpoints (not /cameras.json
        # or /auth/login) behind a User-Agent check — requests' default UA
        # (`python-requests/x.x`) gets a 403 with a "browser required" text
        # body. Found 2026-09-05 while diagnosing a live 502 in
        # routes_stream.py (which surfaces any authenticated_get() failure
        # as a clean 502 — that part was already correct; the actual
        # upstream error was masked because `-o /dev/null` in an earlier
        # curl check discarded the response body that would have shown
        # "browser required" immediately). A real browser UA on the whole
        # session (not just HLS calls) is the simplest fix and costs
        # nothing on the endpoints that didn't need it.
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
        })
        self._logged_in = False
        self._lock = threading.RLock()
        self._cameras: Dict[str, CameraInfo] = {}
        self._last_refresh: float = 0.0

    @property
    def cameras(self) -> Dict[str, CameraInfo]:
        with self._lock:
            return dict(self._cameras)

    def _login(self) -> bool:
        if not self._password or not self._email:
            logger.warning(
                "SENTINEL_ACCESS_TOKEN and/or SENTINEL_ACCESS_EMAIL not set — cannot log in to %s",
                self._login_url,
            )
            return False
        try:
            # allow_redirects=False is required: the portal responds 302 -> grid
            # on success and 200 (re-rendering the login form) on failure. If
            # redirects are followed, both cases end up as a 200 with no
            # Location header, so a wrong password looks identical to success.
            resp = self._session.post(
                self._login_url,
                data={"email": self._email, "password": self._password},
                timeout=10,
                allow_redirects=False,
            )
            self._logged_in = resp.status_code == 302 and "auth/login" not in resp.headers.get("location", "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("login failed: %s", exc)
            self._logged_in = False
        return self._logged_in

    def refresh(self) -> Dict[str, CameraInfo]:
        if config.ONVIF_DISCOVERY_ENABLED:
            onvif_cameras = self._try_onvif_discovery()
            if onvif_cameras:
                if config.DEMO_CAMERA_SCOPE is not None:
                    onvif_cameras = {
                        cid: cam for cid, cam in onvif_cameras.items() if cid in config.DEMO_CAMERA_SCOPE
                    }
                with self._lock:
                    self._cameras = onvif_cameras
                    self._last_refresh = time.time()
                logger.info("ONVIF discovery found %d camera(s) this refresh.", len(onvif_cameras))
                return self.cameras
            logger.info("ONVIF discovery found no devices — falling back to the sandbox catalogue.")

        if not self._logged_in and not self._login():
            return self.cameras

        try:
            resp = self._session.get(self._url, timeout=10, allow_redirects=False)
            if resp.status_code in (301, 302, 401, 403):
                # Session expired — re-login once and retry.
                self._logged_in = False
                if not self._login():
                    return self.cameras
                resp = self._session.get(self._url, timeout=10, allow_redirects=False)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 — catalogue must never crash callers
            logger.warning("catalogue refresh failed: %s", exc)
            return self.cameras

        # Real response is a bare JSON list of {"id", "name"}; tolerate a
        # {"cameras": [...]} wrapper too in case the shape changes later.
        entries = payload if isinstance(payload, list) else payload.get("cameras", [])
        cameras = {}
        for entry in entries:
            try:
                cam = CameraInfo.from_api(entry)
                if config.DEMO_CAMERA_SCOPE is not None and cam.id not in config.DEMO_CAMERA_SCOPE:
                    continue
                cameras[cam.id] = cam
            except Exception as exc:  # noqa: BLE001
                logger.warning("skipping malformed catalogue entry %s: %s", entry, exc)

        with self._lock:
            self._cameras = cameras
            self._last_refresh = time.time()
        logger.info("catalogue refreshed: %d cameras (%d live)", len(cameras), sum(c.live for c in cameras.values()))
        return cameras

    def _try_onvif_discovery(self) -> Dict[str, CameraInfo]:
        """Never raises — any failure degrades to an empty dict so
        refresh() falls back to the sandbox HTTP catalogue."""
        # Lazy import: onvif_discovery.py imports CameraInfo from here,
        # so a top-level import would be circular.
        from .streaming import onvif_discovery

        try:
            return onvif_discovery.discover(
                username=config.ONVIF_USERNAME or None,
                password=config.ONVIF_PASSWORD or None,
                probe_timeout_s=config.ONVIF_PROBE_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001 — discovery must never crash a catalogue refresh
            logger.warning("ONVIF discovery failed (%s) — falling back to sandbox catalogue.", exc)
            return {}

    def get(self, camera_id: str) -> Optional[CameraInfo]:
        with self._lock:
            return self._cameras.get(str(camera_id))

    def authenticated_get(self, url: str, timeout: float = 10, **kwargs):
        """Fetch a CDN-hosted URL (HLS playlist/segment) using this client's
        already-authenticated session — needed because the CDN's access
        password lives here, not in the browser. Used by routes_stream.py to
        proxy HLS so the frontend can actually play a feed without us having
        to hand the sandbox access password to every browser tab. Re-logs-in
        once on session expiry, same as refresh().

        `timeout` defaults to 10s but is overridable — an LL-HLS blocking
        playlist reload can legitimately hold the connection open longer."""
        if not self._logged_in and not self._login():
            raise RuntimeError("not authenticated with CDN — check SENTINEL_ACCESS_TOKEN")
        resp = self._session.get(url, timeout=timeout, allow_redirects=False, **kwargs)
        if resp.status_code in (301, 302, 401, 403):
            self._logged_in = False
            if not self._login():
                raise RuntimeError("re-authentication with CDN failed")
            resp = self._session.get(url, timeout=timeout, allow_redirects=False, **kwargs)
        resp.raise_for_status()
        return resp

    def start_background_refresh(self) -> threading.Thread:
        def loop():
            while True:
                self.refresh()
                time.sleep(config.CATALOGUE_REFRESH_INTERVAL_S)

        t = threading.Thread(target=loop, name="catalogue-refresh", daemon=True)
        t.start()
        return t


catalogue = CatalogueClient()
