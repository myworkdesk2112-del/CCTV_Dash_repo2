import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatusTag from "./StatusTag";
import { IconCamera, IconAlert, IconLayers } from "../icons";
import { clickableProps } from "../a11y";

// Model 4 (Central VMS Model) prototype — NOT a Model 4 backend. Every
// number in the "Current Pilot" section below comes from a real endpoint
// this app already calls elsewhere; the "Statewide Target" section is
// SCALABILITY.md's planning arithmetic, rendered as architecture, never as
// a live count. See CLAUDE.md's forbidden-claims list: never show
// "80,000 connected" — only "target scale: ~80,000 cameras".
export default function StatewideOverview({ cameras, health, alerts, onNavigate }) {
  const [federation, setFederation] = useState(null);
  const [expandedDept, setExpandedDept] = useState(null);

  useEffect(() => {
    api.federationCorrelations().then(setFederation).catch(() => {});
  }, []);

  const activeAlerts = (alerts || []).filter(
    (a) => (a.status || "new") !== "resolved" && (a.status || "new") !== "dismissed"
  );

  // State -> Department -> Camera. No "district" field exists anywhere in
  // CameraRegistry today — showing one would mean fabricating statewide
  // locations this pilot's real metadata doesn't have. Department is real
  // (CameraRegistry.department, 5 real values + null for un-set cameras).
  const byDepartment = useMemo(() => {
    const groups = new Map();
    for (const cam of cameras) {
      const dept = cam.department || "Unassigned";
      if (!groups.has(dept)) groups.set(dept, []);
      groups.get(dept).push(cam);
    }
    return [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [cameras]);

  return (
    <>
      <div className="view-head2">
        <div>
          <h1>Statewide Operations</h1>
          <div className="sub">Model 4 prototype / production architecture — not a Model 4 backend</div>
        </div>
      </div>

      {/* ---------- CURRENT PILOT (real values only) ---------- */}
      <div className="card2">
        <div className="card-h2">
          <h2>Current Pilot</h2>
          <StatusTag kind="LIVE" />
        </div>
        <div className="grid4">
          <div className="card2 kpi-row2">
            <div className="stat-icon2 i-confirmed"><IconCamera /></div>
            <div><div className="kpi2-val">{health?.catalogue_size ?? cameras.length}</div><div className="kpi2-lbl">Cameras onboarded</div></div>
          </div>
          <div className="card2 kpi-row2">
            <div className="stat-icon2 i-confirmed"><IconCamera /></div>
            <div><div className="kpi2-val" style={{ color: "var(--confirmed)" }}>{health?.active_camera_worker_count ?? 0}</div><div className="kpi2-lbl">Cameras online</div></div>
          </div>
          <div className="card2 kpi-row2">
            <div className="stat-icon2 i-danger"><IconAlert /></div>
            <div><div className="kpi2-val" style={{ color: "var(--danger)" }}>{activeAlerts.length}</div><div className="kpi2-lbl">Active alerts</div></div>
          </div>
          <div className="card2 kpi-row2">
            <div className="stat-icon2 i-accent"><IconLayers /></div>
            <div><div className="kpi2-val">{federation?.sources_present?.length ?? "—"}</div><div className="kpi2-lbl">Connected systems</div></div>
          </div>
        </div>
        <p style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>
          Every number above is read live from this running backend — nothing here is
          pre-filled or estimated.
        </p>
      </div>

      {/* ---------- State -> Department -> Camera hierarchy ---------- */}
      <div className="card2">
        <div className="card-h2">
          <h2>Registry Hierarchy</h2>
          <StatusTag kind="LIVE" />
        </div>
        <p style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 10 }}>
          Gujarat State → Department → Camera. This pilot's registry has no district-level
          metadata yet, so no district tier is shown — a real production registry would add
          one rather than have this UI invent statewide locations that don't exist.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ fontWeight: 700, fontSize: 12.5 }}>Gujarat State</div>
          {byDepartment.map(([dept, camList]) => (
            <div key={dept} style={{ marginLeft: 16 }}>
              <div
                className="focusable-row"
                style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", padding: "4px 0", fontSize: 12.5 }}
                aria-expanded={expandedDept === dept}
                {...clickableProps(() => setExpandedDept(expandedDept === dept ? null : dept))}
              >
                <span style={{ color: "var(--text-dim)" }}>{expandedDept === dept ? "▾" : "▸"}</span>
                <strong>{dept}</strong>
                <span style={{ color: "var(--text-dim)" }}>({camList.length} camera{camList.length === 1 ? "" : "s"})</span>
              </div>
              {expandedDept === dept && (
                <div style={{ marginLeft: 24, display: "flex", flexDirection: "column", gap: 2 }}>
                  {camList.map((cam) => (
                    <div key={cam.id} style={{ fontSize: 12, color: "var(--text-dim)", display: "flex", gap: 8 }}>
                      <span style={{ color: cam.is_healthy ? "var(--confirmed)" : "var(--danger)" }} title={cam.is_healthy ? "healthy" : "unhealthy"} aria-hidden="true">●</span>
                      <span className="sr-only">{cam.is_healthy ? "healthy" : "unhealthy"}</span>
                      <span>{cam.id}</span>
                      <span>— {cam.location || "unknown location"}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {!cameras.length && <p style={{ color: "var(--text-dim)", fontSize: 12 }}>No cameras onboarded yet.</p>}
        </div>
      </div>

      {/* ---------- STATEWIDE TARGET (design only) ---------- */}
      <div className="card2" style={{ borderColor: "var(--border-strong)" }}>
        <div className="card-h2">
          <h2>Statewide Target</h2>
          <StatusTag kind="DESIGN_TARGET" />
        </div>
        <p style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 10 }}>
          The hackathon's own theme statement: unify CCTV from 26 departments, ~80,000
          cameras statewide. Nothing below is deployed — this is the architecture target
          this pilot's code is designed to scale into, documented in SCALABILITY.md.
        </p>
        <div className="grid4">
          <div className="card2 kpi-row2" style={{ opacity: 0.85 }}>
            <div><div className="kpi2-val" style={{ fontSize: 18, color: "var(--text-dim)" }}>~80,000</div><div className="kpi2-lbl">Target scale: cameras</div></div>
          </div>
          <div className="card2 kpi-row2" style={{ opacity: 0.85 }}>
            <div><div className="kpi2-val" style={{ fontSize: 16, color: "var(--text-dim)" }}>Edge / Regional</div><div className="kpi2-lbl">Processing tier</div></div>
          </div>
          <div className="card2 kpi-row2" style={{ opacity: 0.85 }}>
            <div><div className="kpi2-val" style={{ fontSize: 16, color: "var(--text-dim)" }}>Central</div><div className="kpi2-lbl">Control plane</div></div>
          </div>
          <div className="card2 kpi-row2" style={{ opacity: 0.85 }}>
            <div><div className="kpi2-val" style={{ fontSize: 16, color: "var(--text-dim)" }}>Multi-region</div><div className="kpi2-lbl">Storage + HA/DR</div></div>
          </div>
        </div>
      </div>

      <div className="card2">
        <div className="card-h2"><h2>Explore</h2></div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn2" onClick={() => onNavigate?.("statewide-central")}>Central Monitoring</button>
          <button className="btn2" onClick={() => onNavigate?.("statewide-infra")}>Infrastructure & Scale</button>
          <button className="btn2" onClick={() => onNavigate?.("statewide-storage")}>Storage & Retention</button>
          <button className="btn2" onClick={() => onNavigate?.("statewide-dr")}>Resilience & DR</button>
          <button className="btn2" onClick={() => onNavigate?.("statewide-readiness")}>Statewide Readiness</button>
        </div>
      </div>
    </>
  );
}
