import { memo } from "react";

// Shared LIVE / PILOT / DESIGN TARGET badge for every Model 4 screen —
// one definition so the three meanings stay visually consistent instead of
// each screen inventing its own colour convention.
//
//   LIVE          = backed by a real current endpoint/runtime
//   PILOT         = real functionality, validated only at hackathon scale
//   DESIGN TARGET = future production architecture, not currently deployed
//
// A DESIGN TARGET badge must never be swapped for LIVE/PILOT just because a
// screen "looks" more finished with green on it — the badge is the honesty
// contract this whole section depends on.
const KIND = {
  LIVE: { label: "LIVE", color: "var(--confirmed)", bg: "var(--confirmed-bg)" },
  PILOT: { label: "PILOT", color: "var(--warn)", bg: "var(--warn-bg)" },
  DESIGN_TARGET: { label: "DESIGN TARGET", color: "var(--text-dim)", bg: "rgba(107, 118, 132, 0.14)" },
};

const StatusTag = memo(function StatusTag({ kind, style }) {
  const k = KIND[kind] || KIND.DESIGN_TARGET;
  return (
    <span
      className="state-badge"
      style={{ color: k.color, background: k.bg, fontWeight: 700, ...style }}
    >
      {k.label}
    </span>
  );
});
export default StatusTag;
