const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// 2026-09-18b (SEC-4, docs/PRODUCTION_MIGRATION_PLAN.md Phase 4): the
// long-lived API key no longer lives in localStorage — a real XSS on
// this app would otherwise be able to read it outright. Auth is now an
// httpOnly session cookie (unreadable by page JS at all) set by
// POST /auth/session/login, plus a separate, deliberately-NOT-httpOnly
// CSRF cookie this file reads and echoes back on every mutating
// request (the standard "double-submit cookie" CSRF pattern — see
// backend/app/api/session_auth.py's docstring for the full rationale).
const CSRF_COOKIE_NAME = "sentinel_csrf";

export function getCsrfToken() {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

// Best-effort "was a session ever established" hint for the UI (e.g.
// deciding whether to show the login form on first paint) — the
// session cookie itself is httpOnly and unreadable here, so this reads
// the CSRF cookie's mere presence instead. It is NOT the source of
// truth for whether the session is actually still valid server-side
// (it could be expired) — api.whoami() remains that source of truth,
// exactly as before this change.
export function hasSessionHint() {
  return Boolean(getCsrfToken());
}

async function login(apiKey) {
  const res = await fetch(`${API_BASE}/auth/session/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) {
    throw new Error(res.status === 401 ? "401 invalid API key" : `${res.status} login failed`);
  }
  return res.json();
}

async function logout() {
  await fetch(`${API_BASE}/auth/session/logout`, { method: "POST", credentials: "include" });
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function withAuth(options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (MUTATING_METHODS.has(method)) {
    const csrf = getCsrfToken();
    if (csrf) headers["X-Sentinel-CSRF-Token"] = csrf;
  }
  return { ...options, method, headers, credentials: "include" };
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, withAuth(options));
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    // FastAPI's `detail` is not always a string. The evidence export gate
    // answers 409 with a structured object ({error, evidence_class, reason,
    // exportable_classes}), and 422 validation errors are an array — both
    // would interpolate as "[object Object]" below and hide the actual
    // reason. Found by calling the live endpoint, not by reading the code.
    if (detail && typeof detail === "object") {
      detail = Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
        : detail.reason || detail.error || JSON.stringify(detail);
    }
    if (res.status === 401) throw new Error("401 not signed in — set an API key above");
    if (res.status === 403) throw new Error(`403 your role can't do this (${detail || "insufficient permissions"})`);
    throw new Error(`${res.status} ${detail || ""}`.trim());
  }
  return res.json();
}

async function downloadBlob(path, filename) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    // Surface the server's own reason rather than a bare status. The
    // evidence certificate route answers 409 with a structured detail
    // explaining WHY an artefact may not be exported (evidence class),
    // and "409 failed to generate file" would hide exactly the
    // explanation the investigator needs.
    let detail;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : body.detail?.reason;
    } catch {
      detail = null;
    }
    throw new Error(`${res.status} ${detail || "failed to generate file"}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const api = {
  base: API_BASE,
  login,
  logout,
  health: () => request("/health"),
  whoami: () => request("/auth/whoami"),
  listCameras: () => request("/cameras"),
  getCamera: (id) => request(`/cameras/${id}`),
  cameraAuditLog: (id) => request(`/cameras/${id}/audit-log`),
  deleteCamera: (id) => request(`/cameras/${id}`, { method: "DELETE" }),
  deregisterCamera: (id, reason) =>
    request(`/cameras/${id}/deregister`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason || null }),
    }),
  reregisterCamera: (id) => request(`/cameras/${id}/register`, { method: "POST" }),
  setCameraMaintenance: (id, underMaintenance, reason, until) =>
    request(`/cameras/${id}/maintenance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        under_maintenance: underMaintenance,
        reason: reason || null,
        until: until || null,
      }),
    }),
  gapAnalysis: () => request("/cameras/gap-analysis"),
  downloadGapAnalysisPdf: () => downloadBlob("/cameras/gap-analysis/export.pdf", "sentinel_gap_analysis.pdf"),
  onboardCamera: (camera) =>
    request("/cameras", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(camera),
    }),
  onboardCamerasBulk: (cameras) =>
    request("/cameras/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cameras),
    }),
  vehicleHistory: (plate, purpose, caseId, { signal } = {}) => {
    const params = new URLSearchParams({ purpose });
    if (caseId) params.set("case_id", caseId);
    return request(`/vehicle/${encodeURIComponent(plate)}/history?${params}`, { signal });
  },
  searchByAttributes: (purpose, { vehicleType, color, partialPlate, caseId, signal } = {}) => {
    const params = new URLSearchParams({ purpose });
    if (vehicleType) params.set("vehicle_type", vehicleType);
    if (color) params.set("color", color);
    if (partialPlate) params.set("partial_plate", partialPlate);
    if (caseId) params.set("case_id", caseId);
    return request(`/vehicle/search-by-attributes?${params}`, { signal });
  },
  listWatchlist: () => request("/watchlist"),
  addWatchlist: (plate, reason) =>
    request("/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plate, reason }),
    }),
  listAlerts: (limit = 100, cameraId) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cameraId) params.set("camera_id", cameraId);
    return request(`/alerts?${params}`);
  },
  ackAlert: (id) => request(`/alerts/${id}/ack`, { method: "POST" }),
  setAlertStatus: (id, status) =>
    request(`/alerts/${id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  hlsUrl: (cameraId) => `${API_BASE}/live/${cameraId}/index.m3u8`,
  whepUrl: (cameraId) => `${API_BASE}/live/${cameraId}/whep`,

  candidateCameras: (plate, purpose, caseId) => {
    const params = new URLSearchParams({ purpose });
    if (caseId) params.set("case_id", caseId);
    return request(`/vehicle/${encodeURIComponent(plate)}/candidate-cameras?${params}`);
  },
  lastDetection: (cameraId) => request(`/cameras/${cameraId}/last-detection`),
  cameraStats: (cameraId) => request(`/cameras/${encodeURIComponent(cameraId)}/stats`),
  eventCropUrl: (eventId) => `${API_BASE}/vehicle/event/${eventId}/crop`,
  // Auth'd image fetch — the session is a cookie, not a header, but an
  // <img src> still can't send credentials by default. Fetch as a blob
  // and hand back an object URL, same shape as before.
  // `purpose`/`caseId` are required by the backend only for a
  // cross-department crop (it is audited against them); harmless otherwise.
  eventCropBlobUrl: async (eventId, { purpose, caseId } = {}) => {
    const params = new URLSearchParams();
    if (purpose) params.set("purpose", purpose);
    if (caseId) params.set("case_id", caseId);
    const qs = params.toString() ? `?${params}` : "";
    const res = await fetch(`${API_BASE}/vehicle/event/${eventId}/crop${qs}`, { credentials: "include" });
    if (!res.ok) throw new Error(`${res.status}`);
    return URL.createObjectURL(await res.blob());
  },
  listApiKeys: () => request("/auth/api-keys"),
  createApiKey: (userId, role, department) =>
    request("/auth/api-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, role, department: department || null }),
    }),
  auditLog: (limit = 200) => request(`/admin/audit-log?limit=${limit}`),
  retentionPolicy: () => request("/admin/retention-policy"),
  triggerPurge: () => request("/admin/purge", { method: "POST" }),
  recentDetections: (limit = 20, cameraId) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cameraId) params.set("camera_id", cameraId);
    return request(`/vehicle/recent?${params}`);
  },

  anprReadiness: (classification) => {
    const params = new URLSearchParams();
    if (classification) params.set("classification", classification);
    const qs = params.toString();
    return request(`/cameras/anpr-readiness${qs ? `?${qs}` : ""}`);
  },

  // Evidence integrity / §63-oriented export (backend/app/api/routes_evidence.py).
  // `verify` is deliberately available for any sighting — checking whether a
  // stored image still matches its write-time hash is an integrity question,
  // not an evidentiary claim. The two export calls are gated server-side on
  // evidence class and answer 409 when the sighting is not CONFIRMED; that
  // refusal is the feature, so callers surface its reason rather than
  // treating it as a generic failure.
  verifyEvidence: (eventId) => request(`/evidence/event/${eventId}/verify`),
  evidencePackage: (eventId, purpose, caseId) => {
    const params = new URLSearchParams({ purpose });
    if (caseId) params.set("case_id", caseId);
    return request(`/evidence/event/${eventId}/package?${params}`);
  },
  downloadEvidenceCertificate: (eventId, purpose, caseId) => {
    const params = new URLSearchParams({ purpose });
    if (caseId) params.set("case_id", caseId);
    return downloadBlob(
      `/evidence/event/${eventId}/certificate.pdf?${params}`,
      `sentinel_evidence_event_${eventId}.pdf`
    );
  },

  federationCorrelations: () => request("/federation/correlations"),
  downloadFederationReportPdf: () =>
    downloadBlob("/federation/correlations/export.pdf", "sentinel_federation_report.pdf"),
};
