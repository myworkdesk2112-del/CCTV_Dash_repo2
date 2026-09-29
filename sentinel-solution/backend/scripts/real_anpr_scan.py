"""Real (non-composited) ANPR scan against the live sandbox's actual camera
footage — no synthetic/pasted plates anywhere in this script.

Answers the single open question blocking the government-feed demo (see
REQUIREMENTS_COVERAGE.md's "remaining priority order" #1): are real plates
readable in the sandbox's actual footage at all, and if reads fail, is the
failure in *localization* (plate never even lands in the extracted crop
region — StubPlateDetector's fixed-geometry heuristic) or in *OCR* (plate is
in the crop but PaddleOCR can't read it)? A single "0/4" number can't
distinguish these; this script reports both separately, per REVIEW_FINDINGS.md
ML-1's finding that localization is the more likely culprit for these
cameras' overview angles.

This bypasses AnalyticsPipeline/the DB entirely — it is a measurement tool,
not a demo populator. Nothing here is persisted to sentinel.db.

Run (from backend/, in the ML .venv, with the real sandbox .env sourced —
NEVER print/log SENTINEL_ACCESS_TOKEN/EMAIL or any camera's rtsp_url, both
carry the sandbox password):

    set -a && . ../.env && set +a
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python scripts/real_anpr_scan.py

That env var is only needed if the real trained plate localizer
(`weights/license-plate-finetune-v1n.onnx`) is present — its onnxruntime
dependency wants a newer protobuf than paddlepaddle can load natively; see
requirements-ml.txt's "KNOWN LIVE CONFLICT" note for why. Harmless to set
unconditionally (falls back to StubPlateDetector without it).

Env knobs (all optional):
    SCAN_CAMERAS               comma-separated camera ids, default = all in catalogue
    SCAN_SECONDS_PER_CAMERA     wall-clock seconds to sample each camera, default 20
    SCAN_MAX_SAVES_PER_CAMERA   cap on saved review images per camera, default 6
    SCAN_RECONNECT              "true" to reconnect with backoff on a stream drop instead of
                                 ending that camera's scan early (added for long unattended
                                 runs, e.g. sampling a full ~12h sandbox loop on one camera —
                                 HACKATHON_DETAILS.md §13a's own "reconnect with backoff"
                                 guidance, opt-in so the short default scan's behavior is
                                 unchanged). Backoff: 2s, doubling, capped at 30s.
    SCAN_PROGRESS_INTERVAL_S    if set, print a running per-camera status line at this
                                 interval (seconds) instead of staying silent until the
                                 camera's scan ends — useful once SCAN_SECONDS_PER_CAMERA is
                                 hours, not seconds.
    SCAN_STOP_AFTER_DISTINCT_PLATES  if set, stop that camera's scan as soon as this many
                                 DISTINCT pattern-valid (and, since 2026-09-26, state-code-
                                 whitelisted) plate texts have been read, instead of running
                                 the full SCAN_SECONDS_PER_CAMERA regardless. Distinctness is
                                 exact-string, on the OCR text as read — plate normalization/
                                 fuzzy-dedup is deliberately not applied here; this is a raw
                                 measurement tool, not the real pipeline's identity resolver.
                                 SCAN_SECONDS_PER_CAMERA still applies as an upper bound in
                                 case that many distinct plates never turn up.
    SCAN_OUTPUT_DIR             default ./data/anpr_scan/<UTC timestamp>
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2

# ORDER MATTERS (Windows torch/paddle DLL conflict — see main.py): build the
# YOLO detector (imports torch via ultralytics) before the PaddleOCR reader.
from app.analytics.detector import YoloVehicleDetector
from app.analytics.anpr import PaddleOcrPlateReader
from app.analytics.plate_detector import StubPlateDetector, YoloPlateDetector, crop_plate, enhance_plate_crop
from app.catalogue import catalogue
from app import config

SCAN_CAMERAS = [c.strip() for c in os.environ.get("SCAN_CAMERAS", "").split(",") if c.strip()]
SECONDS_PER_CAMERA = float(os.environ.get("SCAN_SECONDS_PER_CAMERA", "20"))
MAX_SAVES_PER_CAMERA = int(os.environ.get("SCAN_MAX_SAVES_PER_CAMERA", "6"))
RECONNECT = os.environ.get("SCAN_RECONNECT", "false").lower() == "true"
PROGRESS_INTERVAL_S = float(os.environ.get("SCAN_PROGRESS_INTERVAL_S", "0")) or None
STOP_AFTER_DISTINCT_PLATES = int(os.environ.get("SCAN_STOP_AFTER_DISTINCT_PLATES", "0")) or None
RUN_ID = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
OUTPUT_DIR = os.environ.get("SCAN_OUTPUT_DIR", os.path.join("data", "anpr_scan", RUN_ID))

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


def _open_capture(rtsp_url: str, connect_timeout_s: float = 12.0) -> "cv2.VideoCapture | None":
    """One-shot open, no reconnect/backoff loop — this is a bounded
    measurement scan, not a long-running service (see rtsp_client.py for the
    real resilient consumer used in production). A camera that fails to open
    or produces nothing is reported as such, not silently skipped."""
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    deadline = time.time() + connect_timeout_s
    while not cap.isOpened() and time.time() < deadline:
        time.sleep(0.5)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def scan_camera(camera_id: str, rtsp_url: str, detector, plate_detector, plate_reader, out_dir: str) -> dict:
    cam_dir = os.path.join(out_dir, camera_id)
    os.makedirs(cam_dir, exist_ok=True)

    result = {
        "camera_id": camera_id,
        "opened": False,
        "frames_read": 0,
        "vehicle_detections": 0,
        "plate_localized": 0,   # plate_detector.locate() returned a non-empty bbox
        "plate_read": 0,        # PaddleOCR produced a PLATE_PATTERN-matching string
        "reads": [],            # [{text, confidence, frame_no}]
        "saved": [],            # review image paths for manual "was the plate actually in this crop?" checks
        "error": None,
    }

    cap = _open_capture(rtsp_url)
    if cap is None:
        result["error"] = "failed to open RTSP stream (no connection within timeout)"
        return result
    result["opened"] = True

    frame_stride = config.ANALYTICS_FRAME_STRIDE
    deadline = time.time() + SECONDS_PER_CAMERA
    frame_no = 0
    saves = 0
    reconnect_backoff_s = 2.0
    last_progress_at = time.time()
    distinct_plates: set[str] = set()

    try:
        while time.time() < deadline:
            if cap is None:
                # Mid-backoff after a failed reconnect attempt (below) —
                # try again rather than calling .read() on nothing.
                time.sleep(min(reconnect_backoff_s, 5.0))
                cap = _open_capture(rtsp_url, connect_timeout_s=5.0)
                continue

            ok, frame = cap.read()
            if not ok:
                if not RECONNECT:
                    break
                # Expected on a long run: the sandbox's loop point is a hard
                # scene cut (HACKATHON_DETAILS.md §13.3), and any real network
                # session can drop. Reconnect with backoff rather than ending
                # an 11-hour scan after the first hiccup; frame_no/saves are
                # NOT reset, so this camera's counters stay one continuous
                # series across the reconnect.
                print(f"  [{camera_id}] stream ended/dropped — reconnecting "
                      f"(backoff {reconnect_backoff_s:.0f}s)...", flush=True)
                cap.release()
                time.sleep(reconnect_backoff_s)
                reconnect_backoff_s = min(reconnect_backoff_s * 2, 30.0)
                cap = _open_capture(rtsp_url)  # may return None; handled at top of loop
                continue
            reconnect_backoff_s = 2.0  # reset once a frame arrives again
            frame_no += 1
            result["frames_read"] += 1
            if PROGRESS_INTERVAL_S and (time.time() - last_progress_at) >= PROGRESS_INTERVAL_S:
                last_progress_at = time.time()
                remaining_s = max(0, deadline - time.time())
                print(
                    f"  [{camera_id}] progress: frames={result['frames_read']} "
                    f"vehicles={result['vehicle_detections']} "
                    f"localized={result['plate_localized']} "
                    f"read={result['plate_read']} "
                    f"({remaining_s / 3600:.1f}h remaining)",
                    flush=True,
                )
            if frame_no % frame_stride != 0:
                continue

            detections = detector.detect(frame)
            target_reached = False
            for det in detections:
                if det.label == "person":
                    continue
                result["vehicle_detections"] += 1
                x1, y1, x2, y2 = (int(v) for v in det.bbox)
                crop = frame[max(y1, 0):max(y2, 0), max(x1, 0):max(x2, 0)]
                if crop.size == 0:
                    continue

                plate_bbox = plate_detector.locate(crop)
                plate_crop = crop_plate(crop, plate_bbox) if plate_bbox is not None else None
                if plate_bbox is not None and plate_crop is not None and plate_crop.size > 0:
                    result["plate_localized"] += 1
                    enhanced = enhance_plate_crop(plate_crop)
                    read = plate_reader.read(enhanced)
                else:
                    enhanced = None
                    read = None

                if read is not None:
                    text, conf = read
                    result["plate_read"] += 1
                    result["reads"].append({"text": text, "confidence": conf, "frame_no": frame_no})
                    is_new = text not in distinct_plates
                    distinct_plates.add(text)
                    if is_new:
                        print(f"  [{camera_id}] distinct plate #{len(distinct_plates)}: "
                              f"{text} (confidence {conf:.3f}, frame {frame_no})", flush=True)
                    if STOP_AFTER_DISTINCT_PLATES and len(distinct_plates) >= STOP_AFTER_DISTINCT_PLATES:
                        target_reached = True

                # A successful plate read is ALWAYS saved, uncapped — found
                # 2026-09-26: with a single shared `saves` budget, a run that
                # hit its cap early (on ordinary vehicle detections, before
                # any plate was ever read) produced 10 "distinct" reads with
                # not one saved image to visually confirm any of them
                # against. MAX_SAVES_PER_CAMERA still caps the *diagnostic*
                # no-read saves below (false-positive/negative review), but
                # a real read is exactly the evidence this script exists to
                # let a human verify, so it must never be crowded out.
                if read is not None:
                    tag = f"f{frame_no}_v{result['vehicle_detections']}_READ"
                    vpath = os.path.join(cam_dir, f"{tag}_vehicle.jpg")
                    cv2.imwrite(vpath, crop)
                    saved_entry = {"vehicle_crop": vpath, "plate_crop": None, "ocr_read": read}
                    if plate_crop is not None and plate_crop.size > 0:
                        ppath = os.path.join(cam_dir, f"{tag}_platecrop.jpg")
                        cv2.imwrite(ppath, plate_crop)
                        saved_entry["plate_crop"] = ppath
                    result["saved"].append(saved_entry)
                elif saves < MAX_SAVES_PER_CAMERA:
                    # Save the vehicle crop + (if localized) the plate-region
                    # crop, so a human can check "did the plate ACTUALLY land
                    # in this crop region" independent of whether OCR read it —
                    # the distinction this whole script exists to measure.
                    tag = f"f{frame_no}_v{result['vehicle_detections']}"
                    vpath = os.path.join(cam_dir, f"{tag}_vehicle.jpg")
                    cv2.imwrite(vpath, crop)
                    saved_entry = {"vehicle_crop": vpath, "plate_crop": None, "ocr_read": read}
                    if plate_crop is not None and plate_crop.size > 0:
                        ppath = os.path.join(cam_dir, f"{tag}_platecrop.jpg")
                        cv2.imwrite(ppath, plate_crop)
                        saved_entry["plate_crop"] = ppath
                    result["saved"].append(saved_entry)
                    saves += 1

                if target_reached:
                    break  # inner for-loop over this frame's detections

            if target_reached:
                print(f"  [{camera_id}] reached target of {STOP_AFTER_DISTINCT_PLATES} "
                      f"distinct plate(s) — stopping this camera early.", flush=True)
                break  # outer while-loop — stop sampling this camera
    finally:
        if cap is not None:
            cap.release()

    return result


def main() -> None:
    if not config.SENTINEL_ACCESS_EMAIL or not config.SENTINEL_ACCESS_TOKEN:
        print("SENTINEL_ACCESS_EMAIL / SENTINEL_ACCESS_TOKEN not set — source ../.env first "
              "(set -a && . ../.env && set +a). Refusing to run against an unauthenticated catalogue.")
        sys.exit(1)

    catalogue.refresh()
    cameras = catalogue.cameras
    if not cameras:
        print("Catalogue returned zero cameras — check sandbox access (see catalogue.py's login flow).")
        sys.exit(1)

    ids = SCAN_CAMERAS or sorted(cameras.keys())
    missing = [cid for cid in ids if cid not in cameras]
    if missing:
        print(f"Warning: requested camera ids not in catalogue, skipping: {missing}")
    ids = [cid for cid in ids if cid in cameras]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Scanning {len(ids)} camera(s) for {SECONDS_PER_CAMERA:.0f}s each -> {OUTPUT_DIR}")
    print("(never printing rtsp_url or credentials — camera ids only)")

    detector = YoloVehicleDetector(weights=config.YOLO_WEIGHTS)
    # Real trained localizer if the weights are present (see main.py's
    # _build_plate_detector for the same fallback pattern) — this script
    # previously hardcoded StubPlateDetector, which understated real
    # localization behavior once YoloPlateDetector was wired in 2026-09-05.
    import os as _os
    if _os.path.exists(config.PLATE_DETECTOR_WEIGHTS):
        plate_detector = YoloPlateDetector(weights=config.PLATE_DETECTOR_WEIGHTS)
        print(f"Using real YoloPlateDetector ({config.PLATE_DETECTOR_WEIGHTS})")
    else:
        plate_detector = StubPlateDetector()
        print("Real plate-detector weights not found — falling back to StubPlateDetector")
    plate_reader = PaddleOcrPlateReader()

    results = []
    for cid in ids:
        cam = cameras[cid]
        print(f"  [{cid}] connecting...")
        r = scan_camera(cid, cam.rtsp_url, detector, plate_detector, plate_reader, OUTPUT_DIR)
        status = "ok" if r["opened"] else f"FAILED ({r['error']})"
        print(
            f"  [{cid}] {status} — frames={r['frames_read']} vehicles={r['vehicle_detections']} "
            f"localized={r['plate_localized']} read={r['plate_read']}"
        )
        results.append(r)

    totals = {
        "cameras_scanned": len(results),
        "cameras_opened": sum(1 for r in results if r["opened"]),
        "vehicle_detections": sum(r["vehicle_detections"] for r in results),
        "plate_localized": sum(r["plate_localized"] for r in results),
        "plate_read": sum(r["plate_read"] for r in results),
    }
    report = {"run_id": RUN_ID, "seconds_per_camera": SECONDS_PER_CAMERA, "totals": totals, "cameras": results}
    report_path = os.path.join(OUTPUT_DIR, "report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n=== TOTALS ===")
    print(json.dumps(totals, indent=2))
    print(f"\nFull report: {report_path}")
    print(
        "Next: manually open each camera's *_vehicle.jpg / *_platecrop.jpg in "
        f"{OUTPUT_DIR}/<camera_id>/ to confirm whether the plate is actually visible "
        "in the localized crop (ground truth for precision/recall), independent of "
        "whether OCR happened to read it."
    )


if __name__ == "__main__":
    main()
