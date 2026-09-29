import { useEffect, useState } from "react";
import { api } from "../api";
import { clickableProps } from "../a11y";
import EvidenceTierBadge from "./EvidenceTierBadge";
import EvidenceViewer from "./EvidenceViewer";

// §63-oriented evidence packaging, wired to backend/app/api/routes_evidence.py.
//
// Three deliberate behaviours this screen must preserve:
//
// 1. The export gate is the SERVER'S, not this component's. The buttons are
//    disabled for a non-CONFIRMED sighting as a courtesy, but the backend
//    answers 409 regardless — a UI that enforced the rule by itself would be
//    one XSS or one stale bundle away from exporting a lead as evidence.
// 2. Purpose and case ID are collected before any artefact is produced, and
//    the backend audit-logs the attempt before it renders anything. This form
//    is the capture point for that, not decoration.
// 3. The integrity result is shown verbatim. NO_HASH_RECORDED is not a
//    failure and must not be coloured like one: it means the row predates
//    write-time hashing, so the guarantee was never established — a different
//    statement from "these bytes changed".

const PURPOSE_MIN_LENGTH = 8; // mirrors routes_evidence.py's _PURPOSE_MIN_LENGTH

function integrityColor(status) {
  if (status === "VERIFIED") return "var(--confirmed)";
  if (status === "NO_HASH_RECORDED") return "var(--text-dim)";
  return "var(--danger)";
}

function eventTier(event) {
  // The backend is the only authority on evidence class; recent_detections
  // already carries it. Falling back to LEAD_ONLY (not CONFIRMED) keeps an
  // unexpected/absent value from being read as the exportable one.
  return event.evidence_class || "LEAD_ONLY";
}

export default function EvidenceExportView() {
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [purpose, setPurpose] = useState("");
  const [caseId, setCaseId] = useState("");
  const [integrity, setIntegrity] = useState(null);
  const [pkg, setPkg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [listError, setListError] = useState(null);

  useEffect(() => {
    api.recentDetections(50).then(setEvents).catch((err) => setListError(err.message));
  }, []);

  // Integrity is checked on selection, before any purpose is typed: it is an
  // integrity question, not an evidentiary claim, and the backend allows it
  // for any evidence class. An investigator should know the image is intact
  // before deciding whether it is worth packaging.
  //
  // The dependent state (previous integrity result, previous package, previous
  // error) is cleared by `selectEvent` below — the event that caused the
  // change — not by this effect, so switching sightings cannot briefly render
  // the previous sighting's verdict against the new one's image.
  useEffect(() => {
    if (!selected) return undefined;
    let cancelled = false;
    api
      .verifyEvidence(selected.event_id)
      .then((result) => { if (!cancelled) setIntegrity(result); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [selected]);

  function selectEvent(event) {
    setSelected(event);
    setIntegrity(null);
    setPkg(null);
    setError(null);
  }

  const purposeOk = purpose.trim().length >= PURPOSE_MIN_LENGTH;
  // Prefer the class the verify call just returned: it was derived from the
  // row server-side a moment ago, while the list entry could be minutes old
  // and, for a plate-upgraded identity, stale.
  const tier = selected ? (integrity?.evidence_class || eventTier(selected)) : null;
  const exportable = tier === "CONFIRMED";
  const canExport = Boolean(selected) && purposeOk && exportable && !busy;

  async function buildPackage() {
    setBusy(true);
    setError(null);
    try {
      setPkg(await api.evidencePackage(selected.event_id, purpose.trim(), caseId.trim() || undefined));
    } catch (err) {
      setError(err.message);
      setPkg(null);
    } finally {
      setBusy(false);
    }
  }

  async function downloadCertificate() {
    setBusy(true);
    setError(null);
    try {
      await api.downloadEvidenceCertificate(selected.event_id, purpose.trim(), caseId.trim() || undefined);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="view-head2">
        <div>
          <h1>Evidence Export</h1>
          <div className="sub">
            Section 63-oriented evidence package for downstream legal review — hash recorded at
            write time, not recomputed at export.
          </div>
        </div>
      </div>

      <div className="cols2">
        <div className="card2" style={{ maxHeight: 620, overflowY: "auto" }}>
          <div className="card-h2"><h2>Recent sightings</h2></div>
          {listError && <p style={{ color: "var(--danger)", fontSize: 11 }}>{listError}</p>}
          {events.map((e) => (
            <div
              key={e.event_id}
              className="detectrow2"
              style={{ cursor: "pointer", background: selected?.event_id === e.event_id ? "var(--accent-bg)" : "transparent" }}
              {...clickableProps(() => selectEvent(e))}
            >
              <div className="info2">
                <div className="plate2">{e.plate || `${e.color || "?"} ${e.vehicle_type || "vehicle"}`}</div>
                <div className="meta2">{new Date(e.observed_at).toLocaleString()} · {e.camera_id}</div>
              </div>
              <EvidenceTierBadge tier={eventTier(e)} />
            </div>
          ))}
          {!events.length && !listError && (
            <p style={{ color: "var(--text-dim)", fontSize: 11.5 }}>No sightings recorded yet.</p>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {!selected && (
            <div className="card2">
              <p style={{ color: "var(--text-dim)", fontSize: 12.5, margin: 0 }}>
                Select a sighting to check its integrity and prepare an evidence package.
              </p>
            </div>
          )}

          {selected && (
            <>
              <EvidenceViewer
                eventId={selected.event_id}
                hasImage={selected.has_evidence_image}
                label={`Evidence · ${selected.camera_id}`}
              />

              <div className="card2">
                <div className="card-h2">
                  <h2>Integrity</h2>
                  <EvidenceTierBadge tier={tier} />
                </div>
                {integrity ? (
                  <>
                    <div className="metarow2">
                      <span>Write-time hash check</span>
                      <b style={{ color: integrityColor(integrity.status) }}>{integrity.status}</b>
                    </div>
                    <div className="metarow2">
                      <span>Hashed at</span>
                      <b>{integrity.hashed_at_write_time ? new Date(integrity.hashed_at_write_time).toLocaleString() : "—"}</b>
                    </div>
                    <div className="metarow2">
                      <span>Recorded hash</span>
                      <b style={{ fontSize: 10, wordBreak: "break-all" }}>{integrity.recorded_sha256 || "—"}</b>
                    </div>
                    <div className="metarow2">
                      <span>Hash now</span>
                      <b style={{ fontSize: 10, wordBreak: "break-all" }}>{integrity.current_sha256 || "—"}</b>
                    </div>
                    <div className="metarow2" style={{ borderBottom: "none" }}>
                      <span>Detail</span>
                      <b style={{ fontWeight: 400 }}>{integrity.reason || "—"}</b>
                    </div>
                  </>
                ) : (
                  <p style={{ color: "var(--text-dim)", fontSize: 12 }}>Checking…</p>
                )}
              </div>

              <div className="card2">
                <div className="card-h2"><h2>Purpose-bound export</h2></div>
                {!exportable && (
                  <p style={{ fontSize: 12.5, color: "var(--danger)", lineHeight: 1.6, marginTop: 0 }}>
                    This sighting is <strong>{tier.replace("_", " ")}</strong> and cannot be exported as
                    evidence. Only a sighting that read and validated its own plate (CONFIRMED) may
                    leave the system in an evidence package. The server enforces this independently
                    of this screen.
                  </p>
                )}
                <label htmlFor="evidence-export-purpose" style={{ display: "block", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)", marginBottom: 4 }}>
                  Purpose (recorded in the audit trail, min {PURPOSE_MIN_LENGTH} characters)
                </label>
                <input
                  id="evidence-export-purpose"
                  className="input2"
                  style={{ width: "100%", marginBottom: 10 }}
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  placeholder="e.g. Hit-and-run investigation, FIR 214/2026"
                />
                <label htmlFor="evidence-export-case-id" style={{ display: "block", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)", marginBottom: 4 }}>
                  Case ID (optional)
                </label>
                <input
                  id="evidence-export-case-id"
                  className="input2"
                  style={{ width: "100%", marginBottom: 12 }}
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                  placeholder="e.g. FIR-214-2026"
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <button type="button" className="btn2" disabled={!canExport} onClick={buildPackage}>
                    {busy ? "Working…" : "Build package"}
                  </button>
                  <button type="button" className="btn2" disabled={!canExport} onClick={downloadCertificate}>
                    Download certificate (PDF)
                  </button>
                </div>
                {!purposeOk && purpose.length > 0 && (
                  <p style={{ fontSize: 11, color: "var(--warn)", marginBottom: 0 }}>
                    A stated purpose has to actually say something — {PURPOSE_MIN_LENGTH} characters minimum.
                  </p>
                )}
                {error && <p style={{ fontSize: 12, color: "var(--danger)", marginBottom: 0 }}>{error}</p>}
              </div>

              {pkg && (
                <div className="card2">
                  <div className="card-h2"><h2>Package · {pkg.schema}</h2></div>
                  <p style={{ fontSize: 11.5, color: "var(--warn)", lineHeight: 1.6, marginTop: 0 }}>
                    {pkg.legal_review_notice}
                  </p>
                  <div className="metarow2"><span>Generated at</span><b>{pkg.generated_at}</b></div>
                  <div className="metarow2"><span>Generated by</span><b>{pkg.generated_by?.user_id} ({pkg.generated_by?.role})</b></div>
                  <div className="metarow2"><span>Purpose</span><b>{pkg.purpose}</b></div>
                  <div className="metarow2"><span>Case ID</span><b>{pkg.case_id || "—"}</b></div>
                  <div className="metarow2"><span>Device</span><b>{pkg.device?.camera_id} · {pkg.device?.owning_department || "unassigned"}</b></div>
                  <div className="metarow2"><span>Observed / ingested</span><b>{pkg.sighting?.observed_at} / {pkg.sighting?.ingested_at}</b></div>
                  <div className="metarow2">
                    <span>Image integrity</span>
                    <b style={{ color: integrityColor(pkg.image?.integrity?.status) }}>{pkg.image?.integrity?.status}</b>
                  </div>
                  <div className="metarow2" style={{ borderBottom: "none" }}>
                    <span>Audit entries</span>
                    <b>{(pkg.access_and_export_audit_trail || []).length}</b>
                  </div>
                  <details style={{ marginTop: 10 }}>
                    <summary style={{ fontSize: 11.5, color: "var(--text-dim)", cursor: "pointer" }}>
                      Production method and full package JSON
                    </summary>
                    <pre style={{ fontSize: 10.5, lineHeight: 1.5, overflowX: "auto", background: "var(--accent-bg)", padding: 10, borderRadius: 6 }}>
                      {JSON.stringify(pkg, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
