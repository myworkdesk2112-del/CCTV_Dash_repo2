# Model 2 — Research Notes

Supporting research for `IMPLEMENTATION_PLAN.md`'s remaining items and
for justifying `ARCHITECTURE.md`'s stack deviations. Compiled 2026-09-11.
Cites real, checkable sources — no fabricated benchmarks.

## Cross-camera Re-ID: HSV-histogram vs. a real embedding model

Our current appearance-similarity signal (`analytics/tracker.py`-adjacent
code) is an HSV colour histogram + grayscale template compared by cosine
similarity. This is genuinely simple compared to production vehicle
re-identification:

- **FastReID** (JDAI-CV, Apache-2.0) and **OSNet** (Zhou et al., omni-scale
  network, originally for person Re-ID but widely adapted to vehicle
  Re-ID on VeRi-776/VehicleID) are the standard open-source deep-Re-ID
  baselines cited in `HLD.md`'s own documented upgrade path (§ future
  work, ~lines 732-737). Both need a labelled or at least large
  unlabelled vehicle-crop dataset to fine-tune meaningfully — something
  this sandbox doesn't have at volume (see below).
- **Why we didn't swap it in this pass:** `scripts/
  calibrate_embedding_threshold.py` (run 2026-09-10 against the real
  accumulated `sentinel.db`, 11,832 crops) found the *recall* side of
  Re-ID evaluation is genuinely blocked regardless of embedding choice —
  only 6 events have both a crop and a plate, 0 plates repeat across
  cameras in the real data, and only 4 identity links were ever
  plate-verified (not appearance-circular). A better embedding can't be
  validated without more cross-camera repeat sightings than the current
  30-camera/short-runtime sandbox produces. Swapping the embedding
  algorithm without the data to validate it would trade a known-simple,
  explainable signal for an equally-unvalidated "better-sounding" one —
  not a clear win under this repo's honesty rules. This is a genuine,
  documented limitation, not a schedule excuse.
- **Precedent for keeping it simple and explainable:** the `HLD.md` §1
  positioning explicitly does not claim novelty in ANPR/tracking itself
  (commercial systems — Staqu, Videonetics, Vehant, Innefu — already do
  ANPR+tracking at scale); the claimed differentiator is the
  **explainable** identity-resolution layer (`link_method`/`link_score`/
  `link_time_gap_s` per event), which a documented-but-simple signal
  supports just as well as an opaque deep embedding would, for a jury
  evaluation that can inspect the reasoning.

## ANPR OCR: PaddleOCR vs. alternatives

`STRATEGY.md` records that PaddleOCR was swapped in over an original
EasyOCR stub plan. PaddleOCR's multi-line-plate + homoglyph-correction
handling (added 2026-09-05, closing a real bug where two-line Indian
plates were read as garbage) is why it stayed — EasyOCR has no equivalent
built-in plate-layout awareness and would have needed the same
line-joining logic hand-rolled on top regardless. No further OCR
migration is recommended; the real remaining gap in the ANPR path is
**consensus voting**, not OCR engine choice, and that was already fixed
2026-09-10 (`consensus_plate()` position-weighted voting).

## Live viewing: HLS vs. WebRTC/WHEP

The suggested stack lists "WebRTC/HLS relay." We implement HLS-via-
authenticated-proxy only. This is a genuine, documented gap (not built
this pass): the sandbox exposes both `cctv.corp8.cloud` (HLS/catalogue)
and `103.250.160.189` (RTSP/WHEP) per `HACKATHON_DETAILS.md` §13a, so
WHEP is reachable in principle. Deferred because HLS already satisfies
the literal "unified viewer"/"video wall" deliverables and a WHEP client
adds a second live-video code path to maintain under time pressure — see
`IMPLEMENTATION_PLAN.md` for a scoped estimate if pursued.

**Latency figures, corrected 2026-09-17 (previously unsourced)**:

- **Untuned/default HLS**: real-world citations put standard HLS
  glass-to-glass latency at **~20–30 seconds**. The "~6–15s" figure this
  document previously stated only holds for a *tuned* configuration
  (short segments, small buffer window) — a legitimate engineering
  assumption, but it should be labeled "tuned HLS," not presented as
  HLS's typical out-of-the-box behavior. [Wowza: HLS latency](https://www.wowza.com/blog/hls-latency-sucks-but-heres-how-to-fix-it), [Mux: reduce live stream latency](https://www.mux.com/docs/guides/reduce-live-stream-latency)
- **WHEP/WebRTC**: "sub-second" is accurate and well-supported — multiple
  2025–2026 sources converge on **200ms–800ms glass-to-glass** for a
  tuned WHIP→WHEP path, p50 <500ms/p95 <1.0s cited as realistic
  production targets. [Cloudflare: WebRTC WHIP/WHEP sub-second](https://blog.cloudflare.com/webrtc-whip-whep-cloudflare-stream/), [AdaptNXT: MediaMTX WHIP/WHEP latency, 4 real deployments](https://www.adaptnxt.com/blogs/mediamtx-whip-whep-latency-benchmarks-4-deployments)
- **Directly relevant named production case**: Wowza documents traffic
  management centers using WebRTC/WHEP specifically to deliver
  sub-second live camera video to operators — the same command-center/
  traffic-monitoring use case this project targets, not a generic
  entertainment-streaming example. [Wowza: Traffic Management Centers use WebRTC](https://www.wowza.com/blog/how-traffic-management-centers-use-webrtc-to-deliver-sub-second-live-video)
- **A lower-effort middle option this document previously missed:
  LL-HLS** (Low-Latency HLS, Apple's published extension) gets standard
  HLS down to **~2–5s** without needing a full WebRTC/WHEP client — a
  smaller change to the existing HLS-based proxy (`routes_stream.py`)
  than standing up a new WebRTC code path. Worth considering as a
  cheaper first step before M2-1's full WHEP build. [Streaming Media: LL-HLS/LL-DASH sub-3s](https://www.streamingmedia.com/Articles/Editorial/Spotlights/Low-latency-streaming-via-CDN-How-to-optimize-LL-HLS-and-LL-DASH-for-sub-3-second-latency-172056.aspx)

## Per-camera homography calibration — real technique, real reference-distance source

`IMPLEMENTATION_PLAN.md`'s M2-2 previously described the fix only as "a
one-time per-camera homography (4 reference points)" with no cited
technique. Researched 2026-09-17:

- **Standard technique**: planar-homography ground-plane calibration —
  well-established in traffic-vision literature. A fixed camera's
  road-plane pixels are mapped to real-world metric coordinates via a
  homography matrix fit from ≥4 known image↔ground-plane point
  correspondences (lane markings, road edges); a tracked vehicle's
  frame-to-frame ground-plane displacement over elapsed time (PTS,
  matching this project's existing timing rule) then gives real-world
  speed. [Robust Automatic Monocular Vehicle Speed Estimation (ICCV 2021)](https://openaccess.thecvf.com/content/ICCV2021/papers/Revaud_Robust_Automatic_Monocular_Vehicle_Speed_Estimation_for_Traffic_Surveillance_ICCV_2021_paper.pdf), [Monocular 3D Vehicle Detection Using Uncalibrated Traffic Cameras through Homography (arXiv)](https://arxiv.org/pdf/2103.15293), [Application of 2D Homography for Traffic Data Collection using CCTV (arXiv 2401.07220)](https://arxiv.org/pdf/2401.07220)
- **OpenCV support**: `cv2.findHomography()` (already a dependency of
  this project via `opencv-python`) computes the perspective-transform
  matrix from ≥4 point pairs — no new dependency needed to implement
  this. [LearnOpenCV homography tutorial](https://learnopencv.com/homography-examples-using-opencv-python-c/), [OpenCV official homography tutorial](https://docs.opencv.org/4.13.0/d1/de0/tutorial_py_feature_homography.html)
- **Real prior work, independently checkable**: "A Multi-Vehicle Speed
  Estimation Framework Using Line-Based Homography Transformation in
  Static Traffic Videos" ([ETASR](https://etasr.com/index.php/ETASR/article/view/19490)); "Detection of 3D Bounding Boxes of
  Vehicles Using Perspective Transformation for Accurate Speed
  Measurement" ([arXiv 2003.13137](https://arxiv.org/pdf/2003.13137)).
- **Accuracy — honestly a wide, condition-dependent spread, not one
  number**: reported errors in the literature range from under ~1.5%
  (a homography-based patent claim) up to ~20.9% mean absolute
  percentage error (a YOLOv2+homography+tracking study), with other work
  reporting 9.7–15.0% MAE. Dominant error drivers, consistently named
  across sources: camera-to-road angle/height, calibration-point
  precision, frame-rate/timestamp precision (this project's PTS-based
  timing is the right foundation to build this on), lens distortion, and
  a vehicle's body not being perfectly planar. **Do not cite a single
  "accuracy" figure if this is built** — state a range with its sources,
  consistent with this project's no-fabricated-precision rule.
- **India-specific reference-distance source, verified real**: **IRC
  086:2018** ("Geometric Design Standards for Urban Roads and Streets"),
  a real, publicly downloadable Indian Roads Congress standard,
  specifies a standard urban lane width of **3.5 m** (3 m for lower-order
  access roads) — a legitimate, citable real-world reference distance for
  calibration points on Indian traffic footage, not an assumption this
  project would otherwise have to invent. [IRC 086:2018 full text (law.resource.org)](https://law.resource.org/pub/in/bis/irc/irc.gov.in.086.2018.pdf)

## ONVIF Profile M and multi-vendor metadata interoperability

ONVIF Profile M (the metadata/analytics conformance profile — vehicle,
license-plate, face metadata) is the real vendor-neutral mechanism a
production Model 2 would use to receive metadata directly from
ONVIF-capable cameras instead of running our own YOLOv8/OCR pipeline on
raw video for every vendor. The sandbox doesn't expose ONVIF device
queries, so this isn't testable here, but it's the correct production
target — cross-referenced with Model 1's `onvif_profile` schema-extra
recommendation (`model-1-registry-gis/IMPLEMENTATION_PLAN.md` Part 2),
so a camera's registry entry could eventually indicate whether our own
pipeline is even necessary for that specific camera.

## Anomaly detection: precision caveat

`analytics/anomaly.py`'s wrong-way/stopped-in-restricted-zone detectors
use uncalibrated image-plane direction/speed (`direction_deg`,
`speed_px_per_s` on `VehicleEvent` are explicitly documented as
image-plane-only, not real-world units — no camera calibration/homography
is implemented). This is honest by design: the alerts are a real,
opt-in, per-camera signal built on genuinely-computed motion data, but a
"stopped" or "wrong-way" call is relative to the camera's own frame, not
a calibrated ground-plane measurement. Calibrating this per-camera
(homography from known reference points) is a real Model 2 hardening
item if pursued at scale — not attempted this pass, no fabricated
precision numbers exist for it.
