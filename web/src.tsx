import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Connection = { id: string; provider: string; status: string };
const csrf = () => document.cookie.split("; ").find(x => x.startsWith("obm_csrf="))?.split("=")[1] || "";

const connectionStatus = (status: string) => ({
  connected: "Synced and ready",
  reconnecting: "Finish reconnecting in TrueLayer",
  reauthorization_required: "Reconnect required",
  scope_update_required: "Update access to enable complete read-only financial data",
  sync_delayed: "TrueLayer is temporarily unavailable. Connection saved — retry in a few minutes.",
}[status] || "Preparing connection");

function App() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [busy, setBusy] = useState(false);
  const [connectError, setConnectError] = useState("");
  const [syncError, setSyncError] = useState("");
  const load = () => fetch("/api/connections").then(r => r.json()).then(x => setConnections(x.connections));
  useEffect(() => { load().catch(() => {}); }, []);
  const connect = async () => {
    setBusy(true);
    setConnectError("");
    try {
      const response = await fetch("/api/connect", { method: "POST", headers: { "x-csrf-token": csrf() } });
      const payload = await response.json();
      if (!response.ok || !payload.authorization_url) throw new Error(payload.detail || "Unable to begin connection");
      location.assign(payload.authorization_url);
    } catch (reason) {
      setBusy(false);
      setConnectError(reason instanceof Error ? reason.message : "Unable to begin connection");
    }
  };
  const sync = async (id: string) => {
    setBusy(true); setSyncError("");
    try {
      const response = await fetch(`/api/connections/${id}/sync`, { method: "POST", headers: { "x-csrf-token": csrf() } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Unable to refresh connection");
    } catch (reason) {
      setSyncError(reason instanceof Error ? reason.message : "Unable to refresh connection");
    } finally { await load(); setBusy(false); }
  };
  const reconnect = async (id: string) => {
    setBusy(true); setConnectError("");
    try {
      const response = await fetch(`/api/connections/${id}/reconnect`, { method: "POST", headers: { "x-csrf-token": csrf() } });
      const payload = await response.json();
      if (!response.ok || !payload.authorization_url) throw new Error(payload.detail || "Unable to begin reconnection");
      location.assign(payload.authorization_url);
    } catch (reason) {
      setBusy(false);
      setConnectError(reason instanceof Error ? reason.message : "Unable to begin reconnection");
    }
  };
  const remove = async (id: string) => { if (confirm("Revoke this bank connection and remove all of its local data?")) { await fetch(`/api/connections/${id}/remove`, { method: "POST", headers: { "x-csrf-token": csrf() } }); load(); } };
  return <main className="shell">
    <header><div className="brand"><span className="mark">◒</span><span>OpenBankingMCP</span></div><span className="local"><i /> Local only</span></header>
    <section className="hero"><div><p className="eyebrow">YOUR FINANCIAL DATA, ON YOUR DEVICE</p><h1>Private finance context<br /><em>for your AI.</em></h1><p className="lead">Connect read-only bank data, store it encrypted locally, and ask your MCP client better questions.</p></div><div className="hero-card"><span className="shield">⌁</span><strong>Encrypted by default</strong><p>Credentials stay in your operating system’s secure credential store. Your local cache is encrypted and owner-only.</p></div></section>
    <section className="grid">
      <div className="panel connect"><div className="step">01</div><div><p className="eyebrow">LIVE TRUE LAYER DATA API</p><h2>Connect a real bank</h2><p className="muted">Choose your bank in TrueLayer’s secure account selector, then approve the accounts you want to share.</p></div>{connections.length === 0 && <div className="connection-preview"><span className="route-icon">⌁</span><div><strong>First-time setup</strong><p>In TrueLayer Console: switch to Live, enable Data API permissions and providers, add this app’s redirect URI, then save the live credentials with the setup command.</p></div></div>}<button className="primary" disabled={busy} onClick={connect}>{busy ? "Opening secure connection…" : <>Choose a live bank with TrueLayer <span>→</span></>}</button>{connectError && <p className="connection-error">{connectError}</p>}<p className="fine">Read-only access · No payments · You can remove access any time</p></div>
      <div className="panel accounts"><div className="section-title"><div><p className="eyebrow">YOUR CONNECTIONS</p><h2>Connected accounts</h2></div><span className="count">{connections.length}</span></div>{connections.length ? <ul className="connections">{connections.map(connection => <li key={connection.id}><div className="bank-icon">◒</div><div><strong>{connection.provider}</strong><small className={`connection-status ${connection.status}`}>{connectionStatus(connection.status)}</small></div><div className="actions">{connection.status === "reauthorization_required" || connection.status === "scope_update_required" ? <button onClick={() => reconnect(connection.id)} disabled={busy}>{connection.status === "scope_update_required" ? "Update access" : "Reconnect"}</button> : <button onClick={() => sync(connection.id)} disabled={busy}>Refresh</button>}<button className="quiet" onClick={() => remove(connection.id)}>Remove</button></div></li>)}</ul> : <div className="empty"><div className="empty-icon">⌁</div><strong>No accounts connected yet</strong><p>Your securely connected accounts will appear here.</p></div>}{syncError && <p className="connection-error">{syncError}</p>}</div>
    </section>
    <section className="privacy"><div className="privacy-icon">⌾</div><div><strong>Designed to keep financial data private.</strong><p>OpenBankingMCP is local-only, read-only, and never provides payment or transfer controls.</p></div><span>System credential store + encrypted local cache</span></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
