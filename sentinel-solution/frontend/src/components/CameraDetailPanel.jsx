import { memo, useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import EvidenceTierBadge from "./EvidenceTierBadge";

const EvidenceThumbnail = memo(function EvidenceThumbnail({ eventId }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let objectUrl;
    api.eventCropBlobUrl(eventId).then((url) => { objectUrl = url; setSrc(url); }).catch(() => setSrc(null));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [eventId]);
  return src ? <img className="camera-detail-evidence" src={src} alt="Evidence crop from last detection" /> : null;
});

// Admin-only write (backend enforces this — see api/routes_cameras.py's
// set_maintenance_status); a non-admin key gets a readable 403 from the
// shared request() helper rather than the control being hidden client-side,
// matching this app's existing convention (e.g. UserAdminView.jsx) of
// letting the backend be the actual enforcement boundary.
function MaintenanceControl({ cameraId, camera, onChanged }) {
  const [reason, setReason] = useState(camera.maintenance_reason || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function toggle(nextUnderMaintenance) {
    if (nextUnderMaintenance && !reason.trim()) {
      setError("A reason is required to mark this camera under maintenance.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.setCameraMaintenance(cameraId, nextUnderMaintenance, reason.trim() || null, null);
      onChanged(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="camera-detail-section">
      <h3>Maintenance status</h3>
      <p>
        <b>{camera.under_maintenance ? "Under maintenance" : "In service"}</b>
        {camera.under_maintenance && camera.maintenance_reason ? ` — ${camera.maintenance_reason}` : ""}
      </p>
      {camera.under_maintenance ? (
        <button className="btn2" type="button" disabled={busy} onClick={() => toggle(false)}>
          {busy ? "Updating…" : "Clear maintenance"}
        </button>
      ) : (
        <>
          <label htmlFor="maintenance-reason" className="sub">Reason (required to set under maintenance)</label>
          <input
            id="maintenance-reason"
            className="input2"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="e.g. lens damaged, awaiting vendor repair"
          />
          <button className="btn2" type="button" disabled={busy} onClick={() => toggle(true)}>
            {busy ? "Updating…" : "Mark under maintenance"}
          </button>
        </>
      )}
      {error && <p style={{ color: "var(--danger)", fontSize: 11.5, marginTop: 8 }}>{error}</p>}
    </div>
  );
}

// Reversible "decommissioned" flag — distinct from Delete below (which
// drops the row entirely) and from maintenance (temporary, expected back).
// See api/routes_cameras.py's deregister_camera/reregister_camera.
function DeregisterControl({ cameraId, camera, onChanged }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function deregister() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.deregisterCamera(cameraId, reason.trim() || null);
      onChanged(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function reregister() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.reregisterCamera(cameraId);
      onChanged(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="camera-detail-section">
      <h3>Registration status</h3>
      <p>
        <b>{camera.deregistered ? "Deregistered" : "Registered"}</b>
        {camera.deregistered && camera.deregistered_reason ? ` — ${camera.deregistered_reason}` : ""}
      </p>
      {camera.deregistered ? (
        <button className="btn2" type="button" disabled={busy} onClick={reregister}>
          {busy ? "Updating…" : "Re-register"}
        </button>
      ) : (
        <>
          <label htmlFor="deregister-reason" className="sub">Reason (optional — e.g. decommissioned, returned to vendor)</label>
          <input
            id="deregister-reason"
            className="input2"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="e.g. decommissioned, returned to vendor"
          />
          <button className="btn2" type="button" disabled={busy} onClick={deregister}>
            {busy ? "Updating…" : "Deregister"}
          </button>
        </>
      )}
      {error && <p style={{ color: "var(--danger)", fontSize: 11.5, marginTop: 8 }}>{error}</p>}
    </div>
  );
}

// Hard, irreversible delete — distinct from Deregister above (the backend
// refuses this delete outright, 409, if the camera has
// any real VehicleEvent/Alert evidence, see routes_cameras.py's
// delete_camera). Two-step confirm since there's no undo once the backend
// accepts it. Admin-only, same convention as MaintenanceControl above.
function DeleteCameraControl({ cameraId, onDeleted }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function doDelete() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteCamera(cameraId);
      onDeleted();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="camera-detail-section">
      <h3>Delete camera</h3>
      <p className="sub">
        Permanently removes this camera from the registry — irreversible, and refused if it has any
        real vehicle-detection or alert history. Use maintenance status instead for a camera that's
        temporarily out of service.
      </p>
      {confirming ? (
        <>
          <p><b>Delete {cameraId} permanently? This cannot be undone.</b></p>
          <button className="btn2" type="button" disabled={busy} onClick={doDelete}>
            {busy ? "Deleting…" : "Yes, delete permanently"}
          </button>{" "}
          <button className="btn2" type="button" disabled={busy} onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </>
      ) : (
        <button className="btn2" type="button" onClick={() => setConfirming(true)}>
          Delete camera…
        </button>
      )}
      {error && <p style={{ color: "var(--danger)", fontSize: 11.5, marginTop: 8 }}>{error}</p>}
    </div>
  );
}

function AuditTrail({ auditLog, auditLogError }) {
  return (
    <div className="camera-detail-section">
      <h3>Metadata audit trail</h3>
      {auditLog?.length ? (
        <div className="camera-detail-list">
          {auditLog.map((entry) => (
            <div key={entry.id}>
              <b>{entry.action}</b> by {entry.user_id}
              <br />
              <span className="sub">{new Date(entry.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      ) : (
        <p>{auditLogError ? "Audit trail is unavailable for this account (admin-only)." : "No onboarding/edit history recorded for this camera."}</p>
      )}
    </div>
  );
}

export default function CameraDetailPanel({ cameraId, onClose }) {
  const [data, setData] = useState({ loading: true });
  const panelRef = useRef(null);

  const load = useCallback((activeRef) => {
    Promise.allSettled([
      api.getCamera(cameraId),
      api.lastDetection(cameraId),
      api.cameraStats(cameraId),
      api.recentDetections(20, cameraId),
      api.listAlerts(100, cameraId),
      api.cameraAuditLog(cameraId),
    ]).then((results) => {
      if (activeRef && !activeRef.current) return;
      const value = (index) => (results[index].status === "fulfilled" ? results[index].value : null);
      const error = (index) => (results[index].status === "rejected" ? results[index].reason?.message : null);
      setData({
        loading: false,
        camera: value(0),
        detection: value(1)?.detection,
        stats: value(2),
        sightings: value(3),
        alerts: value(4),
        auditLog: value(5),
        auditLogError: error(5),
        analyticsError: error(3) || error(4),
      });
    });
  }, [cameraId]);

  useEffect(() => {
    const activeRef = { current: true };
    setData({ loading: true });
    load(activeRef);
    return () => { activeRef.current = false; };
  }, [cameraId, load]);

  // Focus trap + Escape-to-close: without this, opening the modal leaves
  // keyboard focus on whatever triggered it, so Tab silently keeps
  // cycling through the (now hidden) page behind the dialog instead of
  // its contents.
  useEffect(() => {
    const panel = panelRef.current;
    panel?.focus();
    function onKeyDown(event) {
      if (event.key === "Escape") { onClose(); return; }
      if (event.key !== "Tab" || !panel) return;
      const focusables = panel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const external = data.camera?.source_system && data.camera?.snapshot_image_url;
  return <div className="camera-detail-backdrop" role="presentation" onClick={onClose}>
    <section ref={panelRef} tabIndex={-1} className="camera-detail-panel card2" role="dialog" aria-modal="true" aria-label={`Camera details for ${cameraId}`} onClick={(event) => event.stopPropagation()}>
      <div className="camera-detail-panel__head"><div><h2>{cameraId}</h2><span className="sub">Camera detail</span></div><button className="btn2" onClick={onClose}>Close</button></div>
      {data.loading ? <p className="sub">Loading camera records…</p> : <>
        {data.camera ? <div className="camera-detail-basics"><span><b>Department</b>{data.camera.department || "Unassigned"}</span><span><b>Location</b>{data.camera.location || "Location unknown"}</span><span><b>Health</b>{data.camera.is_healthy === true ? "Healthy" : data.camera.is_healthy === false ? "Unhealthy" : "Unknown"}</span><span><b>ANPR suitability</b>{data.camera.anpr_suitability?.classification || "Not assessed"}</span></div> : <p className="sub">Camera registry details are unavailable for this account.</p>}
        {external ? <div className="camera-detail-section"><h3>Analytics</h3><p>No analytics run on this external source.</p></div> : <>
          <div className="camera-detail-section"><h3>Last real detection</h3>{data.detection ? <div className="camera-detail-detection"><div><b>{data.detection.plate || "No plate read"}</b> · {data.detection.vehicle_type || "vehicle type unknown"} · {data.detection.color || "colour unknown"}<br /><span className="sub">{new Date(data.detection.observed_at).toLocaleString()}{data.detection.plate_confidence != null ? ` · plate confidence ${Math.round(data.detection.plate_confidence * 100)}%` : ""}</span></div>{data.detection.has_evidence_image && <EvidenceThumbnail eventId={data.detection.event_id} />}</div> : <p>No detection recorded for this camera.</p>}</div>
          <div className="camera-detail-section"><h3>Recent sightings (last 24 hours)</h3>{data.stats && <p className="sub">{data.stats.sighting_count}{data.stats.truncated ? "+" : ""} sightings in the bounded 24-hour window · {data.stats.by_evidence_class.CONFIRMED} confirmed · {data.stats.by_evidence_class.PROBABLE} probable · {data.stats.by_evidence_class.LEAD_ONLY} lead only</p>}{data.sightings?.length ? <div className="camera-detail-list">{data.sightings.map((sighting) => <div key={sighting.event_id}><EvidenceTierBadge tier={sighting.evidence_class} /> <b>{sighting.plate || "No plate read"}</b> · {sighting.vehicle_type || "type unknown"} · {sighting.color || "colour unknown"}<br /><span className="sub">{new Date(sighting.observed_at).toLocaleString()}</span></div>)}</div> : <p>{data.analyticsError ? "Recent analytics are unavailable for this account." : "No recent sightings for this camera."}</p>}</div>
          <div className="camera-detail-section"><h3>Watchlist alerts</h3>{data.alerts?.length ? <div className="camera-detail-list">{data.alerts.map((alert) => <div key={alert.id}><b>{alert.reason}</b> · {alert.alert_type} · {alert.status}</div>)}</div> : <p>{data.analyticsError ? "Alerts are unavailable for this account." : "No active alerts for this camera"}</p>}</div>
        </>}
        {data.camera && <MaintenanceControl cameraId={cameraId} camera={data.camera} onChanged={load} />}
        {data.camera && <DeregisterControl cameraId={cameraId} camera={data.camera} onChanged={load} />}
        <AuditTrail auditLog={data.auditLog} auditLogError={data.auditLogError} />
        {data.camera && <DeleteCameraControl cameraId={cameraId} onDeleted={onClose} />}
      </>}
    </section>
  </div>;
}
