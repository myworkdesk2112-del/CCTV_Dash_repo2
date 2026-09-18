import EvidenceTierBadge from "./EvidenceTierBadge";

// Renders the vehicle journey as CONFIRMED (OBSERVED) sightings interleaved
// with INFERRED camera-less segments (geo-temporal layer, see
// analytics/geo.py). The visual distinction is the point: a solid marker is
// real camera evidence; a dashed connector is an inference the operator must
// read as such, never as observed fact.
//
// `exportable_as_evidence` below is the backend's decision (analytics/
// evidence_class.py); this component only renders it, never re-derives it.
export default function VehicleTimeline({ sightings, routeSegments, selectedIndex, onSelect, onExport }) {
  if (!sightings?.length) {
    return <p className="timeline__empty">No movement history yet for this vehicle.</p>;
  }

  // Segments are keyed by the (from_camera -> to_camera) pair; find the one
  // bridging sighting i to i+1 (same-camera consecutive pairs have none).
  const segments = routeSegments || [];
  const segmentBetween = (from, to) =>
    segments.find((s) => s.from_camera === from && s.to_camera === to);

  return (
    <ol className="timeline">
      {sightings.map((s, i) => {
        const next = sightings[i + 1];
        const seg = next ? segmentBetween(s.camera_id, next.camera_id) : null;
        return (
          <li key={i} style={{ listStyle: "none" }}>
            <div
              className={`timeline__item ${i === selectedIndex ? "timeline__item--selected" : ""}`}
              onClick={() => onSelect(i)}
            >
              <div className="timeline__marker" />
              <div className="timeline__body">
                <div className="timeline__row">
                  {/* The real "Export as Evidence" button below means this
                      row can't itself be role="button" — a focusable
                      control can't nest another one legibly for a screen
                      reader. This heading is the keyboard-operable
                      equivalent of the row-click, with the mouse
                      convenience kept on the row via onClick above. */}
                  <button
                    type="button"
                    className="timeline__select"
                    aria-pressed={i === selectedIndex}
                    onClick={(e) => { e.stopPropagation(); onSelect(i); }}
                  >
                    {s.camera_id}
                  </button>
                  <span>{new Date(s.observed_at).toLocaleString()}</span>
                </div>
                <div className="timeline__row timeline__row--sub">
                  <EvidenceTierBadge tier={s.evidence_class} />
                  {(s.evidence_class == null || s.evidence_class === "LEAD_ONLY") && (
                    <span style={{ fontSize: 10.5, color: "var(--danger)", fontWeight: 600 }}>
                      Investigative Lead Only — Low Visual Confidence
                    </span>
                  )}
                  <span style={{ fontSize: 10.5, color: "var(--text-dim)" }}>{s.link?.method}</span>
                </div>
                <div className="timeline__row timeline__row--sub">
                  <span>{s.location || "unknown location"}</span>
                  <span>
                    {s.plate_read_at_this_camera ? (
                      <span className="badge badge--plate">plate read (consensus {Math.round((s.plate_confidence || 0) * 100)}%)</span>
                    ) : (
                      <span className="badge badge--anon">anonymous — matched by appearance</span>
                    )}
                  </span>
                </div>
                <div className="timeline__row timeline__row--sub">
                  <span>
                    {s.vehicle_type || "type unknown"} · {s.color || "colour unknown"}
                  </span>
                </div>
                {s.link?.reid_similarity != null && (
                  <div className="timeline__row timeline__row--sub">
                    <span style={{ fontSize: 10.5 }}>
                      link score {s.link.reid_similarity.toFixed(2)}
                      {s.link.time_since_previous_sighting_s != null &&
                        ` · gap ${Math.round(s.link.time_since_previous_sighting_s)}s`}
                    </span>
                  </div>
                )}
                <p style={{ fontSize: 10.5, color: "var(--text-dim)", margin: "6px 0 0", lineHeight: 1.5 }}>
                  {s.evidence_class_reason}
                </p>
                <div style={{ marginTop: 8 }}>
                  <button
                    className="btn2"
                    disabled={!s.exportable_as_evidence}
                    title={
                      s.exportable_as_evidence
                        ? "Export this sighting as evidence"
                        : "Investigative lead requiring human verification — cannot be exported as evidence."
                    }
                    onClick={(e) => { e.stopPropagation(); onExport?.(s); }}
                  >
                    Export as Evidence
                  </button>
                  {!s.exportable_as_evidence && (
                    <span style={{ fontSize: 10.5, color: "var(--text-dim)", marginLeft: 8 }}>
                      Investigative lead requiring human verification.
                    </span>
                  )}
                </div>
              </div>
            </div>
            {seg && (
              <div className={`timeline__inferred ${seg.plausible_direct_drive === false ? "timeline__inferred--implausible" : ""}`}>
                <span className="badge badge--inferred">inferred</span>{" "}
                {seg.distance_km != null ? (
                  <span>
                    ~{seg.distance_km} km · {Math.round(seg.time_gap_s)}s
                    {seg.implied_min_speed_kmh != null && <> · ≥{Math.round(seg.implied_min_speed_kmh)} km/h</>}
                    {seg.plausible_direct_drive === false && <strong> · not a direct drive</strong>}
                  </span>
                ) : (
                  <span>gap inferred from order only (no camera GIS)</span>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
