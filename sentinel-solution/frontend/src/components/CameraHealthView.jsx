import { useMemo, useState } from "react";
import { clickableProps } from "../a11y";

// Operational health ONLY — deliberately separate from ANPR readiness.
// A camera can be perfectly healthy (streaming, stable, online) and still
// be geometrically incapable of reading a plate; conflating the two is
// what makes "camera health" dashboards useless to a department.
//
// Every field below comes from CameraRegistry state that the real RTSP
// worker writes (main.py::_sync_camera_health). No packet-loss, latency,
// bitrate or uptime-percentage figures are shown, because nothing in this
// system measures them and CLAUDE.md forbids fabricating them.

const STATES = ["Healthy", "Degraded", "Offline", "Unknown"];

function healthState(cam) {
  if (cam.is_healthy === true) return "Healthy";
  if (cam.is_healthy === false) return cam.last_seen_live_at ? "Degraded" : "Offline";
  return "Unknown";
}

function stateColor(state) {
  if (state === "Healthy") return "var(--confirmed)";
  if (state === "Degraded") return "var(--warn)";
  if (state === "Offline") return "var(--danger)";
  return "var(--text-dim)";
}

function ago(iso) {
  if (!iso) return "never";
  const secs = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

export default function CameraHealthView({ cameras, onOpenCamera }) {
  const [filter, setFilter] = useState("All");

  const counts = useMemo(() => {
    const c = { Healthy: 0, Degraded: 0, Offline: 0, Unknown: 0 };
    cameras.forEach((cam) => { c[healthState(cam)] += 1; });
    return c;
  }, [cameras]);

  const rows = useMemo(
    () => (filter === "All" ? cameras : cameras.filter((c) => healthState(c) === filter)),
    [cameras, filter]
  );

  return (
    <>
      <div className="view-head2">
        <div>
          <h1>Camera Health</h1>
          <div className="sub">
            Operational stream health from the live RTSP workers. ANPR suitability is a separate
            question — see ANPR Readiness.
          </div>
        </div>
      </div>

      <div className="grid4">
        {STATES.map((s) => (
          <div className="card2 kpi-row2 focusable-row" key={s} style={{ cursor: "pointer" }} {...clickableProps(() => setFilter(s))}>
            <div>
              <div className="kpi2-val" style={{ color: stateColor(s) }}>{counts[s]}</div>
              <div className="kpi2-lbl">{s}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card2">
        <div className="card-h2">
          <h2>Cameras ({rows.length})</h2>
          <div style={{ display: "flex", gap: 6 }}>
            {["All", ...STATES].map((s) => (
              <button
                key={s}
                className="btn2"
                onClick={() => setFilter(s)}
                style={filter === s ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--text-dim)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              <th style={{ padding: "0 10px 8px" }}>Camera</th>
              <th style={{ padding: "0 10px 8px" }}>State</th>
              <th style={{ padding: "0 10px 8px" }}>Department</th>
              <th style={{ padding: "0 10px 8px" }}>Location</th>
              <th style={{ padding: "0 10px 8px" }}>Last live frame</th>
              <th style={{ padding: "0 10px 8px" }}>In catalogue</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((cam) => {
              const state = healthState(cam);
              return (
                <tr
                  key={cam.id}
                  className={onOpenCamera ? "focusable-row" : undefined}
                  style={{ borderBottom: "1px solid var(--border)", cursor: onOpenCamera ? "pointer" : "default" }}
                  {...(onOpenCamera ? clickableProps(() => onOpenCamera(cam.id)) : {})}
                >
                  <td style={{ padding: "10px", fontWeight: 600 }}>{cam.id}</td>
                  <td style={{ padding: "10px", color: stateColor(state), fontWeight: 600 }}>{state}</td>
                  <td style={{ padding: "10px" }}>{cam.department || "—"}</td>
                  <td style={{ padding: "10px" }}>{cam.location || "—"}</td>
                  <td style={{ padding: "10px" }}>{ago(cam.last_seen_live_at)}</td>
                  <td style={{ padding: "10px" }}>{cam.live ? "yes" : "no"}</td>
                </tr>
              );
            })}
            {!rows.length && (
              <tr><td colSpan={6} style={{ padding: 16, color: "var(--text-dim)" }}>No cameras in this state.</td></tr>
            )}
          </tbody>
        </table>

        <p style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 14, lineHeight: 1.6 }}>
          <strong>Degraded</strong> means the camera was live at some point but its worker is not
          currently delivering frames. <strong>Unknown</strong> means it has never been confirmed
          live. Packet loss, latency and bitrate are not shown because this system does not
          measure them.
        </p>
      </div>
    </>
  );
}
