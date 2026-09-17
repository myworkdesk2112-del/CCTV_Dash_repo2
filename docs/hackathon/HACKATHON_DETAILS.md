# Gujarat Police Innovation Challenge 2026 ("Sentinel")

Source: https://sentinel.gujarat.gov.in/

## 1. Overview

- **Name:** Gujarat Police Innovation Hackathon 2026 / "Sentinel" / CCTV Integration Hackathon
- **Organizer:** Gujarat Police, Home Department, Government of Gujarat
- **Theme:** Integrated Video Management & Analytics Platform — unify CCTV systems from 26 government departments (~80,000 cameras statewide), correlate live feeds with government databases, and generate AI-powered alerts for law enforcement
- **Total Prize Pool:** ₹51,00,000
- **Venue:** i-Hub Gujarat, Gandhinagar
- **Knowledge Partners:** National Forensic Sciences University (NFSU), Dhirubhai Ambani Institute of Information and Communication Technology (DA-IICT)
- **Tech Partner:** i-Hub Gujarat
- **Official site sections:** Home, About, Prize Money, Resources, Problem Statements & Step-by-Step Guide, Schedule & Venue, FAQs, Contact Us, Sign In, Register

Uniqueness: uses real government CCTV footage (not synthetic/demo data); top solutions are evaluated for actual production deployment, not just demonstration.

## 2. Timeline / Important Dates

| Milestone | Date |
|---|---|
| Registration opens | 4 August 2026 |
| Registration & submission deadline | 28 September 2026 |
| Shortlisting | 28 September 2026 |
| Event / Grand Finale | 12–13 October 2026 |
| Results announced | 13 October 2026 |

(Updated 2026-09-17 — confirmed against the live sentinel.gujarat.gov.in
homepage; deadline moved again from 15 Sep to 28 Sep, event moved from
22–23 Sep to 12–13 Oct. Prior history: originally 7 Sep / event 10–11 Sep,
first moved to 15 Sep / 22–23 Sep as of 2026-09-05. Re-check the live site
before treating this date as final — it has moved twice already.)

## 3. Who Can Participate

- Students (undergrad/postgrad, recognized Indian institutes)
- Researchers and PhD scholars
- DPIIT-registered startups (valid DPIIT Startup Recognition Certificate required at registration/verification)
- Industry professionals and innovators
- Established technology companies
- System integrators
- Both individual and team participation allowed (no stated team-size cap)

### Participant Categories
- **Category 1:** Students, graduates, doctoral scholars, academic/research teams, DPIIT-recognized startups (small & medium)
- **Category 2:** Companies, system integrators, technology providers, LLPs, partnerships, established enterprises (large startups & companies)

## 4. Registration

- **Fee:** Free
- **Process:**
  1. Fill in full name, email address, mobile number
  2. Select participant category (Student/Researcher/Professional, DPIIT Startup, or Company/SI)
  3. Create password (min 8 characters, 1 uppercase, 1 lowercase, 1 digit, 1 special character)
  4. Confirm password
  5. Receive OTP via email for verification
- No specific eligibility documents required at registration stage (DPIIT certificate needed for startup category verification)

## 5. About / Core Objectives

The hackathon challenges participants to design **scalable, secure, interoperable** solutions that:
- Integrate diverse CCTV systems across departments
- Correlate live video feeds with government databases
- Leverage AI-powered video analytics for real-time intelligence and automated alerts

Participants may adopt one of the reference solution models or propose an innovative hybrid architecture.

### Open Source Requirement
All solutions must use open-source technologies. Recommended stack (not mandatory):
- React, Python, Node.js
- PostgreSQL, PostGIS
- WebRTC, RTSP
- Kafka, RabbitMQ
- TensorFlow, PyTorch
- FFmpeg, GStreamer
- Leaflet, OpenLayers

## 6. The Problem in Detail

Gujarat's **26 government departments** each operate independent CCTV ecosystems:
- Mixed analog and IP-based cameras
- Geographically dispersed (~1,000 km, border districts to locations like Valsad, Dahod, Dwarka)
- Heterogeneous vendors, formats, VMS platforms
- Varying storage/retention periods (7–15+ days), cloud or local infrastructure
- No unified way to monitor, search, or cross-reference footage with law-enforcement databases

**Department camera usage examples:**
- Home Department: traffic and crime
- Food & Civil Supplies: storage facilities
- RTO: offices and checkpoints

**Government databases to integrate with:** VAHAN, SARTHI, eGujCop, AFIS, NAFIS (enable automated alerts for stolen vehicles, wanted persons, fingerprint matches)

**Private CCTV integration:** Solution should also support viewing public-facing CCTV from societies, malls, commercial establishments, "wherever feasible and permitted"

**Architecture principles required:** Open, modular, scalable, secure, standards-based, vendor-neutral (avoid lock-in)

## 7. Solution Models (choose one or hybrid; Model 1 is mandatory foundation)

Important: Model 1 should be treated as the common CCTV registry and GIS foundation that may support Models 2, 3, and 4.

### Model 1: Centralised CCTV Registry & GIS Mapping (MANDATORY base layer)
Metadata inventory without centralised video streaming.
- **Features:** Bulk import, API-based onboarding, interactive GIS mapping, health monitoring, gap-analysis reporting, role-based access control
- **Deliverables:** Working registry portal with GIS visualization, bulk/manual onboarding demo, sample metadata dataset, registry API documentation, gap-analysis report
- **Stack:** Leaflet/OpenLayers/PostGIS, Node.js/Python backend, PostgreSQL+PostGIS, React.js frontend, department-wise RBAC
- No video streaming — pair with another model for actual feed integration

### Model 2: Unified Viewing & Metadata Analytics
Aggregates departmental feeds through a single interface without replacing existing infrastructure. Connects directly to departmental systems via RTSP/ONVIF/APIs — no middleware layer.
- **Features:** Feed aggregation via RTSP/ONVIF/APIs, ANPR-based metadata generation, event tagging, searchable vehicle-movement records, configurable video walls, automated alerts
- **Deliverables:** Unified viewer connecting ≥2 different systems, ANPR demonstration, searchable metadata dashboard, architecture note confirming departmental system independence
- **Stack:** WebRTC/HLS relay, ONVIF/RTSP libraries, open-source ANPR models, Node.js/Python microservices, Kafka, Elasticsearch, PostgreSQL

### Model 3: VMS Federation & Middleware Integration
Interoperability layer enabling cross-platform communication while departments retain independent infrastructure. Uses intermediate federation layers (vs. Model 2's direct connection).
- **Features:** Adapter/plugin architecture for multiple vendors, metadata exchange bus, event-correlation engine, unified workflow dashboard, extensible connector framework
- **Deliverables:** Working middleware federating ≥2 systems, unified event-correlation dashboard, adapter architecture documentation, sample federated analytics report
- **Stack:** Node.js/Java Spring Boot middleware, Kafka/RabbitMQ messaging, Kong/NGINX API Gateway, PostgreSQL/Redis, React.js frontend

### Model 4: Central VMS Model
Fully consolidated statewide platform with centralised monitoring, recording, storage, and AI analytics.
- **Features:** Centralised ingestion, tiered storage (hot/warm/cold), ANPR, face recognition, crowd/vehicle counting, anomaly detection, vehicle tracking, database integration readiness, redundancy/disaster recovery/RBAC
- **Deliverables:** Working prototype using multi-department feeds, ANPR and vehicle-tracking demo, scalability/load-test report for ~80,000 cameras, disaster-recovery design, security architecture document
- **Stack:** Custom/open-source VMS, S3-compatible distributed storage/Ceph, Kafka + GPU analytics, PostgreSQL/TimescaleDB, Kubernetes orchestration, high-bandwidth backbone with regional edge support

### Hybrid/Innovative Architecture
Combine elements from two or more models, or submit a fully innovative/customised architecture addressing the stated requirements.

### Solution Design Dimensions (all models)
Architecture, integration strategy, AI/analytics approach (ANPR, cross-camera tracking), cybersecurity/privacy/RBAC, deployment architecture, infrastructure sizing, cost-benefit analysis, scalability roadmap, department-wise information requirements, future roadmap.

## 8. Live Technical Evaluation / Test Case

**Scenario (~50 cameras):**
- Onboard ~50 geographically distributed heterogeneous (simulated) camera feeds from different departments
- Integrate live feeds into your unified platform
- Demonstrate centralised monitoring and AI-powered analytics
- Track a designated vehicle using a registration number provided during evaluation
- Present complete timestamped movement history across the camera network
- Cross-reference live feeds with a representative watchlist database (stolen vehicles, wanted persons, missing persons, blacklisted vehicles)
- Generate automated real-time alerts upon watchlist matches

**Expected output:** Vehicle identification/tracing across the network, complete route traversal with timestamped location-wise movement history, working watchlist database with continuous cross-referencing and automated alerts, evidence of CCTV integration quality, analytics quality, interoperability, scalability, performance.

## 9. Mandatory Submission Deliverables

1. **Solution Presentation (PPT/PDF):** model justification, solution overview/objectives/innovations, high-level architecture and workflows, AI video analytics approach, watchlist correlation/alert methodology, technologies/frameworks/tools, scalability/interoperability/security/deployment considerations, operational benefits
2. **Technical Proposal — High-Level Design (HLD):** overall architecture with component diagrams, heterogeneous camera/NVR/VMS integration approach, live stream ingestion/processing/management architecture, CCTV-to-watchlist correlation and alert-generation methodology, AI analytics technologies (ANPR, FRS, object/person/vehicle tracking), alert workflow with prioritization/visualization, scalability for ~80,000 cameras, technical prerequisites and departmental information requirements
3. **Demonstration on participant's own feed (2–3 min video):** live/recorded feed onboarding and processing, AI detection/analytics (ANPR, facial recognition, etc.), watchlist database correlation, automatic real-time alert generation/visualization — must be a fully functional working solution, no mock-ups
4. **Live Demonstration on Government-Provided CCTV Feed:** successful onboarding onto the platform, live/recorded viewing capability, available video-analytics output, screen-recorded video with output report (detected vehicles/plates with timestamps)
5. **Scalability Strategy (Plan for Scale):** central/regional/edge-compute requirements, GPU/accelerator requirements, network bandwidth planning and low-bandwidth strategies, hot/warm/cold storage assumptions, load balancing/horizontal scaling/monitoring/health checks, high availability/backup/disaster recovery/cybersecurity controls, estimated implementation and operational costs

### Submission Format
- Unlisted YouTube links (visibility: Unlisted)
- Google Drive/OneDrive links (access: "Anyone with link — Viewer")
- Optional: hosted platform URL with test credentials
- Optional: GitHub/GitLab source code repository link

## 10. Evaluation Framework

**Common evaluation areas:**
1. Successful test case (onboarding + operation on government feed with required analytics output)
2. Solution presentation (clarity, completeness, problem understanding, model justification, features)
3. Solution architecture (technical soundness, feasibility, security, interoperability, design clarity)
4. Working platform & demonstration (maturity on participant and government feeds)
5. Video analytics output (quality of ANPR, detection, timestamps, reporting)
6. Scalability & PoC readiness (capability to scale toward ~80,000 cameras, on-site PoC preparedness)
7. Submission completeness (all documents, videos, reports, links, credentials accessible)

**Bonus consideration** (does not offset mandatory requirement non-compliance):
- Innovative hybrid/customized architecture with operational value
- Advanced cross-camera vehicle tracking or multi-camera correlation
- Additional reliable analytics beyond ANPR
- Edge-processing, bandwidth-optimization, low-connectivity operation
- Enhanced cybersecurity, privacy, auditability, or RBAC
- Operational dashboards, automated alerts, health monitoring, integration-ready APIs

Evaluated by Gujarat Police leadership and a technical jury (Phase 2); knowledge partners (NFSU, DA-IICT) provide mentoring/evaluation expertise in AI, computer vision, cybersecurity, digital forensics.

## 11. Format — Two Phases

### Phase 1 — Sandbox Round (₹18,00,000 pool)
Teams integrate solutions with test feeds, competing within their category.

| Position | Category 1 (students/SME) | Category 2 (large startups/companies) |
|---|---|---|
| 1st Prize | ₹4,00,000 | ₹5,00,000 |
| 2nd Prize | ₹2,00,000 | ₹3,00,000 |
| 3rd Prize | ₹1,00,000 | ₹2,00,000 |
| **Subtotal** | **₹7,00,000** | **₹10,00,000** |

- Top 3 teams from each category (6 finalist teams total) advance to the Grand Finale (Phase 2)
- Phase 1 prize money also serves as a grant to support development/refinement of the final solution
- **Consolation Awards:** 4 additional best-performing teams (across both categories) receive ₹25,000 each = ₹1,00,000

### Phase 2 — Production Round / Grand Finale (₹31,00,000 pool)
All 6 finalists integrate solutions with real CCTV feeds at production scale, irrespective of category. Evaluated directly by Gujarat Police leadership and a technical jury.

| Position | Prize |
|---|---|
| 1st Prize (Grand Winner) | ₹16,00,000 |
| 2nd Prize (1st Runner-Up) | ₹8,00,000 |
| 3rd Prize (2nd Runner-Up) | ₹7,00,000 |

### Additional Awards at Production Round (₹2,00,000)
- **Consolation Award:** ₹50,000 each for the 3 finalists outside the top three = ₹1,50,000
- **Special Jury Award:** ₹50,000 (Jury's discretion, for an outstanding aspect of any solution)

### Grand Total Prize Pool
Phase 1 (₹18,00,000) + Phase 2 (₹31,00,000) + Additional Awards (₹2,00,000) = **₹51,00,000**

## 12. Sandbox Dataset & Live Streaming Infrastructure

- **Dataset:** ~12 hours of CCTV footage from each of 30+ cameras, across 5 departments: Health, Police, GSRTC, Panchayat, Municipal Corporation
- Real footage, no synthetic data
- A Python-based middleware ingests recorded footage, synchronizes timelines, and serves it as simulated live video via dedicated streaming endpoints
- Why simulated: realistic integration experience while protecting production security and ensuring consistent, fair testing across teams

## 13. Sandbox Integration Reference — "Consuming the Sentinel Camera Grid"

Guide for teams connecting to the Sentinel sandbox at the protocol layer.

### 13.1 What you are connecting to
Every camera is published as a live RTP/RTSP stream. One second of video takes one second to arrive; frames carry monotonic presentation timestamps (PTS); there is no seeking, no byte-range fetching, no running ahead of real time. Treat each endpoint like a physical camera on an operational network.

| Protocol | Endpoint | Intended for |
|---|---|---|
| RTSP | `rtsp://<host>:8554/stream/<id>` | AI inference (OpenCV, GStreamer, FFmpeg, DeepStream) |
| WebRTC (WHEP) | `http://<host>:8889/stream/<id>/whep` | Low-latency browser preview |
| HLS | `http://<host>/live/stream/<id>/index.m3u8` | Dashboards, mobile, restricted networks |

Always start from the catalogue rather than hard-coding endpoints:
```
curl -s http://<host>/api/ingest
```
Returns every camera with id, location, codec, live status, stream properties, and all three URLs. Camera ids and the set of available cameras can change — the catalogue is the contract, the URL pattern is not.

### 13.2 Connecting — Code Examples

**OpenCV (Python):**
```python
import os
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2

cap = cv2.VideoCapture("rtsp://<host>:8554/stream/1", cv2.CAP_FFMPEG)
while True:
    ok, frame = cap.read()
    if not ok:
        break  # reconnect
    pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
    ...
```

**GStreamer:**
```
gst-launch-1.0 rtspsrc location=rtsp://<host>:8554/stream/1 protocols=tcp latency=200 \
 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! fakesink
```
For H.265 streams, use `rtph265depay` and `h265parse` instead.

**FFmpeg / ffprobe:**
```
ffplay -rtsp_transport tcp rtsp://<host>:8554/stream/1
ffprobe -rtsp_transport tcp rtsp://<host>:8554/stream/1
```

**NVIDIA DeepStream:**
Use `nvurisrcbin` / `uridecodebin` with the RTSP URI and set `select-rtp-protocol=4` (TCP). Streams are H.264 or H.265; both decode on `nvv4l2decoder` without CPU demuxing.

### 13.3 Do's and Don'ts

- **DO — Force RTSP over TCP.** UDP is accepted but fails across NAT and most corporate firewalls; partial UDP delivery produces corrupt frames that look like model bugs. Set `rtsp_transport=tcp` in every client. If port 8554 is blocked, use HLS instead.
- **DON'T — Trust the reported frame rate.** `CAP_PROP_FPS` (and equivalents) often doesn't match actual delivery rate. Measure the real rate yourself, or ignore declared frame rate and use timestamps.
- **DO — Drive all timing from PTS, never arrival time.** Use `CAP_PROP_POS_MSEC` (OpenCV), buffer PTS (GStreamer), or RTP timestamps — not wall-clock time at frame-read moment. On connect, the gateway replays the buffered group-of-pictures so the decoder can start at a keyframe — the first 1-2 seconds may arrive faster than real time. A tracker timestamping by arrival will compute impossible velocities right after connecting. Kalman filters/multi-object trackers must be fed PTS deltas.
- **DON'T — Assume a constant frame rate.** Frame intervals aren't guaranteed uniform. Pipelines must tolerate inter-frame gaps without treating them as disconnects; motion models must use actual elapsed PTS between frames, not a fixed cadence.
- **DO — Reconnect automatically, with backoff.** Feeds are supervised and may restart; expect brief interruptions. Reconnect with exponential backoff (start ~2s, cap ~30s). Do not reconnect in a tight loop.
- **DON'T — Treat decode warnings at join as fatal.** Grid includes H.264 and H.265. Attaching mid-stream can produce messages like "Error constructing the frame RPS" or "Could not find ref with POC" until the first IDR frame arrives — normal, self-corrects. Don't abort on first decoder error.
- **DON'T — Assume a uniform grid.** Cameras differ in resolution, codec, frame rate, bitrate. Read per-camera properties from `/api/ingest` and size batching/buffers/decoders accordingly. A fixed-shape inference batch across every camera won't work unscaled.
- **DO — Expect a scene discontinuity.** Each feed is a continuous recording that loops; at the loop point the scene cuts abruptly, like a camera reboot. Long-lived state (background models, re-id galleries, track ids) should recover from a hard cut rather than assume infinite continuity.
- **DON'T — Plan around obtaining copies of the footage.** No file download. The grid is consumed live only, and that's what evaluation exercises. `/stream/<id>` is the browser playback fallback answering range requests for a media player — pulling it with plain curl/wget yields a partial file that looks complete. Build against a live capture from the start.
- **DON'T — Publish to the gateway.** Consume only. Do not push streams to any path, and do not call the gateway's control API.
- **DO — Pace your load.** Each connected client receives its own copy of the stream. Open only the cameras you're actively processing; close captures when finished.

### 13.4 Pre-submission Checklist
- [ ] Every client forces RTSP over TCP
- [ ] No timing logic depends on `CAP_PROP_FPS` or frame arrival time
- [ ] Inter-frame gaps do not crash or stall the pipeline
- [ ] Reconnect with backoff implemented and tested by restarting a feed
- [ ] Decoder warnings on join are logged, not fatal
- [ ] Camera list and per-camera properties are read from `/api/ingest`
- [ ] Pipeline handles mixed H.264/H.265 and mixed resolutions
- [ ] Behaviour is sane across a scene discontinuity

### 13.5 Support
Report feed problems with: camera id, exact URL, client and version, UTC timestamp, client-side error log. Confirm the camera's live status in `/api/ingest` before reporting it as down.

## 13a. ACTUAL Sandbox Endpoints (Integrator's Guide — authoritative, use these over §13's generic `<host>` examples)

Retrieved from the logged-in Control Room "Integrator's Guide" page, after requesting feed access. This supersedes the placeholder `<host>` values in §13 with real values.

### Access model
- **HLS** is served over the **CDN host** (`cctv.corp8.cloud`), **behind your access password**, and works from any network.
- **RTSP & WebRTC/WHEP** carry raw TCP/UDP media that a CDN cannot proxy, so they are served **directly on the public static IP** `103.250.160.189` (or a dedicated non-proxied subdomain such as `stream.corp8.cloud`).
- RTSP/WHEP are reachable from anywhere the gateway ports are open — **no Tailscale or device registration required**.
- Gateway ports: **8554/TCP** (RTSP), **8889/TCP** (WHEP), **8189/UDP** (WHEP media).
- **Updated (2026-09-04): RTSP & WebRTC/WHEP now authenticate every connection**
  with the registered email + access password embedded directly in the URL:
  `rtsp://<email>:<password>@103.250.160.189:8554/stream/<id>`. The `@` in the
  email **must be percent-encoded as `%40`** (e.g. `alice%40example.com`) or
  URL parsing breaks. Only emails on the approved access list can connect.
  This is separate from the CDN's cookie-session login used for HLS/the
  catalogue (`POST https://cctv.corp8.cloud/auth/login`, which — also
  discovered 2026-09-04 by inspecting the real login form — requires **both**
  `email` and `password` fields, not password alone; sending password alone
  silently re-renders the login page with a 200, not an error).

### Endpoints

| Protocol | Endpoint | Reachable via | Intended for |
|---|---|---|---|
| HLS | `https://cctv.corp8.cloud/<id>/index.m3u8` | Public (password) | Dashboards, mobile, restricted networks, remote AI |
| RTSP | `rtsp://103.250.160.189:8554/stream/<id>` | Public IP (direct) | AI inference (OpenCV, GStreamer, FFmpeg, DeepStream) |
| WebRTC (WHEP) | `http://103.250.160.189:8889/stream/<id>/whep` | Public IP (direct) | Low-latency browser preview |

- `<id>` = camera id, format **`cam01` … `cam30`**
- **Catalogue (real endpoint, replaces the generic `/api/ingest`):**
  ```
  curl -s https://cctv.corp8.cloud/cameras.json
  ```
  Start from this catalogue rather than hard-coding — the camera set can change.

### Connecting — updated code examples

**OpenCV (Python) — HLS (remote) or RTSP (on-network):**
```python
import os, cv2
# HLS (works anywhere with your session):
cap = cv2.VideoCapture("https://cctv.corp8.cloud/cam04/index.m3u8", cv2.CAP_FFMPEG)
# RTSP (direct — force TCP):
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
cap = cv2.VideoCapture("rtsp://103.250.160.189:8554/stream/cam04", cv2.CAP_FFMPEG)
while True:
    ok, frame = cap.read()
    if not ok: break            # reconnect
    pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
```

**GStreamer (RTSP):**
```
gst-launch-1.0 rtspsrc location=rtsp://103.250.160.189:8554/stream/cam04 protocols=tcp latency=200 \
  ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! fakesink
```

**FFmpeg / ffprobe:**
```
ffplay -rtsp_transport tcp rtsp://103.250.160.189:8554/stream/cam04
ffplay https://cctv.corp8.cloud/cam04/index.m3u8
```

### Do's and don'ts (condensed — same substance as §13.3, reconfirmed here)
- Force RTSP over TCP; use HLS if port 8554 is blocked.
- Never trust `CAP_PROP_FPS`; use timestamps for any speed/dwell/time metric.
- Drive timing from PTS, never arrival time (buffered GOP replay on connect can arrive faster than real time).
- Don't assume constant frame rate; tolerate inter-frame gaps.
- Reconnect with exponential backoff (~2s → cap ~30s); never tight-loop.
- Join-time decode warnings (mixed H.264/H.265, "Could not find ref with POC") are normal, not fatal.
- Expect a scene discontinuity at each feed's loop point; long-lived state must recover from the hard cut.
- No file download — the grid is consumed live only; build against live capture from the start.
- Pace your load: each client gets its own stream copy; open only cameras being processed, close when done.

### Pre-submission checklist (updated)
- [ ] RTSP clients force TCP; remote clients use HLS
- [ ] No timing logic depends on `CAP_PROP_FPS` or frame arrival time
- [ ] Inter-frame gaps do not crash or stall the pipeline
- [ ] Reconnect with backoff implemented and tested
- [ ] Decoder warnings on join are logged, not fatal
- [ ] Camera list read from `cameras.json`; mixed H.264/H.265 and resolutions handled
- [ ] Behaviour is sane across a scene discontinuity (loop point)

### Support
Report feed problems with: camera id, exact URL, client + version, UTC timestamp, client-side error log. Confirm the camera's status on the live grid before reporting it down.

## 14. Contact & Links

- **Address:** State Crime Record Bureau (SCRB), Next to Police Bhawan, Sector-18, Gandhinagar, Gujarat 382009
- **Phone:** +91 95370 89982
- **Email:** sentinel.hackathon@gujarat.gov.in
- **Parent site:** https://gujhome.gujarat.gov.in
- **Official hackathon site:** https://sentinel.gujarat.gov.in/
  - Register: https://sentinel.gujarat.gov.in/register
  - Problem Statements: https://sentinel.gujarat.gov.in/problems
  - Prize/Phases: https://sentinel.gujarat.gov.in/phases
  - FAQs: https://sentinel.gujarat.gov.in/faqs
  - Schedule & Venue: https://sentinel.gujarat.gov.in/schedule

## 15. Full FAQ (Q&A)

**Q1: Core Objective?**
Design a secure, scalable, interoperable, cost-effective solution integrating CCTV cameras from 26 Government Departments into one unified platform instead of fragmented systems.

**Q2: Official Website?**
https://sentinel.gujarat.gov.in — central hub for registration, resources, and submissions.

**Q3: Number of Government Departments?**
26 departments currently operate independent CCTV ecosystems.

**Q4: Camera Types?**
Both analog and IP-based cameras, geographically dispersed.

**Q5: Footage Storage?**
Different departments use cloud or local infrastructure with varying retention periods (7–15+ days).

**Q6: Department Camera Usage Examples?**
Home Department: traffic and crime; Food & Civil Supplies: storage facilities; RTO: offices and checkpoints.

**Q7: Private CCTV Integration?**
Yes — should integrate viewing capabilities for public-facing CCTV installed by societies, malls, commercial establishments, when feasible.

**Q8: Government Database Integration?**
VAHAN, SARTHI, eGujCop, AFIS, NAFIS enable automated alerts for stolen vehicles, wanted persons, fingerprint matches.

**Q9: Key Technical Challenges?**
Heterogeneous infrastructure, geographical dispersion (~1,000 km), unified analytics across cameras, scalability requirements.

**Q10: Architecture Principles?**
Open, modular, scalable, secure, standards-based, vendor-neutral — avoiding lock-in.

**Q11: Number of Integration Models?**
Four reference models (1–4) plus hybrid/custom architecture options.

**Q12: Mandatory Model?**
Model 1 (Centralised CCTV Registry & GIS Foundation) is compulsory for all submissions, and must combine with other models.

**Q13: Model 1 Definition?**
A centralized metadata registry with GIS-based mapping for camera onboarding and inventory management.

**Q14: Model 1 Video Streaming?**
No — Model 1 handles metadata only; pair with another model for actual feed integration.

**Q15: Model 1 Key Features?**
Bulk/manual/API onboarding, interactive GIS mapping, camera health monitoring, gap-analysis reports, role-based search.

**Q16: Model 2 Definition?**
"Unified Viewing and Selective Analytics" connecting directly to departmental systems via RTSP, ONVIF, or APIs without intermediate middleware.

**Q17: Model 2 Middleware?**
No middleware layer required; direct integration with each departmental system.

**Q18: Model 3 Definition?**
A middleware layer integrating multiple departmental VMS platforms while departments retain independent infrastructure.

**Q19: Model 3 vs. Model 2?**
Model 3 uses intermediate federation layers; Model 2 connects directly to departmental systems.

**Q20: Model 4 Definition?**
"Central VMS and AI Platform" providing centralized monitoring, recording, storage, and advanced AI analytics across departments.

**Q21: Model 4 Infrastructure?**
Scalable storage, high-bandwidth connectivity, centralized compute, redundancy, cybersecurity controls, large-scale video ingestion capability.

**Q22: Model 4 Analytics?**
ANPR, face recognition, crowd/vehicle counting, anomaly detection, statewide tracking, plus VAHAN/SARTHI/eGujCop/AFIS/NAFIS integration.

**Q23: Custom Architecture?**
Yes — teams may combine elements from two or more models, or submit a fully innovative/customised architecture.

**Q24: Solution Design Dimensions?**
Architecture, integration strategy, AI/analytics approach (ANPR, cross-camera tracking), cybersecurity/privacy/RBAC, deployment architecture, infrastructure sizing, cost-benefit analysis, scalability roadmap.

**Q25: Technology Stack Flexibility?**
Suggested stacks (React, Node.js/Python, PostgreSQL+PostGIS, Kafka, Kubernetes) are references — teams choose their own technologies.

**Q26: Live Test Case?**
Teams onboard ~50 geographically distributed simulated camera feeds from different departments onto their platform for centralized monitoring and analytics.

**Q27: Vehicle-Tracking Challenge?**
A designated vehicle number is provided; teams must track it across multiple camera locations with timestamped movement history.

**Q28: Expected Test Case Output?**
Complete vehicle route traversal, timestamped location-wise movement history, evidence of interoperability and analytics capability.

**Q29: Required Documents?**
Solution Presentation (model, justification, key features) and Technical Proposal/HLD with architecture diagrams and integration approach.

**Q30: HLD Coverage?**
Architecture diagrams; heterogeneous camera/VMS integration; geographic dispersion handling; video analytics (ANPR, tracking); scalability for ~80,000 cameras; department-level technical details.

**Q31: Demonstration Videos?**
Two required: participant's own feed (2–3 min) showing onboarding/viewing/detection, and government-feed demonstration with output report.

**Q32: Mock-ups Accepted?**
No — demonstrations must show actual working software; mock-ups, animations, and concept videos will not be accepted.

**Q33: Government-Feed Demonstration Accompaniment?**
Screen-recorded video plus output report showing detected vehicles/plates with timestamps.

**Q34: Submission Method?**
Unlisted YouTube link, Google Drive/OneDrive with viewer access, hosted platform URL with credentials, or GitHub/GitLab repository.

**Q35: Statewide Scalability Plan (~80,000 cameras)?**
Central/regional/edge compute, GPU capacity, network bandwidth planning, tiered storage, load balancing, horizontal scaling, monitoring, HA/DR, phased rollout.

**Q36: Official Evaluation Areas?**
Test case success, presentation clarity, architecture soundness, platform maturity, analytics output quality, scalability readiness, submission completeness.

**Q37: Bonus Points Impact?**
Bonus consideration may be given for meaningful additional capabilities, but won't offset mandatory requirement non-compliance.

**Q38: Bonus-Earning Features?**
Hybrid architectures, advanced cross-camera tracking, reliable analytics, edge processing, bandwidth optimization, enhanced cybersecurity, operational dashboards, automated alerts.

**Q39: Live Video Dataset?**
Approximately 12 hours of CCTV footage from each of 30+ cameras across Health, Police, GSRTC, Panchayat, and Municipal Corporation departments.

**Q40: Recorded-to-Live Conversion?**
A Python-based middleware ingests recorded footage, synchronizes timelines, and serves it as simulated live video via dedicated streaming endpoints.

**Q41: Why Simulated Streams?**
Provides realistic integration experience while protecting production security and ensuring consistent, fair testing across teams.

**Q42: Official Knowledge Partners?**
National Forensic Sciences University (NFSU) and Dhirubhai Ambani Institute of Information and Communication Technology (DA-IICT).

**Q43: Partner Roles?**
Provide technical expertise, mentoring, and submission evaluation using domain knowledge in AI, computer vision, cybersecurity, digital forensics.

**Q44: Category 1 Eligibility?**
Students, graduates, doctoral scholars, academic/research teams, DPIIT-recognized startups.

**Q45: DPIIT Startup Registration?**
A valid DPIIT Startup Recognition Certificate must be provided at registration or verification.

**Q46: Category 2 Eligibility?**
Companies, system integrators, technology providers, LLPs, partnerships, established enterprises not qualifying as Category 1 startups.

**Q47: Website Capabilities?**
Register for the hackathon; access the official Problem Statement and Solution Framework, datasets, APIs, and reference materials; receive announcements, schedules, and updates; submit required documents/videos/code; view evaluation-related notifications.

**Q48: Overall Hackathon Format?**
Phase 1 – Sandbox Round: teams integrate their solution with the organizer's test feed, competing within their category. The six highest-ranked participants (top 3 per category) qualify for Phase 2. Phase 2 – Production Round (Grand Finale): the six qualifiers demonstrate their solutions using live camera feeds in a production-scale environment.

**Q49: Phase 1 Prize Purpose?**
Prize money serves dual purpose: recognition reward and grant funding for Phase 2 solution development.

**Q50: Total Prize Breakdown?**
₹51,00,000 total — see Section 11 above for full breakdown.

## 16. Notes / Gaps

- No maximum or minimum team-size limit is explicitly stated anywhere on the site.
- No registration fee is mentioned (registration is free).
- Sandbox `<host>` address and live camera credentials are only available after Sign In / Register (not publicly listed).
