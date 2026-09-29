"""Measure the real edge/bandwidth-reduction ratio this pilot actually
achieves, instead of relying only on SCALABILITY.md's arithmetic projection
(80,000 cameras x an assumed ~2 Mbps).

Two real, independent measurements, both against data this deployment
actually produced — no new infrastructure, no synthetic numbers:

1. Real RTSP ingest bitrate for a real live sandbox camera, measured with a
   timed `ffmpeg -c copy -f null -` capture. Uses the STREAM-TIME bitrate
   (bytes received / seconds of video content decoded), not wall-clock
   transfer speed — this sandbox's own delivery pacing runs slower than
   real-time (observed `speed=0.2x-0.4x`), which is a sandbox artifact, not
   a property of the camera's encoding. Wall-clock bitrate would understate
   what a real deployment pulling this camera in real time would see.

2. Real structured-event size, computed from actual `vehicle_event` and
   `camera_density_window` rows already persisted in the real accumulated
   `sentinel.db` (read-only query; this script never writes to it) —
   serialized the same shape `analytics/federation.py`'s `NormalizedEvent`
   and `analytics/density.py`'s window rows actually cross an event-plane
   wire as, not an assumed "~1 KB" figure.

Output: a JSON artifact under `data/bandwidth_measurement/` plus a redacted
human-readable summary on stdout. Never prints an RTSP/WHEP URL — see
CLAUDE.md 15.5.

Honesty labels used in the output (CLAUDE.md 26's vocabulary):
- "measured_pilot": LIVE/REAL VERIFIED — this run's actual numbers.
- "extrapolated_statewide": a projection built from (1), explicitly labeled
  as a projection, not a proven statewide result.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalogue import catalogue  # noqa: E402
from app import config  # noqa: E402

CAPTURE_SECONDS = 10
STATEWIDE_CAMERA_COUNT = 80_000


def _redact(text: str) -> str:
    return re.sub(r"rtsp://[^\s\"']+", "rtsp://[REDACTED]", text)


def measure_real_rtsp_bitrate_kbps(camera_id: str, rtsp_url: str) -> dict:
    """Real timed capture of one live camera. Returns a dict with the
    measured bitrate and the raw evidence numbers behind it, or an
    `error` key if the camera could not be captured (never fabricates
    a number when the real capture fails)."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-rtsp_transport", "tcp", "-i", rtsp_url,
                "-t", str(CAPTURE_SECONDS), "-c", "copy", "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=CAPTURE_SECONDS + 20,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        # `TimeoutExpired.__str__` includes the full argv, which contains the
        # credential-bearing RTSP URL — redact before this ever reaches a
        # print or a written file (CLAUDE.md 15.5).
        return {"camera_id": camera_id, "error": f"capture failed: {_redact(str(exc))}"}

    stderr = _redact(proc.stderr)
    size_match = re.search(r"video:(\d+)KiB", stderr)
    time_match = re.search(r"Lsize=\S*\s+time=(\d+):(\d+):(\d+\.\d+)", stderr) or re.search(
        r"time=(\d+):(\d+):(\d+\.\d+)", stderr
    )
    if not size_match or not time_match:
        return {"camera_id": camera_id, "error": "could not parse ffmpeg summary", "stderr_tail": stderr[-400:]}

    video_kib = int(size_match.group(1))
    groups = time_match.groups()
    h, m, s = (float(g) for g in groups[-3:])
    stream_seconds = h * 3600 + m * 60 + s
    if stream_seconds <= 0:
        return {"camera_id": camera_id, "error": "zero stream-seconds captured"}

    kbps = (video_kib * 1024 * 8) / stream_seconds / 1000
    return {
        "camera_id": camera_id,
        "video_kib_received": video_kib,
        "stream_seconds_decoded": round(stream_seconds, 2),
        "measured_bitrate_kbps": round(kbps, 1),
    }


def measure_real_structured_event_bytes(db_path: str, camera_id: str | None = None) -> dict:
    """Real average serialized size of what actually crosses the event-plane
    wire today: a `vehicle_event` row shaped like `federation.py`'s
    `NormalizedEvent.raw_payload`, and a `camera_density_window` row shaped
    like the window rows `density.py` writes. Read-only against the real
    accumulated database — never mutates it.

    When `camera_id` is given, the event-rate figure is computed for THAT
    camera alone — comparing one camera's real RTSP bitrate against a
    global all-camera event rate would silently mix two different
    cameras' traffic and produce a meaningless ratio. Byte-size averages
    still sample across all cameras (a bigger, more representative
    sample); only the rate is camera-scoped."""
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute(
        "SELECT plate, plate_confidence, camera_id, observed_at FROM vehicle_event "
        "ORDER BY id DESC LIMIT 500"
    )
    event_rows = cur.fetchall()
    event_sizes = [
        len(json.dumps({
            "plate": r["plate"], "plate_confidence": r["plate_confidence"],
            "camera_id": r["camera_id"], "observed_at": r["observed_at"],
        }, default=str).encode("utf-8"))
        for r in event_rows
    ]

    cur.execute(
        "SELECT camera_id, window_started_at, window_seconds, sampled_frames, "
        "vehicle_detections, person_detections FROM camera_density_window "
        "ORDER BY id DESC LIMIT 500"
    )
    density_rows = cur.fetchall()
    density_sizes = [
        len(json.dumps(dict(r), default=str).encode("utf-8"))
        for r in density_rows
    ]

    if camera_id is not None:
        cur.execute(
            "SELECT MIN(observed_at), MAX(observed_at), COUNT(*) FROM vehicle_event WHERE camera_id = ?",
            (camera_id,),
        )
    else:
        cur.execute("SELECT MIN(observed_at), MAX(observed_at), COUNT(*) FROM vehicle_event")
    min_ts, max_ts, total_count = cur.fetchone()
    con.close()

    real_events_per_second = None
    span_s = None
    if min_ts and max_ts and total_count and min_ts != max_ts:
        span_s = (dt.datetime.fromisoformat(max_ts) - dt.datetime.fromisoformat(min_ts)).total_seconds()
        if span_s > 0:
            real_events_per_second = total_count / span_s

    return {
        "rate_scoped_to_camera": camera_id,
        "sample_vehicle_events": len(event_sizes),
        "avg_vehicle_event_bytes": round(statistics.fmean(event_sizes), 1) if event_sizes else None,
        "sample_density_windows": len(density_sizes),
        "avg_density_window_bytes": round(statistics.fmean(density_sizes), 1) if density_sizes else None,
        "camera_vehicle_event_rows": total_count,
        "observed_span_seconds": round(span_s, 1) if span_s else None,
        "real_events_per_second_this_camera": round(real_events_per_second, 4) if real_events_per_second else None,
    }


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "sentinel.db"

    cams = catalogue.refresh()
    live = {cid: c for cid, c in cams.items() if c.live}

    # Prefer live cameras that ALSO have real vehicle_event history in this
    # DB, so the RTSP-bitrate sample and the event-rate sample describe the
    # SAME camera's real traffic — comparing camera A's video bitrate
    # against camera B's event rate would silently mix two different
    # cameras and produce a meaningless ratio.
    import sqlite3
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cameras_with_events = {
        row[0] for row in con.execute("SELECT DISTINCT camera_id FROM vehicle_event").fetchall()
    }
    con.close()
    candidates = [cid for cid in live if cid in cameras_with_events]
    sample_ids = candidates[:3] if candidates else list(live.keys())[:3]
    if not candidates:
        print("WARNING: none of the currently-live cameras have real vehicle_event "
              "history in this DB — rate/ratio numbers below will be omitted rather "
              "than compared across mismatched cameras.")
    print(f"Capturing {len(sample_ids)} real live camera(s): {sample_ids}")

    rtsp_measurements = []
    for cid in sample_ids:
        print(f"  measuring {cid} ({CAPTURE_SECONDS}s real capture)...")
        rtsp_measurements.append(measure_real_rtsp_bitrate_kbps(cid, live[cid].rtsp_url))

    ok_measurements = [m for m in rtsp_measurements if "measured_bitrate_kbps" in m]
    avg_rtsp_kbps = (
        statistics.fmean(m["measured_bitrate_kbps"] for m in ok_measurements) if ok_measurements else None
    )

    # Per-camera event rate, scoped to one of the sampled cameras that has
    # real history (so it lines up with the RTSP measurement above).
    rate_camera = next((cid for cid in sample_ids if cid in cameras_with_events), None)
    event_stats = measure_real_structured_event_bytes(db_path, camera_id=rate_camera)

    result = {
        "measured_at": dt.datetime.utcnow().isoformat() + "Z",
        "db_used": db_path,
        "measured_pilot": {
            "rtsp_capture_per_camera": rtsp_measurements,
            "avg_measured_rtsp_kbps": round(avg_rtsp_kbps, 1) if avg_rtsp_kbps else None,
            "structured_event_sizes": event_stats,
        },
    }

    if avg_rtsp_kbps and event_stats.get("avg_vehicle_event_bytes") and event_stats.get("real_events_per_second_this_camera"):
        event_plane_bps = event_stats["avg_vehicle_event_bytes"] * 8 * event_stats["real_events_per_second_this_camera"]
        real_ratio = (avg_rtsp_kbps * 1000) / event_plane_bps if event_plane_bps > 0 else None
        result["measured_pilot"]["real_event_plane_bps_per_camera"] = round(event_plane_bps, 3)
        result["measured_pilot"]["real_measured_compression_ratio"] = round(real_ratio, 1) if real_ratio else None

        result["extrapolated_statewide"] = {
            "note": "PROJECTION built from the measured_pilot numbers above — not an independently proven statewide result.",
            "camera_count": STATEWIDE_CAMERA_COUNT,
            "raw_video_gbps": round(avg_rtsp_kbps * STATEWIDE_CAMERA_COUNT / 1_000_000, 2),
            "event_plane_mbps": round(event_plane_bps * STATEWIDE_CAMERA_COUNT / 1_000_000_000 * 1000, 2),
        }

    out_dir = Path(__file__).resolve().parent.parent / "data" / "bandwidth_measurement"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
