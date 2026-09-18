import { memo } from "react";

// Single source of truth for the CONFIRMED / PROBABLE / LEAD_ONLY badge —
// previously defined three times (VehicleTimeline.jsx, CameraDetailPanel.jsx,
// and re-exported for SearchView.jsx to import from VehicleTimeline), which
// meant a future edit to one copy could silently drift from the others.
// CLAUDE.md's "these must never look identical" rule only holds if there's
// exactly one definition. Evidence tier itself always comes from the backend
// (analytics/evidence_class.py) and is never re-derived here — a badge
// computed in the browser could drift from the row it labels.
const TIER = {
  CONFIRMED: {
    label: "CONFIRMED",
    color: "var(--confirmed)",
    bg: "var(--confirmed-bg)",
    title: "Directly evidenced sighting (e.g. plate-confirmed).",
  },
  PROBABLE: {
    label: "PROBABLE",
    color: "var(--warn)",
    bg: "var(--warn-bg)",
    title: "Multiple supporting signals, but still requires investigator verification.",
  },
  LEAD_ONLY: {
    label: "LEAD ONLY",
    color: "var(--danger)",
    bg: "var(--danger-bg)",
    title: "Investigative Lead Only — Low Visual Confidence. Appearance-based match, not a confirmed sighting.",
  },
};

const EvidenceTierBadge = memo(function EvidenceTierBadge({ tier }) {
  const t = TIER[tier] || TIER.LEAD_ONLY;
  return (
    <span
      className="state-badge"
      style={{ color: t.color, background: t.bg, fontWeight: 700 }}
      title={t.title}
    >
      {t.label}
    </span>
  );
});
export default EvidenceTierBadge;
