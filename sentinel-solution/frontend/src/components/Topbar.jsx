import { useEffect, useState } from "react";
import { api, hasSessionHint } from "../api";
import { IconShield, IconSearch, IconBell } from "../icons";

export default function Topbar({ health, activeAlertCount, onSearchSubmit, onAuthenticated }) {
  const [key, setKey] = useState("");
  const [identity, setIdentity] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");

  async function checkIdentity() {
    try {
      setIdentity(await api.whoami());
      setError(null);
      // The key may have just been set — App's data polls started at mount
      // (before any session existed) and won't retry until their next
      // interval tick, which can land well after a screen has already been
      // shown. Trigger an immediate refresh so screens don't wait out that gap.
      onAuthenticated?.();
    } catch (err) {
      setIdentity(null);
      setError(err.message);
    }
  }

  useEffect(() => {
    if (hasSessionHint()) checkIdentity();
  }, []);

  async function signIn() {
    setError(null);
    try {
      await api.login(key.trim());
      setKey("");
      await checkIdentity();
    } catch (err) {
      setError(err.message);
    }
  }

  async function signOut() {
    await api.logout();
    setIdentity(null);
  }

  return (
    <header className="topbar2">
      <div className="topbar-brandblock" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div className="brand-mark"><IconShield width={16} height={16} /></div>
        <div className="topbar-title2">
          <div className="t1">SENTINEL</div>
          <div className="agency">Gujarat Police · Geo-Temporal Vehicle Intelligence</div>
        </div>
      </div>

      <div className="stat-chip"><span className={`dot2 ${health ? "on" : "off"}`} /> System <b>{health ? "NOMINAL" : "UNKNOWN"}</b></div>
      <div className="stat-chip">
        Cameras <b>{health?.catalogue_size ?? "—"}</b>
        {health && <> · <span style={{ color: "var(--confirmed)" }}>{health.active_camera_worker_count ?? 0} active</span></>}
      </div>
      <div className="stat-chip"><span className="dot2 off" /> Alerts <b>{activeAlertCount ?? "—"}</b></div>

      <div className="topbar-spacer" />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) onSearchSubmit?.(query.trim());
        }}
        className="searchbar2"
        style={{
          display: "flex", alignItems: "center", gap: 8, background: "var(--panel-bg-2)",
          border: "1px solid var(--border)", borderRadius: 6, padding: "0 10px", height: 32, width: 240,
        }}
      >
        <IconSearch width={14} height={14} style={{ color: "var(--text-dim)", flex: "none" }} />
        <input
          type="text"
          placeholder="Search vehicle / plate / case ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ background: "none", border: "none", color: "var(--text-h)", fontSize: 12, width: "100%", height: "100%", fontFamily: "var(--mono)" }}
        />
      </form>

      <div className="bell" title="Active alerts">
        <IconBell />
        {activeAlertCount > 0 && <span className="bcount">{activeAlertCount}</span>}
      </div>

      <div
        className="userchip2"
        style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px 4px 4px", borderRadius: 20, border: "1px solid var(--border)", background: "var(--panel-bg-2)" }}
      >
        {identity ? (
          <>
            <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--accent-bg)", border: "1px solid var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 800, color: "var(--accent)" }}>
              {identity.user_id?.slice(0, 2).toUpperCase()}
            </div>
            <div style={{ fontSize: 11, lineHeight: 1.15 }}>
              <b style={{ display: "block", color: "var(--text-h)" }}>{identity.user_id}</b>
              <span style={{ color: "var(--text-dim)", fontSize: 9.5 }}>{identity.role}</span>
            </div>
            <button className="btn2" style={{ padding: "3px 8px", fontSize: 10.5 }} onClick={signOut}>Sign out</button>
          </>
        ) : (
          <>
            <input
              type="password"
              placeholder="API key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && signIn()}
              style={{ background: "none", border: "none", color: "var(--text-h)", fontSize: 11, width: 130 }}
            />
            <button className="btn2" style={{ padding: "3px 8px", fontSize: 10.5 }} onClick={signIn}>Sign in</button>
          </>
        )}
      </div>
      {error && <span style={{ color: "var(--danger)", fontSize: 10.5 }}>{error}</span>}
    </header>
  );
}
