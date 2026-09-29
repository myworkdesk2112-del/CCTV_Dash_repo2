import {
  IconGrid, IconMap, IconGraph, IconCar, IconCamera, IconAlert, IconEye,
  IconFolder, IconEvidence, IconReport, IconPulse, IconLayers,
  IconSettings, IconShield,
} from "../icons";
import { clickableProps } from "../a11y";

// Grouped by what an operator is trying to DO, not by which model of the
// hackathon spec a feature belongs to — the previous grouping leaked our
// internal Model 1/2/3 structure into an operational product.
//
// `pending: true` marks a destination whose backend does not exist yet. It
// renders an honest "not yet implemented" screen rather than being hidden,
// because a jury asking "where are investigation cases?" should get a
// truthful answer instead of a missing menu entry. ANPR Readiness and
// Evidence Export carried this marker until 2026-09-19 and are now real
// screens; Investigation Cases is the only remaining placeholder.
const NAV = [
  { group: "Operations", items: [
    { id: "command", label: "Command Centre", icon: IconGrid },
    { id: "livemap", label: "State Map", icon: IconMap },
    { id: "livenetwork", label: "Live Network", icon: IconCamera },
  ]},
  { group: "Investigations", items: [
    { id: "vehicle", label: "Vehicle Search", icon: IconCar },
    { id: "graph", label: "Observation Trail", icon: IconGraph, core: true },
    { id: "monitoring", label: "Watchlist & Alerts", icon: IconAlert },
    { id: "cases", label: "Investigation Cases", icon: IconFolder, pending: true },
  ]},
  { group: "Camera Intelligence", items: [
    { id: "network", label: "Camera Registry", icon: IconCamera },
    { id: "health", label: "Camera Health", icon: IconPulse },
    { id: "coverage", label: "Coverage & Gaps", icon: IconMap },
    { id: "anpr", label: "ANPR Readiness", icon: IconEye },
  ]},
  { group: "Evidence", items: [
    { id: "evidence", label: "Evidence Records", icon: IconEvidence },
    { id: "export", label: "Evidence Export", icon: IconReport },
  ]},
  { group: "Integrations", items: [
    { id: "systems", label: "Connected Systems", icon: IconLayers },
    { id: "federation", label: "Integration Monitor", icon: IconGraph },
  ]},
  { group: "Statewide Operations", items: [
    { id: "statewide", label: "Statewide Overview", icon: IconMap },
    { id: "statewide-central", label: "Central Monitoring", icon: IconCamera },
    { id: "statewide-infra", label: "Infrastructure & Scale", icon: IconLayers },
    { id: "statewide-storage", label: "Storage & Retention", icon: IconReport },
    { id: "statewide-dr", label: "Resilience & DR", icon: IconShield },
    { id: "statewide-readiness", label: "Statewide Readiness", icon: IconGraph },
  ]},
  { group: "System", items: [
    { id: "audit", label: "Audit & Governance", icon: IconShield },
    { id: "users", label: "User Administration", icon: IconFolder },
    { id: "reports", label: "Reports", icon: IconReport },
    { id: "architecture", label: "Architecture", icon: IconLayers },
    { id: "runtime", label: "Runtime Health", icon: IconPulse },
    { id: "settings", label: "Settings", icon: IconSettings },
  ]},
];

export default function Sidebar({ view, onNavigate, coverage }) {
  return (
    <nav className="sidebar">
      <div className="brand">
        <div className="brand-mark"><IconShield width={16} height={16} /></div>
        <div>
          <div className="brand-name">SENTINEL</div>
          <div className="brand-tag">Gujarat Police</div>
        </div>
      </div>

      {NAV.map((g) => (
        <div className="navgroup" key={g.group}>
          <div className="navgroup-label">{g.group}</div>
          {g.items.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.id}
                className={`navitem ${view === item.id ? "active" : ""}`}
                aria-current={view === item.id ? "page" : undefined}
                {...clickableProps(() => onNavigate(item.id))}
              >
                <Icon />
                {item.label}
                {item.core && <span className="core-tag">CORE</span>}
                {item.pending && <span className="core-tag pending-tag">SOON</span>}
              </div>
            );
          })}
        </div>
      ))}

      <div className="coverage-box">
        <div className="coverage-title">Camera estate</div>
        <div className="coverage-row"><span>In catalogue</span><b>{coverage?.catalogue_size ?? "—"}</b></div>
        <div className="coverage-row"><span>Onboarded</span><b>{coverage?.registered_size ?? "—"}</b></div>
      </div>
      <div className="sidebar-foot">
        Interoperability &amp; evidence layer<br />Gujarat Police Innovation Challenge 2026
      </div>
    </nav>
  );
}
