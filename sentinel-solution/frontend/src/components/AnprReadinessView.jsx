import { useEffect, useState } from "react";
import { api } from "../api";
import { clickableProps } from "../a11y";

// Camera ANPR fitness — deliberately a different question from Camera
// Health. A camera can be online, stable and streaming perfectly and still
// be geometrically incapable of producing a plate read; the remediation for
// one is a network/power job and for the other an optics/placement job.
//
// Everything rendered here comes from backend/app/analytics/anpr_suitability.py,
// which computes both measures from persisted real sightings. Nothing on
// this screen is derived in the browser: a verdict computed here could drift
// from the data it describes, and a readiness finding a department acts on
// (moving a camera, buying a lens) has to be reproducible from the API.

const VERDICTS = ["CAPABLE", "MARGINAL", "UNSUITABLE"];

function verdictColor(v) {
  if (v === "CAPABLE") return "var(--confirmed)";
  if (v === "MARGINAL") return "var(--warn)";
  if (v === "UNSUITABLE") return "var(--danger)";
  return "var(--text-dim)";
}

function verdictBg(v) {
  if (v === "CAPABLE") return "var(--confirmed-bg)";
  if (v === "MARGINAL") return "var(--warn-bg)";
  if (v === "UNSUITABLE") return "var(--danger-bg)";
  return "transparent";
}

function VerdictBadge({ verdict, title }) {
  return (
    <span
      className="state-badge"
      style={{ color: verdictColor(verdict), background: verdictBg(verdict), fontWeight: 700 }}
      title={title || undefined}
    >
      {verdict || "NOT ASSESSED"}
    </span>
  );
}

function px(value) {
  return value == null ? "—" : `${Math.round(value)} px`;
}

function pct(value) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

// The basis is the single most important qualifier on this screen: a
// heuristic region bounds the plate rather than being it, so a generous
// measurement from that seam proves nothing. Saying so in the UI is what
// keeps the number from being read as more than it is.
const BASIS_LABEL = {
  upper_bound_region: "upper bound (heuristic region)",
  mixed_upper_bound_region: "upper bound (mixed localiser history)",
  model_localised_plate: "model-localised plate",
};

export default function AnprReadinessView({ onOpenCamera }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("All");
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .anprReadiness()
      .then((result) => { if (!cancelled) { setData(result); setError(null); } })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <>
        <div className="view-head2"><div><h1>ANPR Readiness</h1></div></div>
        <div className="card2"><p style={{ color: "var(--danger)", fontSize: 12.5 }}>{error}</p></div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <div className="view-head2"><div><h1>ANPR Readiness</h1></div></div>
        <div className="card2"><p style={{ color: "var(--text-dim)", fontSize: 12.5 }}>Loading camera fitness…</p></div>
      </>
    );
  }

  const rows = filter === "All"
    ? data.cameras
    : data.cameras.filter((c) => c.anpr_suitability?.classification === filter);

  const t = data.thresholds || {};

  return (
    <>
      <div className="view-head2">
        <div>
          <h1>ANPR Readiness</h1>
          <div className="sub">
            Whether a camera is physically capable of reading a plate — a separate question from
            whether its stream is up. See Camera Health for the latter.
          </div>
        </div>
      </div>

      <div className="grid4">
        {VERDICTS.map((v) => (
          <div
            className="card2 kpi-row2 focusable-row"
            key={v}
            style={{ cursor: "pointer" }}
            {...clickableProps(() => setFilter(v))}
          >
            <div>
              <div className="kpi2-val" style={{ color: verdictColor(v) }}>{data.summary?.[v] ?? 0}</div>
              <div className="kpi2-lbl">{v}</div>
            </div>
          </div>
        ))}
        <div className="card2 kpi-row2">
          <div>
            <div className="kpi2-val" style={{ color: "var(--text-dim)" }}>{data.insufficient_sample ?? 0}</div>
            <div className="kpi2-lbl" title="Counted inside MARGINAL — too little real data to judge yet, not a measured mediocre result.">
              Not enough data
            </div>
          </div>
        </div>
      </div>

      {data.measures_disagree > 0 && (
        <div className="card2" style={{ borderColor: "var(--warn)" }}>
          <p style={{ fontSize: 12.5, margin: 0, lineHeight: 1.6 }}>
            <strong style={{ color: "var(--warn)" }}>{data.measures_disagree} camera(s) disagree between measures.</strong>{" "}
            Each is reading plates at an acceptable rate while its plate-pixel estimate says it should not
            be able to. The observed reads win — they happened. The estimate is what is wrong there,
            most likely because the heuristic region is not landing on the plate.
          </p>
        </div>
      )}

      <div className="card2">
        <div className="card-h2">
          <h2>Cameras ({rows.length})</h2>
          <div style={{ display: "flex", gap: 6 }}>
            {["All", ...VERDICTS].map((v) => (
              <button
                key={v}
                type="button"
                className="btn2"
                onClick={() => setFilter(v)}
                style={filter === v ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--text-dim)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              <th style={{ padding: "0 10px 8px" }}>Camera</th>
              <th style={{ padding: "0 10px 8px" }}>ANPR verdict</th>
              <th style={{ padding: "0 10px 8px" }}>Stream health</th>
              <th style={{ padding: "0 10px 8px" }}>Plate px (width)</th>
              <th style={{ padding: "0 10px 8px" }}>Sightings read</th>
              <th style={{ padding: "0 10px 8px" }}>Department</th>
              <th style={{ padding: "0 10px 8px" }}><span className="sr-only">Expand</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const s = row.anpr_suitability || {};
              const open = expanded === row.camera_id;
              const bounded = (s.geometry_basis || "").includes("upper_bound");
              return [
                <tr
                  key={row.camera_id}
                  className="focusable-row"
                  style={{ borderBottom: open ? "none" : "1px solid var(--border)", cursor: "pointer" }}
                  {...clickableProps(() => setExpanded(open ? null : row.camera_id))}
                >
                  <td style={{ padding: "10px", fontWeight: 600 }}>
                    {row.camera_id}
                    <div style={{ color: "var(--text-dim)", fontWeight: 400, fontSize: 11 }}>{row.location || "Location unknown"}</div>
                  </td>
                  <td style={{ padding: "10px" }}>
                    <VerdictBadge verdict={s.classification} />
                    {s.data_status === "insufficient_sample" && (
                      <div style={{ color: "var(--text-dim)", fontSize: 10.5, marginTop: 3 }}>not enough data</div>
                    )}
                  </td>
                  <td style={{ padding: "10px", color: row.is_healthy === false ? "var(--danger)" : "var(--text-h)" }}>
                    {row.is_healthy === true ? "Healthy" : row.is_healthy === false ? "Unhealthy" : "Unknown"}
                  </td>
                  <td style={{ padding: "10px" }}>
                    {px(s.plate_region_mean_w_px)}
                    {s.plate_region_mean_w_px != null && (
                      <span style={{ color: "var(--text-dim)", fontSize: 10.5 }}>
                        {bounded ? " (bound)" : ""}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "10px" }}>
                    {s.confirmed_plate_reads ?? 0}/{s.sample_vehicle_events ?? 0}
                    <span style={{ color: "var(--text-dim)" }}> · {pct(s.ocr_success_rate)}</span>
                  </td>
                  <td style={{ padding: "10px" }}>{row.department || "—"}</td>
                  <td style={{ padding: "10px", color: "var(--text-dim)" }}>{open ? "▾" : "▸"}</td>
                </tr>,
                open && (
                  <tr key={`${row.camera_id}-detail`} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td colSpan={7} style={{ padding: "0 10px 14px" }}>
                      <div style={{ background: "var(--accent-bg)", borderRadius: 6, padding: 12 }}>
                        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)", marginBottom: 8 }}>
                          Why this verdict
                        </div>
                        <div className="metarow2">
                          <span>Observed plate reads</span>
                          <b><VerdictBadge verdict={s.read_rate_verdict} /> {s.read_rate_reason}</b>
                        </div>
                        <div className="metarow2">
                          <span>Plate-pixel geometry</span>
                          <b>
                            <VerdictBadge verdict={s.geometry_verdict} />{" "}
                            {s.geometry_reason || "No plate region was ever recorded for this camera."}
                          </b>
                        </div>
                        <div className="metarow2">
                          <span>Measurement basis</span>
                          <b>{BASIS_LABEL[s.geometry_basis] || "not measured"}{s.geometry_samples ? ` · ${s.geometry_samples} sighting(s)` : ""}</b>
                        </div>
                        <div className="metarow2">
                          <span>Frame-level OCR yield</span>
                          <b>
                            {s.frame_ocr_attempts
                              ? `${s.frame_ocr_reads} valid reads from ${s.frame_ocr_attempts} OCR attempts (${pct(s.frame_ocr_yield)})`
                              : "not recorded for this camera's sightings"}
                          </b>
                        </div>
                        <div className="metarow2">
                          <span>Plate region (mean w × h)</span>
                          <b>{px(s.plate_region_mean_w_px)} × {px(s.plate_region_mean_h_px)} · best {px(s.plate_region_max_w_px)}</b>
                        </div>
                        <div className="metarow2">
                          <span>Not measured anywhere</span>
                          <b style={{ color: "var(--text-dim)", fontWeight: 400 }}>{(s.unmeasured_factors || []).join(", ")}</b>
                        </div>
                        <div className="metarow2" style={{ borderBottom: "none" }}>
                          <span>Recommended action</span>
                          <b>{s.recommendation}</b>
                        </div>
                        {onOpenCamera && (
                          <button type="button" className="btn2" style={{ marginTop: 10 }} onClick={() => onOpenCamera(row.camera_id)}>
                            Open camera
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ),
              ];
            })}
            {!rows.length && (
              <tr><td colSpan={7} style={{ padding: 16, color: "var(--text-dim)" }}>No cameras with this verdict.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card2">
        <div className="card-h2"><h2>How this is scored</h2></div>
        <p style={{ fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.7, marginTop: 0 }}>{data.method}</p>
        <div className="metarow2">
          <span>Plate width required</span>
          <b>&ge; {t.plate_width_capable_px} px capable · &lt; {t.plate_width_floor_px} px ruled out</b>
        </div>
        <div className="metarow2">
          <span>Read rate required</span>
          <b>&ge; {pct(t.read_rate_capable)} of sightings, over at least {t.minimum_sample_events} sightings</b>
        </div>
        <div className="metarow2">
          <span>Plate-width threshold source</span>
          <b style={{ fontWeight: 400 }}>{t.plate_width_source}</b>
        </div>
        <div className="metarow2" style={{ borderBottom: "none" }}>
          <span>Read-rate threshold source</span>
          <b style={{ fontWeight: 400 }}>{t.read_rate_source}</b>
        </div>
      </div>
    </>
  );
}
