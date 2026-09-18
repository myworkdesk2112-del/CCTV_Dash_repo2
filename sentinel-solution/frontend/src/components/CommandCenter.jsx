import { memo, useEffect, useState } from "react";
import { api } from "../api";
import MapView from "./MapView";
import { IconCamera, IconCar, IconAlert, IconVehicleSide } from "../icons";
import { clickableProps } from "../a11y";

const POLL_MS = 8000;

const DetectionThumbnail = memo(function DetectionThumbnail({ eventId, hasImage, watchlisted }) {
  const [url, setUrl] = useState(null);

  useEffect(() => {
    let active = true;
    let blobUrl = null;
    if (!hasImage || !eventId) return undefined;

    api.eventCropBlobUrl(eventId).then(
      (nextUrl) => {
        if (!active) { URL.revokeObjectURL(nextUrl); return; }
        blobUrl = nextUrl;
        setUrl(nextUrl);
      },
      () => { if (active) setUrl(null); }
    );
    return () => {
      active = false;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [eventId, hasImage]);

  return <div className={`vehicle-thumb2 ${watchlisted ? "watch2" : ""}`}>{url ? <img src={url} alt="Evidence crop" /> : <IconVehicleSide />}</div>;
});

// Deliberately real-numbers-only: no fabricated "GPU load" / "storage %"
// gauges here — we have no telemetry source for those. Every KPI below
// comes straight from a real endpoint.
export default function CommandCenter({ cameras, health, gapAnalysis, alerts, route, onOpenAlert }) {
  const [recent, setRecent] = useState([]);
  const [recentError, setRecentError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const data = await api.recentDetections(12);
        if (!cancelled) { setRecent(data); setRecentError(null); }
      } catch (err) {
        if (!cancelled) setRecentError(err.message);
      }
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const onlineCount = health?.active_camera_worker_count ?? 0;
  const totalCount = health?.catalogue_size ?? 0;
  const activeAlerts = (alerts || []).filter((a) => (a.status || "new") !== "resolved" && (a.status || "new") !== "dismissed");
  const unhealthyCount = gapAnalysis?.unhealthy?.length ?? 0;

  return (
    <>
      <div className="view-head2">
        <div>
          <h1>Command Center</h1>
          <div className="sub">Statewide operating picture — live from the sandbox catalogue</div>
        </div>
      </div>

      <div className="grid4">
        <div className="card2 kpi-row2">
          <div className="stat-icon2 i-confirmed"><IconCamera /></div>
          <div><div className="kpi2-val" style={{ color: "var(--confirmed)" }}>{onlineCount}</div><div className="kpi2-lbl">Cameras online / {totalCount}</div></div>
        </div>
        <div className="card2 kpi-row2">
          <div className="stat-icon2 i-predicted"><IconCar /></div>
          <div><div className="kpi2-val">{gapAnalysis?.registered_size ?? "—"}</div><div className="kpi2-lbl">Cameras registered (Model 1)</div></div>
        </div>
        <div className="card2 kpi-row2">
          <div className="stat-icon2 i-danger"><IconAlert /></div>
          <div><div className="kpi2-val" style={{ color: "var(--danger)" }}>{activeAlerts.length}</div><div className="kpi2-lbl">Active alerts</div></div>
        </div>
        <div className="card2 kpi-row2">
          <div className="stat-icon2 i-accent"><IconAlert /></div>
          <div><div className="kpi2-val">{unhealthyCount}</div><div className="kpi2-lbl">Unhealthy cameras</div></div>
        </div>
      </div>

      <div className="cols2">
        <div className="card2" style={{ padding: 0 }}>
          <div className="mapwrap2">
            <div className="map-legend2">
              <span className="legend-item2"><span className="legend-swatch2" style={{ background: "var(--confirmed)" }} />Confirmed</span>
              <span className="legend-item2"><span className="legend-swatch2" style={{ background: "var(--inferred)" }} />Inferred</span>
              <span className="legend-item2"><span className="legend-swatch2" style={{ background: "var(--predicted)" }} />Predicted</span>
              <span className="legend-item2"><span className="legend-swatch2" style={{ background: "var(--danger)" }} />Alert</span>
            </div>
            <MapView cameras={cameras} route={route} />
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="card2">
            <div className="card-h2"><h2>Recent detections</h2><span className="n">live, polled 8s</span></div>
            {recentError && <p style={{ color: "var(--danger)", fontSize: 11 }}>{recentError}</p>}
            {!recent.length && !recentError && <p style={{ color: "var(--text-dim)", fontSize: 11 }}>No detections yet — the pipeline logs a sighting once a real vehicle is processed on a live camera.</p>}
            {recent.map((r) => (
              <div className="detectrow2" key={r.event_id}>
                <DetectionThumbnail key={`${r.event_id}-${r.has_evidence_image}`} eventId={r.event_id} hasImage={r.has_evidence_image} watchlisted={r.watchlisted} />
                <div className="info2">
                  <div className="plate2">{r.plate || `${r.color || "?"} ${r.vehicle_type || "vehicle"}`}</div>
                  <div className="meta2">{new Date(r.observed_at).toLocaleTimeString()} · {r.camera_id}{r.location ? ` · ${r.location}` : ""}</div>
                </div>
                {r.watchlisted && <span className="state-badge" style={{ color: "var(--danger)", background: "var(--danger-bg)" }}>Watchlist</span>}
              </div>
            ))}
          </div>

          {activeAlerts[0] && (
            <div className="card2">
              <div className="card-h2"><h2>Live alert</h2></div>
              <div className="alert-item alert-item--new" style={{ cursor: "pointer" }} {...clickableProps(() => onOpenAlert?.())}>
                <div>
                  <strong>{activeAlerts[0].plate}</strong> at <strong>{activeAlerts[0].camera_id}</strong>
                  <div className="alert-item__reason">{activeAlerts[0].reason}</div>
                  <div className="alert-item__time">{new Date(activeAlerts[0].created_at).toLocaleString()}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
