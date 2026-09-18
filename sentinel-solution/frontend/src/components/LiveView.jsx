import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { api, getCsrfToken } from "../api";

// Non-trickle ICE only: the backend's WHEP proxy (routes_stream.py) proxies
// just the initial offer/answer exchange, not PATCH trickle candidates (see
// its docstring) — so the offer must not be sent until ICE gathering has
// finished collecting every local candidate. Most media servers (MediaMTX
// included) accept this "vanilla ICE" form; it just means slightly slower
// connection setup than trickle, not a correctness problem.
function waitForIceGatheringComplete(pc, timeoutMs = 5000) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs);
    const check = () => {
      if (pc.iceGatheringState === "complete") {
        clearTimeout(timer);
        pc.removeEventListener("icegatheringstatechange", check);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", check);
  });
}

// Plays a camera's feed either via our backend's /live/{id}/index.m3u8 HLS
// proxy, or (toggle) via the lower-latency /live/{id}/whep WebRTC signaling
// proxy — see routes_stream.py for both. WHEP's actual media (SRTP) flows
// directly browser<->media-server once signaling completes; only the SDP
// offer/answer and session teardown go through the backend, so switching
// modes adds no ongoing relay load server-side.
export default function LiveView({ cameraId }) {
  const videoRef = useRef(null);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("hls");

  useEffect(() => {
    setError(null);
    if (!cameraId || !videoRef.current || mode !== "hls") return;

    const video = videoRef.current;
    video.srcObject = null; // clear any leftover WHEP MediaStream from the other mode
    const src = api.hlsUrl(cameraId);
    let hls;

    if (Hls.isSupported()) {
      hls = new Hls({
        maxBufferLength: 10,
        // /live/* is RBAC-gated (routes_stream.py) — hls.js's own fetches
        // for the playlist and every segment need the session cookie too,
        // not just the initial <video> element. withCredentials, not a
        // header, now that auth is a cookie (SEC-4, 2026-09-18b).
        xhrSetup: (xhr) => {
          xhr.withCredentials = true;
        },
      });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_evt, data) => {
        if (data.fatal) setError(`stream error: ${data.details}`);
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Native Safari HLS's own request pipeline is a separate code path
      // from fetch/XHR and has known, inconsistent cross-origin cookie
      // behavior across Safari versions — not verified to reliably carry
      // the session cookie. Do not assign src and leave an opaque blank
      // player: fail with an honest message instead.
      setError("Live view requires Chrome, Firefox, or Edge in this environment (Safari's native HLS player is not verified to carry the session cookie).");
    } else {
      setError("this browser cannot play HLS");
    }

    return () => hls?.destroy();
  }, [cameraId, mode]);

  useEffect(() => {
    if (!cameraId || !videoRef.current || mode !== "whep") return;

    const video = videoRef.current;
    video.removeAttribute("src"); // clear any leftover HLS <video src> from the other mode
    video.load();
    let cancelled = false;
    let pc = null;
    let teardownUrl = null;

    async function connect() {
      pc = new RTCPeerConnection();
      pc.addTransceiver("video", { direction: "recvonly" });
      pc.addTransceiver("audio", { direction: "recvonly" });
      pc.ontrack = (evt) => {
        if (video.srcObject !== evt.streams[0]) video.srcObject = evt.streams[0];
      };
      pc.oniceconnectionstatechange = () => {
        if (!cancelled && ["failed", "disconnected"].includes(pc.iceConnectionState)) {
          setError(`WHEP connection ${pc.iceConnectionState} — the feed may be offline`);
        }
      };

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await waitForIceGatheringComplete(pc);
      if (cancelled) return;

      const headers = { "Content-Type": "application/sdp" };
      const csrf = getCsrfToken();
      if (csrf) headers["X-Sentinel-CSRF-Token"] = csrf;

      const res = await fetch(api.whepUrl(cameraId), {
        method: "POST",
        credentials: "include",
        headers,
        body: pc.localDescription.sdp,
      });
      if (!res.ok) throw new Error(`WHEP offer rejected (${res.status})`);

      const location = res.headers.get("Location");
      if (location) teardownUrl = location.startsWith("http") ? location : `${api.base}${location}`;

      const answerSdp = await res.text();
      if (cancelled) return;
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    }

    connect().catch((err) => {
      if (!cancelled) setError(`WHEP setup failed: ${err.message} — try HLS instead`);
    });

    return () => {
      cancelled = true;
      pc?.close();
      if (teardownUrl) {
        const csrf = getCsrfToken();
        const headers = csrf ? { "X-Sentinel-CSRF-Token": csrf } : {};
        // Best-effort: an idle WHEP session on the media server times out
        // on its own even if this never lands (e.g. tab closed mid-flight).
        fetch(teardownUrl, { method: "DELETE", credentials: "include", headers }).catch(() => {});
      }
    };
  }, [cameraId, mode]);

  if (!cameraId) {
    return <div className="live-view live-view--empty">Select a camera to view its feed.</div>;
  }

  return (
    <div className="live-view">
      <div className="live-view__mode-toggle">
        <button type="button" disabled={mode === "hls"} onClick={() => setMode("hls")}>
          HLS
        </button>
        <button type="button" disabled={mode === "whep"} onClick={() => setMode("whep")}>
          Low-latency (WHEP)
        </button>
      </div>
      <video ref={videoRef} controls autoPlay muted className="live-view__video" />
      {error && <div className="live-view__error">{error} — feed may be offline or the sandbox session expired.</div>}
    </div>
  );
}
