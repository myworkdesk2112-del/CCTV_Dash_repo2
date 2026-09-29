import { useState } from "react";
import { api } from "./api";
import { usePolling, useCameraPolling, useAlertPolling, useHealthPolling } from "./hooks/usePolling";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import CommandCenter from "./components/CommandCenter";
import LiveMapView from "./components/LiveMapView";
import LiveNetworkView from "./components/LiveNetworkView";
import GeoTemporalGraph from "./components/GeoTemporalGraph";
import VehicleIntelligence from "./components/VehicleIntelligence";
import CameraNetworkView from "./components/CameraNetworkView";
import CameraDetailPanel from "./components/CameraDetailPanel";
import AlertsView from "./components/AlertsView";
import WatchlistView from "./components/WatchlistView";
import FederationDashboard from "./components/FederationDashboard";
import InvestigationsView from "./components/InvestigationsView";
import EvidenceView from "./components/EvidenceView";
import ReportsView from "./components/ReportsView";
import SystemHealthView from "./components/SystemHealthView";
import ArchitectureView from "./components/ArchitectureView";
import SettingsView from "./components/SettingsView";
import CameraHealthView from "./components/CameraHealthView";
import CoverageGapsView from "./components/CoverageGapsView";
import ConnectedSystemsView from "./components/ConnectedSystemsView";
import MonitoringView from "./components/MonitoringView";
import UserAdminView from "./components/UserAdminView";
import NotImplemented from "./components/NotImplemented";
import StatewideOverview from "./components/StatewideOverview";
import CentralMonitoringView from "./components/CentralMonitoringView";
import InfrastructureScaleView from "./components/InfrastructureScaleView";
import StorageRetentionView from "./components/StorageRetentionView";
import ResilienceDRView from "./components/ResilienceDRView";
import StatewideReadinessView from "./components/StatewideReadinessView";
import AnprReadinessView from "./components/AnprReadinessView";
import EvidenceExportView from "./components/EvidenceExportView";
import "./App.css";

const CAMERA_POLL_MS = 15000;
const ALERT_POLL_MS = 6000;

export default function App() {
  const [view, setView] = useState("command");
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState(null);
  // Separate from selectedCameraId (which only highlights a row/pin): this
  // actually opens the management modal (maintenance/registration/delete/
  // audit trail — see CameraDetailPanel.jsx). Found 2026-09-27: the
  // Registry screen (CameraNetworkView, Model 1's own home) had no path to
  // this modal at all — only a small "i" icon on the unrelated Live
  // Network video-wall screen did, so these real, working controls were
  // effectively unreachable from where a user would actually look for them.
  const [detailCameraId, setDetailCameraId] = useState(null);
  const [vehicleResult, setVehicleResult] = useState(null);
  const [health, setHealth] = useState(null);
  const [gapAnalysis, setGapAnalysis] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [gapRefreshToken, setGapRefreshToken] = useState(0);
  const [pendingPlate, setPendingPlate] = useState("");
  // Owned here, not inside LiveNetworkView, so the operator's video-wall
  // composition survives switching away to check an alert and back —
  // that component unmounts on every view change (see the comment below).
  const [wallSelected, setWallSelected] = useState([]);
  const [wallTileLimit, setWallTileLimit] = useState(4);

  const refreshCameras = useCameraPolling(api, setCameras, CAMERA_POLL_MS, [gapRefreshToken]);
  const refreshGapAnalysis = usePolling(() => api.gapAnalysis(), setGapAnalysis, CAMERA_POLL_MS, [gapRefreshToken]);
  useHealthPolling(api, setHealth, CAMERA_POLL_MS);
  const refreshAlerts = useAlertPolling(api, setAlerts, ALERT_POLL_MS, []);

  const activeAlertCount = alerts.filter((a) => (a.status || "new") !== "resolved" && (a.status || "new") !== "dismissed").length;

  function openGraph(plate) {
    setPendingPlate(plate);
    setView("graph");
  }
  function openVehicle(plate) {
    setPendingPlate(plate);
    setView("vehicle");
  }
  function openCamera(id) {
    setSelectedCameraId(id);
    setView("livemap");
    setDetailCameraId(id);
  }
  function openCameraDetail(id) {
    setSelectedCameraId(id);
    setDetailCameraId(id);
  }

  return (
    <div className="shell">
      <Sidebar view={view} onNavigate={setView} coverage={gapAnalysis} />
      <div className="main-area">
        <Topbar
          health={health}
          activeAlertCount={activeAlertCount}
          onSearchSubmit={openVehicle}
          onAuthenticated={() => {
            refreshCameras();
            refreshGapAnalysis();
            refreshAlerts();
          }}
        />
        {/* Conditional mounting, not always-mounted+CSS-hidden: caught by
            actually running this and watching the network tab — with every
            view mounted at once, all 8+ screens' on-mount data-fetches fired
            simultaneously on page load, before the API key was ever set,
            producing a burst of guaranteed 401s and continuous background
            polling for screens the user never opened. Only the active
            view's component exists in the tree now, matching the original
            app's tab behaviour (and normal React idiom). */}
        <div className="views2">
          <div className="view2 active">
            {view === "command" && <CommandCenter cameras={cameras} health={health} gapAnalysis={gapAnalysis} alerts={alerts} route={vehicleResult?.sightings} onOpenAlert={() => setView("alerts")} />}
            {view === "livemap" && <LiveMapView cameras={cameras} route={vehicleResult?.sightings} selectedCameraId={selectedCameraId} onSelectCamera={openCamera} />}
            {view === "livenetwork" && <LiveNetworkView cameras={cameras} alerts={alerts} selected={wallSelected} setSelected={setWallSelected} tileLimit={wallTileLimit} setTileLimit={setWallTileLimit} />}
            {view === "graph" && <GeoTemporalGraph cameras={cameras} initialPlate={pendingPlate} />}
            {view === "vehicle" && <VehicleIntelligence key={`vehicle-${pendingPlate}`} initialPlate={pendingPlate} onResult={setVehicleResult} onOpenGraph={openGraph} />}
            {view === "network" && (
              <CameraNetworkView
                cameras={cameras}
                gapAnalysis={gapAnalysis}
                selectedCameraId={selectedCameraId}
                onSelectCamera={openCameraDetail}
                gapRefreshToken={gapRefreshToken}
                onOnboarded={() => setGapRefreshToken((n) => n + 1)}
              />
            )}
            {view === "monitoring" && <MonitoringView />}
            {view === "alerts" && <AlertsView />}
            {view === "watchlist" && <WatchlistView />}
            {view === "federation" && <FederationDashboard onOpenPlate={openVehicle} />}
            {view === "audit" && <InvestigationsView />}
            {view === "evidence" && <EvidenceView />}
            {view === "reports" && <ReportsView />}
            {view === "health" && <CameraHealthView cameras={cameras} onOpenCamera={openCamera} />}
            {view === "coverage" && <CoverageGapsView cameras={cameras} />}
            {view === "systems" && <ConnectedSystemsView cameras={cameras} health={health} />}
            {view === "users" && <UserAdminView />}
            {view === "runtime" && <SystemHealthView health={health} gapAnalysis={gapAnalysis} />}
            {view === "architecture" && <ArchitectureView />}
            {view === "settings" && <SettingsView />}
            {view === "statewide" && <StatewideOverview cameras={cameras} health={health} alerts={alerts} onNavigate={setView} />}
            {view === "statewide-central" && <CentralMonitoringView cameras={cameras} health={health} />}
            {view === "statewide-infra" && <InfrastructureScaleView />}
            {view === "statewide-storage" && <StorageRetentionView />}
            {view === "statewide-dr" && <ResilienceDRView />}
            {view === "statewide-readiness" && <StatewideReadinessView />}
            {view === "cases" && (
              <NotImplemented
                title="Investigation Cases"
                sub="Group sightings, alerts and evidence under a named case"
                what="Sentinel already requires a case ID and a stated purpose on every vehicle lookup, and records both in the audit trail — but there is no case entity yet, so cases cannot be listed, reopened, or used to group evidence. Building the screen without that backend would mean inventing case records, which this project does not do."
                requires={[
                  "A Case model plus an additive migration (id, title, owner, status, created_at)",
                  "Linking the existing audit-log purpose/case_id entries to it",
                  "Case-scoped authorization so an investigator sees only their own cases",
                ]}
                related={{ view: "audit", label: "Audit & Governance" }}
                onNavigate={setView}
              />
            )}
            {view === "anpr" && <AnprReadinessView onOpenCamera={openCamera} />}
            {view === "export" && <EvidenceExportView />}
          </div>
        </div>
        {detailCameraId && (
          <CameraDetailPanel cameraId={detailCameraId} onClose={() => setDetailCameraId(null)} />
        )}
      </div>
    </div>
  );
}
