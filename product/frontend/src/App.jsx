import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, API } from "./api.js";
import ProposalCard from "./components/ProposalCard.jsx";
import BlockedCard from "./components/BlockedCard.jsx";
import DriftGauge from "./components/DriftGauge.jsx";
import Balances from "./components/Balances.jsx";
import ReceiptsFeed from "./components/Receipts.jsx";
import BountyBoard from "./components/BountyBoard.jsx";
import Ledger from "./components/Ledger.jsx";
import { usd, ago } from "./format.js";

const TABS = [
  ["desk", "Approval desk"],
  ["bounties", "Bounty board"],
  ["ledger", "Ledger"],
];

function useTab() {
  const read = () => (TABS.some(([k]) => k === location.hash.slice(1)) ? location.hash.slice(1) : "desk");
  const [tab, setTab] = useState(read);
  useEffect(() => {
    const on = () => setTab(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [tab, (t) => (location.hash = t)];
}

export default function App() {
  const [tab, setTab] = useTab();
  const [state, setState] = useState({ proposals: [], receipts: [], config: null, balances: {}, bounties: [], health: null });
  const [online, setOnline] = useState(true);
  const [toast, setToast] = useState(null);
  const lastBlocked = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [proposals, receipts, config, balances, bounties, health] = await Promise.all([
        api.proposals(), api.receipts(), api.config(), api.balances(), api.bounties(), api.health(),
      ]);
      setState({ proposals, receipts, config, balances, bounties, health });
      setOnline(true);
      const newestBlocked = proposals.find((p) => p.blocked);
      if (newestBlocked && lastBlocked.current !== null && newestBlocked.id !== lastBlocked.current) {
        setToast({ kind: "block", text: "Attack blocked: an injected payment request was stopped by policy." });
      }
      lastBlocked.current = newestBlocked ? newestBlocked.id : "";
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const pending = state.proposals.filter((p) => p.status === "pending");
  const blocked = state.proposals.filter((p) => p.blocked);
  const recent = state.proposals.filter((p) => p.status !== "pending" && !p.blocked).slice(0, 6);

  async function decide(id, decision, reason) {
    await api.decide(id, decision, reason);
    setToast({ kind: decision === "approve" ? "ok" : "warn", text: decision === "approve" ? "Approved. Sent to the router for signing." : "Rejected. The agent is told why." });
    await refresh();
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">▲</span> Runway
          <span className="tagline">An economy for AI agents, with a human on every order</span>
        </div>
        <nav className="tabs">
          {TABS.map(([k, label]) => (
            <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>
              {label}
              {k === "desk" && pending.length > 0 && <span className="count">{pending.length}</span>}
            </button>
          ))}
        </nav>
        <div className="status">
          {state.config?.dry_run && <span className="pill pill-warn">DRY RUN</span>}
          {state.health?.stub_executor && <span className="pill pill-soft" title="Fake receipts until Person A's router is live">stub router</span>}
          <span className={`pill ${online ? "pill-ok" : "pill-bad"}`} title={API}>{online ? "queue online" : "queue offline"}</span>
        </div>
      </header>

      {!online && (
        <div className="offline">
          Can't reach the approval queue at <span className="mono">{API}</span>. Start it with{" "}
          <span className="mono">uvicorn app:app --port 8000</span> in <span className="mono">product/queue_service</span>.
        </div>
      )}

      {tab === "desk" && (
        <main className="desk">
          <div className="stack">
            <div className="page-title">
              <h1>Approvals</h1>
              <p>
                <span className="strong">{pending.length} waiting</span> · No auto-approve. Every order is reviewed one at a time.
              </p>
            </div>
            {pending.length === 0 && <div className="empty">Nothing waiting. The agent will ask before it spends.</div>}
            {pending.map((p) => (
              <ProposalCard key={p.id} p={p} config={state.config} onDecide={decide} />
            ))}

            {blocked.length > 0 && (
              <>
                <h2 className="section-title danger">Blocked before reaching you</h2>
                {blocked.slice(0, 2).map((p) => (
                  <BlockedCard key={p.id} p={p} />
                ))}
              </>
            )}

            {recent.length > 0 && (
              <>
                <h2 className="section-title">Recently decided</h2>
                <div className="recent">
                  {recent.map((p) => (
                    <div key={p.id} className="recent-row">
                      <div className="grow">
                        <div className="recent-title">{p.seller}</div>
                        <div className="recent-sub">
                          {p.decision?.reason ? `“${p.decision.reason}”` : p.purpose}
                        </div>
                      </div>
                      <span className={`pill pill-${p.status}`}>{p.status}</span>
                      <span className="recent-amt num">{usd(p.amount_usd)}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <aside className="stack">
            <DriftGauge
              config={state.config}
              onChange={async (v) => {
                await api.setConfig({ drift_pct: v });
                refresh();
              }}
            />
            <Balances balances={state.balances} />
            <ReceiptsFeed receipts={state.receipts} />
          </aside>
        </main>
      )}

      {tab === "bounties" && (
        <main className="page">
          <div className="page-title">
            <h1>Bounties</h1>
            <p>Hire humans and agents. Every payout is approved like any other order.</p>
          </div>
          <BountyBoard bounties={state.bounties} proposals={state.proposals} api={api} refresh={refresh} />
        </main>
      )}

      {tab === "ledger" && (
        <main className="page">
          <div className="page-title">
            <h1>Ledger</h1>
            <p>Every proposal, decision and fill, with quote versus fill.</p>
          </div>
          <Ledger proposals={state.proposals} balances={state.balances} />
        </main>
      )}

      <footer className="footer">
        <span className="muted small">Technical demo, not financial advice. Simulated sellers are labelled.</span>
        <details className="demo-controls">
          <summary>Demo controls</summary>
          <button className="btn btn-ghost small" onClick={async () => { await api.attack(); refresh(); }}>
            Simulate injection attack
          </button>
          <button
            className="btn btn-ghost small"
            onClick={async () => {
              if (confirm("Reset all demo data to the seeded state?")) {
                await api.reset();
                lastBlocked.current = null;
                refresh();
              }
            }}
          >
            Reset demo data
          </button>
        </details>
      </footer>

      {toast && <div className={`toast toast-${toast.kind}`}>{toast.text}</div>}
    </div>
  );
}
