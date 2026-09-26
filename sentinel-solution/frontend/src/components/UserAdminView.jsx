import { useEffect, useState } from "react";
import { api } from "../api";

// Admin-only. Real GET/POST /auth/api-keys — no invented user directory.
//
// A minted key is shown exactly once, here, and never persisted by the
// frontend: the backend stores only its SHA-256 hash, so there is nowhere
// to look it up again. That mirrors ensure_default_admin_key's deliberate
// print()-once behaviour; the warning below exists so an operator does not
// assume they can retrieve it later.
export default function UserAdminView() {
  const [keys, setKeys] = useState([]);
  const [error, setError] = useState(null);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("viewer");
  const [department, setDepartment] = useState("");
  const [minted, setMinted] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setKeys(await api.listApiKeys());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    if (!userId.trim()) return;
    if (role !== "admin" && !department.trim()) {
      setError("department is required for viewer and investigator keys — a blank department would grant statewide access.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setMinted(await api.createApiKey(userId.trim(), role, department.trim()));
      setUserId("");
      setDepartment("");
      await load();
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
          <h1>User Administration</h1>
          <div className="sub">API keys, roles and department scope — admin only</div>
        </div>
      </div>

      {error && (
        <div className="card2">
          <p style={{ color: "var(--danger)", fontSize: 12.5, margin: 0 }}>{error}</p>
        </div>
      )}

      {minted && (
        <div className="card2" style={{ borderColor: "var(--warn)" }}>
          <div className="card-h2">
            <h2>Key created for {minted.user_id}</h2>
            <span className="state-badge" style={{ color: "var(--warn)", background: "var(--warn-bg)" }}>
              SHOWN ONCE
            </span>
          </div>
          <code style={{ display: "block", padding: 12, background: "var(--bg-sunken)", borderRadius: 6, fontSize: 12.5, wordBreak: "break-all" }}>
            {minted.api_key}
          </code>
          <p style={{ fontSize: 11.5, color: "var(--text-dim)", marginTop: 10, lineHeight: 1.6 }}>
            Copy it now. Only a SHA-256 hash is stored, so this value cannot be recovered — if it
            is lost, mint a new key and revoke this one.
          </p>
          <button className="btn2" onClick={() => setMinted(null)}>Dismiss</button>
        </div>
      )}

      <div className="cols2">
        <div className="card2">
          <div className="card-h2"><h2>Issue a key</h2></div>
          <form onSubmit={create} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <input className="input2" placeholder="user id (e.g. insp.patel)" value={userId} onChange={(e) => setUserId(e.target.value)} />
            <select className="input2" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="viewer">viewer — read-only</option>
              <option value="investigator">investigator — search, watchlist, alerts</option>
              <option value="admin">admin — full control, sees raw camera URLs</option>
            </select>
            <input className="input2" placeholder={role === "admin" ? "department (optional for admin)" : "department (required)"} value={department} onChange={(e) => setDepartment(e.target.value)} />
            <button className="btn2" type="submit" disabled={busy || !userId.trim()}>
              {busy ? "Creating…" : "Create key"}
            </button>
          </form>
        </div>

        <div className="card2">
          <div className="card-h2"><h2>Issued keys ({keys.length})</h2></div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-dim)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                <th style={{ padding: "0 10px 8px" }}>User</th>
                <th style={{ padding: "0 10px 8px" }}>Role</th>
                <th style={{ padding: "0 10px 8px" }}>Department</th>
                <th style={{ padding: "0 10px 8px" }}>Created</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={`${k.user_id}-${k.created_at}`} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "10px", fontWeight: 600 }}>{k.user_id}</td>
                  <td style={{ padding: "10px" }}>{k.role}</td>
                  <td style={{ padding: "10px" }}>{k.department || "all"}</td>
                  <td style={{ padding: "10px" }}>{new Date(k.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
              {!keys.length && <tr><td colSpan={4} style={{ padding: 16, color: "var(--text-dim)" }}>No keys visible.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
