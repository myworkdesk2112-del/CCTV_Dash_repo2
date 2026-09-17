# Backend Code Review — 2026-09-17

Full read-through of `sentinel-solution/backend/app/` (43 files, ~6,480
lines) looking for concrete bugs — not style/cleanup. Three review passes
covered `analytics/`, `api/`, and `db/`+`streaming/`+`watchlist/`+top-level
files respectively. All fixes below were applied and the full backend test
suite (`python -m pytest tests -q`) passed — **162 passed, 0 failed** —
after every change. AUTOMATED-TEST VERIFIED, not field-tested against live
camera streams.

## Fixed

| # | File | Severity | Issue | Fix |
|---|---|---|---|---|
| 1 | `analytics/tracker.py` | HIGH (crash) | `Track` was a plain `@dataclass`, so its auto-generated `__eq__` tuple-compares every field including `best_crop: Optional[np.ndarray]`. `pop_expired()`'s `t not in expired` membership check falls through to `__eq__` for any non-identical object, and comparing two same-shaped numpy crops raises `ValueError: truth value of an array with more than one element is ambiguous`. This crashes `AnalyticsPipeline.process()` for that camera whenever two same-shaped-crop tracks are active at once — a common case (same-class vehicles produce similarly-sized bbox crops). | `@dataclass(eq=False)` — `Track` has no legitimate value-equality use, only the identity-based membership check that motivated the bug. Confirmed via grep: the only place `Track` instances are compared is that one `not in` check. |
| 2 | `analytics/identity.py` | LOW | `if plate_confidence and (...)` used truthiness, so a legitimate `plate_confidence == 0.0` would never update `existing.plate_confidence`. Currently unreachable (pipeline.py suppresses reads below `PLATE_MIN_CONFIDENCE` before this is called) but wrong on its own terms. | `if plate_confidence is not None and (...)`. |
| 3 | `api/routes_vehicle.py` | LOW | `_explain_link`'s `temporal_consistency` was only floor-clamped (`max(0.0, ...)`), so a negative `link_time_gap_s` (clock skew / out-of-order write) could push it above `1.0` inside a field presented to investigators as a 0–1 confidence component of `fused_score`. | Added the missing ceiling: `min(1.0, max(0.0, ...))`. |
| 4 | `api/routes_vehicle.py`, `api/routes_alerts.py` | HIGH (data exposure) | `recent_detections`/`list_alerts` passed a client-supplied `limit` straight into `.limit()` with no bound. SQLite treats a negative `LIMIT` as "no limit" — `?limit=-1` returns the entire table to any authenticated viewer, violating this project's own scale-aware/no-unbounded-fetch rule (§24.12). | Clamped with the pattern already used elsewhere in this codebase: `min(max(limit, 1), 500)`. |
| 5 | `api/routes_admin.py` | MEDIUM | `list_audit_log` clamped only the upper bound (`min(limit, 500)`), missing the floor clamp that `density_windows` in the same file already has. | Matched the existing `min(max(limit, 1), 500)` pattern. |
| 6 | `api/routes_cameras.py` | MEDIUM | `camera_audit_log` had no limit at all (`.all()`) — a camera onboarded/edited many times returns an ever-growing unpaginated list. | Added a defensive `.limit(2000)`. |
| 7 | `api/routes_watchlist.py` | MEDIUM | `list_watchlist` had no limit/pagination — fine at pilot scale, won't scale. | Added ordering + a defensive `.limit(5000)`. |
| 8 | `streaming/manager.py` | MEDIUM (race condition) | `reconcile()` popped `_analytics_health`/`_frame_counters` entries for a stopped camera **before** `worker.stop()` had joined that camera's thread. An in-flight `_handle_frame` callback (unlocked `setdefault`) could resurrect the entry after `reconcile()` believed it was cleaned up — no future reconcile pass will ever pop it again, a small permanent per-camera-restart leak plus an unlocked-mutation race against the locked reads in `health_snapshot()`. | Moved the pop to *after* `worker.stop()` returns (thread already joined, no more frames possible), under the lock. |
| 9 | `catalogue.py` | MEDIUM (scoping gap) | `DEMO_CAMERA_SCOPE` filtering was applied on the sandbox-HTTP catalogue path but **not** on the ONVIF-discovery path — if ONVIF discovery is enabled while recording the scoped own-feed demo video, any other ONVIF device on the LAN would appear live in the catalogue, breaking the scoping guarantee `config.py` documents. | Applied the same `DEMO_CAMERA_SCOPE` filter to ONVIF-discovered cameras before they replace `self._cameras`. |

## Investigated, not a bug (false positive from the initial pass)

- **`api/routes_vehicle.py` — possible `None` camera passed to `rank_candidate_cameras`.** Confirmed in `analytics/geo.py`'s own docstring and implementation that `last_camera=None` is an explicitly handled, tested case (returns an empty, honestly-noted candidate list) — not a null-pointer risk.

## Reviewed, no issues found

`auth.py`, `deps.py`, `rate_limit.py`, `routes_stream.py` (SSRF guard on the HLS segment proxy is correctly host-restricted), `routes_admin.py`'s RBAC, `routes_cameras.py`'s department scoping, `routes_federation.py`, `anomaly.py`, `evidence_class.py`, `geo.py`, `anpr.py`, `anpr_suitability.py`, `attributes.py`, `density.py`, `federation.py`, `reid.py`, `plate_detector.py`, `pipeline.py`, `db/models.py`, `db/retention.py`, `db/session.py`'s additive-migration logic, `rtsp_client.py`'s PTS/discontinuity/backoff handling, `onvif_discovery.py`'s SSRF guards, `watchlist/service.py`, `external_camera_source.py`, `main.py`. Several of these already carry "found by security/software-engineering review 2026-09-04/05" comments from prior passes — no new authz bypass, credential leak, or evidence-tier bypass found in this pass.

## Not touched

Pervasive `datetime.datetime.utcnow()` deprecation warnings across the codebase (539 warnings in the test run) — cosmetic (Python 3.12 deprecation, not yet removed), not a correctness bug, and fixing every call site is a much larger diff than a bug-fix pass warrants. Flagged here so it doesn't silently disappear from view; a candidate for a dedicated, explicitly-scoped follow-up task.

## Contracts / data

No API response shape changes, no new required parameters, no DB/migration changes. `limit` query parameters now clamp instead of returning unbounded rows — backward compatible for any caller already passing a sane value.

## Verified

`cd sentinel-solution/backend && python -m pytest tests -q` → 162 passed, 0 failed, run after all fixes above.

## Still open

- None of the above were exercised against live camera streams — verified by the test suite and static reasoning only.
- The `datetime.utcnow()` deprecation cleanup (noted above) is deliberately deferred.
