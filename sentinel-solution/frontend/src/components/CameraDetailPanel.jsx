import { memo, useEffect, useRef, useState } from "react";
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

export default function CameraDetailPanel({ cameraId, onClose }) {
  const [data, setData] = useState({ loading: true });
  const panelRef = useRef(null);
  useEffect(() => {
    let active = true;
    Promise.allSettled([api.getCamera(cameraId), api.lastDetection(cameraId), api.cameraStats(cameraId), api.recentDetections(20, cameraId), api.listAlerts(100, cameraId)]).then((results) => {
      if (!active) return;
      const value = (index) => results[index].status === "fulfilled" ? results[index].value : null;
      const error = (index) => results[index].status === "rejected" ? results[index].reason?.message : null;
      setData({ loading: false, camera: value(0), detection: value(1)?.detection, stats: value(2), sightings: value(3), alerts: value(4), analyticsError: error(3) || error(4) });
    });
    return () => { active = false; };
  }, [cameraId]);

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
      </>}
    </section>
  </div>;
}
