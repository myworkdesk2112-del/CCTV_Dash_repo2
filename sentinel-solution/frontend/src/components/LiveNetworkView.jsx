import { useEffect, useMemo, useRef, useState } from "react";
import LiveView from "./LiveView";
import SnapshotView from "./SnapshotView";
import CameraDetailPanel from "./CameraDetailPanel";

const WALL_LAYOUTS = [1, 4, 6, 9];
const HEALTH_STATES = ["healthy", "degraded", "offline", "unknown"];
const HEALTH_LABEL = { healthy: "Healthy", degraded: "Degraded", offline: "Offline", unknown: "Unknown" };
const TOUR_INTERVAL_MS = 20000;

function healthOf(camera) {
  if (camera.analytics_degraded === true) return "degraded";
  if (camera.is_healthy === true) return "healthy";
  if (camera.is_healthy === false) return "offline";
  return "unknown";
}

// Active (non-resolved/dismissed) alerts, matching App.jsx's own definition
// of "active" for the topbar count — kept identical so the tile badge and
// the topbar badge never disagree about what "active" means.
function isActiveAlert(alert) {
  const status = alert.status || "new";
  return status !== "resolved" && status !== "dismissed";
}

// `selected`/`tileLimit`/`setSelected`/`setTileLimit` are owned by App.jsx,
// not this component — the app's conditional-mount navigation (see
// App.jsx's comment on why views aren't all mounted at once) unmounts this
// component every time the operator switches views, so a wall built here
// would otherwise vanish on every trip to check an alert. Lifting just
// these two pieces of state keeps the rest of this view's filter state
// local, since only the wall composition needs to survive navigation.
export default function LiveNetworkView({ cameras, alerts, selected, setSelected, tileLimit, setTileLimit }) {
  const [department, setDepartment] = useState("");
  const [location, setLocation] = useState("");
  const [source, setSource] = useState("");
  const [healthFilter, setHealthFilter] = useState("");
  const [cameraType, setCameraType] = useState("");
  const [query, setQuery] = useState("");
  const [detailCameraId, setDetailCameraId] = useState(null);
  const [dragId, setDragId] = useState(null);
  const [touring, setTouring] = useState(false);
  const [tourIndex, setTourIndex] = useState(0);
  const wallRef = useRef(null);

  const departments = useMemo(() => [...new Set(cameras.map((camera) => camera.department || "Unassigned"))].sort(), [cameras]);
  const cameraTypes = useMemo(() => [...new Set(cameras.map((camera) => camera.camera_type).filter(Boolean))].sort(), [cameras]);
  const locations = useMemo(() => [...new Set(cameras.map((camera) => camera.location).filter(Boolean))].sort(), [cameras]);

  const alertingCameraIds = useMemo(
    () => new Set((alerts || []).filter(isActiveAlert).map((alert) => alert.camera_id)),
    [alerts]
  );

  // Metadata filters minus health — reused both for the main list and for
  // the health-state counts, so "12 healthy" always means "12 healthy among
  // what department/location/etc. already narrowed down", not the whole estate.
  const matchesMetadata = useMemo(() => (camera) => {
    const searchText = `${camera.id} ${camera.location || ""} ${camera.vendor || ""}`.toLowerCase();
    const feedSource = camera.source_system ? "external" : camera.live ? "live" : "offline";
    return (!department || (camera.department || "Unassigned") === department)
      && (!location || camera.location === location)
      && (!source || feedSource === source)
      && (!cameraType || camera.camera_type === cameraType)
      && (!query || searchText.includes(query.toLowerCase()));
  }, [department, location, source, cameraType, query]);

  const metadataFiltered = useMemo(() => cameras.filter(matchesMetadata), [cameras, matchesMetadata]);

  const healthCounts = useMemo(() => {
    const counts = { healthy: 0, degraded: 0, offline: 0, unknown: 0 };
    metadataFiltered.forEach((camera) => { counts[healthOf(camera)] += 1; });
    return counts;
  }, [metadataFiltered]);

  const filteredCameras = useMemo(
    () => metadataFiltered.filter((camera) => !healthFilter || healthOf(camera) === healthFilter),
    [metadataFiltered, healthFilter]
  );
  const viewableCameras = useMemo(() => filteredCameras.filter((camera) => camera.live || camera.snapshot_image_url), [filteredCameras]);
  const viewableById = useMemo(() => Object.fromEntries(viewableCameras.map((camera) => [camera.id, camera])), [viewableCameras]);
  const activeSelected = selected.filter((id) => viewableById[id]);
  const tourPageCount = Math.max(1, Math.ceil(viewableCameras.length / tileLimit));

  const activeFilters = [
    department && { key: "department", label: `Dept: ${department}`, onClear: () => setDepartment("") },
    location && { key: "location", label: `Location: ${location}`, onClear: () => setLocation("") },
    source && { key: "source", label: `Source: ${source}`, onClear: () => setSource("") },
    cameraType && { key: "cameraType", label: `Type: ${cameraType}`, onClear: () => setCameraType("") },
    query && { key: "query", label: `Search: "${query}"`, onClear: () => setQuery("") },
    healthFilter && { key: "healthFilter", label: `Health: ${HEALTH_LABEL[healthFilter]}`, onClear: () => setHealthFilter("") },
  ].filter(Boolean);

  function updateFilter(setter) {
    return (event) => { setter(event.target.value); setSelected([]); };
  }
  function clearAllFilters() {
    setDepartment(""); setLocation(""); setSource(""); setCameraType(""); setQuery(""); setHealthFilter("");
  }
  function toggleHealthFilter(state) {
    setHealthFilter((previous) => (previous === state ? "" : state));
    setSelected([]);
  }
  function toggle(id) {
    setTouring(false);
    setSelected((previous) => {
      const active = previous.filter((cameraId) => viewableById[cameraId]);
      return active.includes(id) ? active.filter((cameraId) => cameraId !== id) : active.length < tileLimit ? [...active, id] : active;
    });
  }
  function setWallLimit(limit) {
    setTileLimit(limit);
    setSelected((previous) => previous.filter((id) => viewableById[id]).slice(0, limit));
  }
  function focusTile(id) {
    setTouring(false);
    setTileLimit(1);
    setSelected([id]);
  }
  // Fills empty tiles up to the current layout size, prioritising cameras
  // with an active alert first — an operator opening the wall cold should
  // see what's alerting before what's merely online.
  function fillWall() {
    setTouring(false);
    setSelected((previous) => {
      const active = previous.filter((id) => viewableById[id]);
      if (active.length >= tileLimit) return active;
      const remaining = viewableCameras
        .map((camera) => camera.id)
        .filter((id) => !active.includes(id))
        .sort((a, b) => Number(alertingCameraIds.has(b)) - Number(alertingCameraIds.has(a)));
      return [...active, ...remaining.slice(0, tileLimit - active.length)];
    });
  }
  function handleDrop(targetId) {
    return (event) => {
      event.preventDefault();
      if (!dragId || dragId === targetId) { setDragId(null); return; }
      setTouring(false);
      setSelected((previous) => {
        const active = previous.filter((id) => viewableById[id]);
        const from = active.indexOf(dragId);
        const to = active.indexOf(targetId);
        if (from === -1 || to === -1) return previous;
        const next = [...active];
        next.splice(from, 1);
        next.splice(to, 0, dragId);
        return next;
      });
      setDragId(null);
    };
  }

  // Tour mode: rotates the wall through the full viewable set in
  // tileLimit-sized pages, so an operator watching e.g. a 4-tile wall can
  // still cycle through 20 cameras unattended instead of only ever seeing
  // the first 4. Any manual action above (toggle/drag/fill/focus) turns
  // touring off, since it would otherwise silently overwrite what the
  // operator just picked a few seconds later.
  useEffect(() => {
    if (!touring || viewableCameras.length === 0) return undefined;
    const pageCount = Math.max(1, Math.ceil(viewableCameras.length / tileLimit));
    const id = setInterval(() => setTourIndex((previous) => (previous + 1) % pageCount), TOUR_INTERVAL_MS);
    return () => clearInterval(id);
  }, [touring, tileLimit, viewableCameras.length]);

  useEffect(() => {
    if (!touring) return;
    const ids = viewableCameras.map((camera) => camera.id);
    if (ids.length === 0) return;
    const pageCount = Math.max(1, Math.ceil(ids.length / tileLimit));
    const page = tourIndex % pageCount;
    setSelected(ids.slice(page * tileLimit, page * tileLimit + tileLimit));
  }, [touring, tourIndex, tileLimit, viewableCameras, setSelected]);

  function toggleTour() {
    setTourIndex(0);
    setTouring((previous) => !previous);
  }
  function toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      wallRef.current?.requestFullscreen?.();
    }
  }

  return <>
    <div className="view-head2"><div><h1>Live Network</h1><div className="sub">Live and external camera feeds for Gujarat operations.</div></div></div>

    <div className="card2 live-network-toolbar">
      <div className="live-network-toolbar__filters">
        <label>Department<select value={department} onChange={updateFilter(setDepartment)}><option value="">All departments</option>{departments.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <label>Location<select value={location} onChange={updateFilter(setLocation)}><option value="">All locations</option>{locations.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <label>Feed source<select value={source} onChange={updateFilter(setSource)}><option value="">All sources</option><option value="live">Live HLS</option><option value="external">External snapshots</option><option value="offline">Offline / unavailable</option></select></label>
        <label>Camera type<select value={cameraType} onChange={updateFilter(setCameraType)}><option value="">All camera types</option>{cameraTypes.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <label className="live-network-toolbar__search">Search<input value={query} onChange={updateFilter(setQuery)} placeholder="ID, location, vendor" /></label>
      </div>

      <div className="live-network-toolbar__health">
        {HEALTH_STATES.map((state) => (
          <button
            key={state}
            type="button"
            className={`health-seg health-seg--${state} ${healthFilter === state ? "health-seg--active" : ""}`}
            onClick={() => toggleHealthFilter(state)}
            aria-pressed={healthFilter === state}
          >
            <span className={`camera-health-dot camera-health-dot--${state}`} />
            {HEALTH_LABEL[state]}
            <b>{healthCounts[state]}</b>
          </button>
        ))}
      </div>

      {activeFilters.length > 0 && (
        <div className="live-network-toolbar__chips">
          {activeFilters.map((filter) => (
            <span key={filter.key} className="filter-chip">
              {filter.label}
              <button type="button" aria-label={`Remove filter: ${filter.label}`} onClick={filter.onClear}>×</button>
            </span>
          ))}
          <button type="button" className="filter-chip filter-chip--clear-all" onClick={clearAllFilters}>Clear all</button>
        </div>
      )}
    </div>

    <div className="card2 camera-registry-list">
      <div className="camera-registry-list__head"><div><h2>Camera registry</h2><span className="sub">{filteredCameras.length} cameras match the metadata filters</span></div><span className="sub">Real registry metadata</span></div>
      <div className="camera-registry-table-wrap"><table className="camera-registry-table"><thead><tr><th>Camera</th><th>Department</th><th>Location</th><th>Type / vendor</th><th>Feed</th><th>Health</th><th>Alert</th></tr></thead><tbody>{filteredCameras.map((camera) => { const health = healthOf(camera); return <tr key={camera.id}><td><strong>{camera.id}</strong></td><td>{camera.department || "Unassigned"}</td><td>{camera.location || "Location unknown"}</td><td>{camera.camera_type || "Type unknown"}{camera.vendor ? ` / ${camera.vendor}` : ""}</td><td>{camera.source_system ? "External snapshot" : camera.live ? "Live HLS" : "Offline"}</td><td><span className={`camera-health-dot camera-health-dot--${health}`} />{HEALTH_LABEL[health]}</td><td>{alertingCameraIds.has(camera.id) ? <span className="badge badge--alerting">active alert</span> : "—"}</td></tr>; })}</tbody></table>{filteredCameras.length === 0 && <p className="sub camera-registry-list__empty">No cameras match these metadata filters.</p>}</div>
    </div>

    <div className="view-head2 live-network-wall-head">
      <div>
        <h2>Video wall</h2>
        <div className="sub">
          {activeSelected.length}/{tileLimit} tiles active / {viewableCameras.length} selectable cameras · drag a tile to reorder
          {touring && ` · touring page ${(tourIndex % tourPageCount) + 1}/${tourPageCount}`}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {WALL_LAYOUTS.map((limit) => (
          <button key={limit} className={`btn2 ${tileLimit === limit ? "primary2" : ""}`} onClick={() => setWallLimit(limit)}>{limit === 1 ? "Focus" : limit}</button>
        ))}
        <button className="btn2" onClick={fillWall} disabled={activeSelected.length >= tileLimit || viewableCameras.length === 0}>Fill wall</button>
        <button
          className={`btn2 ${touring ? "primary2" : ""}`}
          onClick={toggleTour}
          disabled={viewableCameras.length <= tileLimit}
          title={viewableCameras.length <= tileLimit ? "Tour needs more viewable cameras than tiles" : "Rotate the wall through every viewable camera"}
        >
          {touring ? "Stop tour" : "Tour"}
        </button>
        <button className="btn2" onClick={toggleFullscreen} disabled={activeSelected.length === 0}>Fullscreen</button>
        <button className="btn2" onClick={() => { setTouring(false); setSelected([]); }} disabled={activeSelected.length === 0}>Clear</button>
      </div>
    </div>

    <div className="card2" style={{ marginBottom: 14 }}>
      <div className="camera-grid-picker">
        {viewableCameras.length === 0 ? <p className="sub">No viewable cameras match the current filters.</p> : viewableCameras.map((camera) => (
          <button key={camera.id} onClick={() => toggle(camera.id)} className={`camera-grid-picker__chip ${activeSelected.includes(camera.id) ? "camera-grid-picker__chip--active" : ""} ${alertingCameraIds.has(camera.id) ? "camera-grid-picker__chip--alerting" : ""}`}>
            {camera.id}{camera.source_system ? " (external)" : ""}
          </button>
        ))}
      </div>
    </div>

    {activeSelected.length === 0 ? <div className="card2" style={{ padding: 24, textAlign: "center", color: "var(--text-dim)" }}>Select one or more filtered cameras to tile their feeds, or use "Fill wall".</div> : (
      <div ref={wallRef} className={`camera-grid camera-grid--n${activeSelected.length} camera-grid--fullscreenable`}>
        {activeSelected.map((id) => {
          const camera = viewableById[id];
          const health = healthOf(camera);
          const alerting = alertingCameraIds.has(id);
          return (
            <div
              key={id}
              className={`camera-grid__tile card2 camera-grid__tile--health-${health} ${alerting ? "camera-grid__tile--alerting" : ""} ${dragId === id ? "camera-grid__tile--dragging" : ""}`}
              draggable={activeSelected.length > 1}
              onDragStart={() => setDragId(id)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop(id)}
              onDragEnd={() => setDragId(null)}
            >
              <div className="camera-grid__tile-label">
                {id}
                {alerting && <span className="camera-grid__tile-alert-badge" title="Active alert on this camera">ALERT</span>}
              </div>
              <div className="camera-grid__tile-actions">
                {tileLimit !== 1 && (
                  <button className="camera-grid__tile-info" aria-label={`Focus ${id} alone`} title="Focus this camera alone" onClick={() => focusTile(id)}>⤢</button>
                )}
                <button className="camera-grid__tile-info" aria-label={`Open details for ${id}`} onClick={() => setDetailCameraId(id)}>i</button>
              </div>
              {camera.snapshot_image_url ? <SnapshotView imageUrl={camera.snapshot_image_url} sourceLabel={camera.source_system} /> : <LiveView cameraId={id} />}
            </div>
          );
        })}
      </div>
    )}
    {tileLimit === 1 && activeSelected.length === 1 && (
      <div style={{ textAlign: "center", marginTop: 10 }}>
        <button className="btn2" onClick={() => setWallLimit(4)}>Back to grid</button>
      </div>
    )}
    {detailCameraId && <CameraDetailPanel cameraId={detailCameraId} onClose={() => setDetailCameraId(null)} />}
  </>;
}
