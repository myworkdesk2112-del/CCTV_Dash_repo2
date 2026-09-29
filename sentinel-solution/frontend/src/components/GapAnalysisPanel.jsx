import { useEffect, useState } from "react";
import { api } from "../api";

// Model 1 explicitly lists "gap-analysis reporting" as a required
// deliverable (HACKATHON_DETAILS.md §7) — this renders the backend's
// GET /cameras/gap-analysis report (routes_cameras.py) directly, not a
// mocked summary.
export default function GapAnalysisPanel({ onRefresh }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  async function load() {
    try {
      setReport(await api.gapAnalysis());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportPdf() {
    setExporting(true);
    try {
      await api.downloadGapAnalysisPdf();
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  useEffect(() => {
    load();
  }, [onRefresh]);

  if (error) return <p className="gap-analysis__error">{error}</p>;
  if (!report) return <p className="gap-analysis__empty">Loading…</p>;

  return (
    <div className="gap-analysis">
      <h3>Gap analysis</h3>
      <div className="gap-analysis__stats">
        <div><strong>{report.catalogue_size}</strong><span>live in catalogue</span></div>
        <div><strong>{report.registered_size}</strong><span>onboarded</span></div>
      </div>

      <Row label="Live but never onboarded (no metadata)" items={report.live_not_onboarded} tone="warn" />
      <Row label="Onboarded but not currently live" items={report.onboarded_not_live} tone="warn" />
      <Row label="Missing department tag" items={report.missing_department} tone="warn" />
      <Row label="Missing GIS coordinates" items={report.missing_gis_coordinates} tone="warn" />
      <Row label="Missing storage details" items={report.missing_storage_details} tone="warn" />
      <Row label="Confirmed unhealthy" items={report.unhealthy} tone="bad" />
      <Row label="Missing install date" items={report.missing_install_date} tone="warn" />
      <Row label={`Ageing (installed >${report.ageing_threshold_years}y ago)`} items={report.ageing} tone="bad" />

      <h4>Cameras by department</h4>
      <ul className="gap-analysis__dept-list">
        {Object.entries(report.cameras_by_department).map(([dept, count]) => (
          <li key={dept}>
            <span>{dept}</span>
            <strong>{count}</strong>
          </li>
        ))}
        {!Object.keys(report.cameras_by_department).length && <li className="gap-analysis__empty">No cameras onboarded yet.</li>}
      </ul>
      <button onClick={load} className="gap-analysis__refresh">Refresh</button>
      <button onClick={exportPdf} disabled={exporting} className="gap-analysis__refresh">
        {exporting ? "Exporting…" : "Export PDF"}
      </button>
    </div>
  );
}

function Row({ label, items, tone }) {
  return (
    <div className={`gap-analysis__row gap-analysis__row--${tone}`}>
      <span>{label}</span>
      <strong>{items.length}</strong>
      {items.length > 0 && <div className="gap-analysis__row-items">{items.join(", ")}</div>}
    </div>
  );
}
