const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const API_KEY_STORAGE_KEY = "sentinel_api_key";

export function getApiKey() {
  return localStorage.getItem(API_KEY_STORAGE_KEY) || "";
}

export function setApiKey(key) {
  if (key) localStorage.setItem(API_KEY_STORAGE_KEY, key);
  else localStorage.removeItem(API_KEY_STORAGE_KEY);
}

async function request(path, options = {}) {
  const apiKey = getApiKey();
  const headers = { ...(options.headers || {}) };
  if (apiKey) headers["X-Sentinel-API-Key"] = apiKey;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    if (res.status === 401) throw new Error("401 missing/invalid API key — set one above");
    if (res.status === 403) throw new Error(`403 your role can't do this (${detail || "insufficient permissions"})`);
    throw new Error(`${res.status} ${detail || ""}`.trim());
  }
  return res.json();
}

export const api = {
  base: API_BASE,
  health: () => request("/health"),
  whoami: () => request("/auth/whoami"),
  listCameras: () => request("/cameras"),
  getCamera: (id) => request(`/cameras/${id}`),
  gapAnalysis: () => request("/cameras/gap-analysis"),
  // The API key lives in a custom header, not a cookie, so a plain <a href>
  // download can't authenticate — fetch the PDF as a blob and trigger a
  // client-side download instead.
  downloadGapAnalysisPdf: async () => {
    const apiKey = getApiKey();
    const headers = {};
    if (apiKey) headers["X-Sentinel-API-Key"] = apiKey;
    const res = await fetch(`${API_BASE}/cameras/gap-analysis/export.pdf`, { headers });
    if (!res.ok) throw new Error(`${res.status} failed to generate PDF`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sentinel_gap_analysis.pdf";
    a.click();
    URL.revokeObjectURL(url);
  },
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
  // Auth'd image fetch — API key is a header, not a query param, so an
  // <img src> can't carry it. Fetch as a blob and hand back an object URL.
  eventCropBlobUrl: async (eventId) => {
    const apiKey = getApiKey();
    const res = await fetch(`${API_BASE}/vehicle/event/${eventId}/crop`, {
      headers: apiKey ? { "X-Sentinel-API-Key": apiKey } : {},
    });
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

  federationCorrelations: () => request("/federation/correlations"),
  downloadFederationReportPdf: async () => {
    const apiKey = getApiKey();
    const headers = {};
    if (apiKey) headers["X-Sentinel-API-Key"] = apiKey;
    const res = await fetch(`${API_BASE}/federation/correlations/export.pdf`, { headers });
    if (!res.ok) throw new Error(`${res.status} failed to generate PDF`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sentinel_federation_report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  },
};
