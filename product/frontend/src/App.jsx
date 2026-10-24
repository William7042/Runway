import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, API } from "./api.js";
import ProposalCard, { titleOf } from "./components/ProposalCard.jsx";
import BlockedCard from "./components/BlockedCard.jsx";
import BountyBoard from "./components/BountyBoard.jsx";
import Activity from "./components/Activity.jsx";
import Landing from "./components/Landing.jsx";
import DemoControls from "./components/DemoControls.jsx";
import { usd, ago, parseFlag } from "./format.js";

// Routes: "#home" (landing, default), "#desk", "#activity", "#bounties"
const TABS = [
  ["desk", "Approvals"],
  ["activity", "Activity"],
  ["bounties", "Bounties"],
];
const ROUTES = ["home", ...TABS.map(([k]) => k)];

function useRoute() {
  const read = () => {
    const h = location.hash.slice(1);
    if (h === "ledger") return "activity"; // old link
    return ROUTES.includes(h) ? h : "home";
  };
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => {
      setRoute(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [route, (r) => (location.hash = r)];
}

export default function App() {
  const [route, go] = useRoute();
  const [state, setState] = useState({ proposals: [], config: null, balances: {}, bounties: [], health: null });
  const [online, setOnline] = useState(true);
  const [toast, setToast] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [dismissedBlocked, setDismissedBlocked] = useState(() => new Set());
  const lastBlocked = useRef(null);
  const awaitingReceipt = useRef(new Set());

  const refresh = useCallback(async () => {
    try {
      const [proposals, config, balances, bounties, health] = await Promise.all([
        api.proposals(), api.config(), api.balances(), api.bounties(), api.health(),
      ]);
      if (!Array.isArray(proposals)) throw new Error("bad response");
      setState({ proposals, config, balances, bounties, health });
      setOnline(true);

      const newestBlocked = proposals.find((p) => p.blocked);
      if (newestBlocked && lastBlocked.current !== null && newestBlocked.id !== lastBlocked.current) {
        setToast({ kind: "block", text: "Attack blocked. An injected payment request was stopped by policy." });
      }
      lastBlocked.current = newestBlocked ? newestBlocked.id : "";

      for (const id of awaitingReceipt.current) {
        const p = proposals.find((x) => x.id === id);
        if (p?.receipt) {
          awaitingReceipt.current.delete(id);
          const ok = p.receipt.status === "executed";
          setToast({
            kind: ok ? "ok" : "block",
            text: ok ? `Paid ${usd(p.amount_usd)} to ${p.seller}. Tx ${String(p.receipt.tx_hash).slice(0, 14)}…` : `Payment to ${p.seller} failed.`,
          });
        }
      }
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

  // Queue: oldest first, so requests are handled in the order the agent made them.
  const pending = state.proposals.filter((p) => p.status === "pending").sort((a, b) => (a.created_at || 0) - (b.created_at || 0));
  const current = pending.find((p) => p.id === selectedId) || pending[0];
  const upNext = pending.filter((p) => p !== current);
  const blocked = state.proposals.filter((p) => p.blocked && !dismissedBlocked.has(p.id)).slice(0, 1);

  async function decide(id, decision, reason) {
    await api.decide(id, decision, reason);
    if (decision === "approve") awaitingReceipt.current.add(id);
    setSelectedId(null);
    setToast(
      decision === "approve"
        ? { kind: "ok", text: "Approved. The router is signing and sending it now." }
        : { kind: "warn", text: "Rejected. The agent is told why." }
    );
    await refresh();
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => go("home")} title="About Runway">
          <span className="logo">▲</span> Runway
        </button>
        <nav className="tabs">
          {TABS.map(([k, label]) => (
            <button key={k} className={`tab ${route === k ? "active" : ""}`} onClick={() => go(k)}>
              {label}
              {k === "desk" && pending.length > 0 && <span className="count">{pending.length}</span>}
            </button>
          ))}
        </nav>
        <div className="status">
          {state.config?.dry_run && <span className="pill pill-warn">Dry run</span>}
          <span className={`live ${online ? "on" : "off"}`} title={API}>
            <span className="live-dot" />
            {online ? "Live" : "Offline"}
          </span>
        </div>
      </header>

      {!online && route !== "home" && (
        <div className="offline">
          Can't reach the approval queue at <span className="mono">{API}</span>. Double-click <span className="mono">product/start.bat</span> to start it.
        </div>
      )}

      {route === "home" && <Landing onOpen={() => go("desk")} />}

      {route === "desk" && (
        <main className="desk-focus">
          {blocked.map((p) => (
            <div key={p.id} className="blocked-wrap">
              <BlockedCard p={p} />
              <button className="btn btn-ghost small dismiss" onClick={() => setDismissedBlocked(new Set([...dismissedBlocked, p.id]))}>
                Dismiss
              </button>
            </div>
          ))}

          <div className="page-title">
            <h1>{pending.length === 0 ? "You're all caught up" : pending.length === 1 ? "1 decision waiting" : `${pending.length} decisions waiting`}</h1>
            <p>Nothing is paid until you approve it. There is no auto-approve.</p>
          </div>

          {current ? (
            <ProposalCard
              key={current.id}
              p={current}
              config={state.config}
              onDecide={decide}
              position={pending.indexOf(current) + 1}
              total={pending.length}
            />
          ) : (
            <div className="empty big-empty">
              <div className="empty-mark">✓</div>
              <div className="strong">No orders need your approval.</div>
              <div>When the agent wants to spend, it will show up here first.</div>
              <button className="btn small" onClick={() => go("activity")}>
                See activity
              </button>
            </div>
          )}

          {upNext.length > 0 && (
            <section className="upnext">
              <h2 className="section-title">Up next</h2>
              <div className="upnext-list">
                {upNext.map((p) => {
                  const hasWarn = (p.flags || []).length > 0;
                  return (
                    <button key={p.id} className="upnext-row" onClick={() => setSelectedId(p.id)}>
                      <div className="grow">
                        <div className="upnext-title">{titleOf(p)}</div>
                        <div className="upnext-sub">
                          to {p.seller} · {ago(p.created_at)}
                          {hasWarn && <span className="warn-dot"> · {parseFlag(p.flags[0]).label}</span>}
                        </div>
                      </div>
                      <span className="upnext-amt num">{usd(p.amount_usd)}</span>
                      <span className="chev" aria-hidden="true">›</span>
                    </button>
                  );
                })}
              </div>
            </section>
          )}
        </main>
      )}

      {route === "activity" && (
        <main className="page">
          <div className="page-title">
            <h1>Activity</h1>
            <p>Wallets, totals, and every decision with quote versus fill.</p>
          </div>
          <Activity proposals={state.proposals} balances={state.balances} />
        </main>
      )}

      {route === "bounties" && (
        <main className="page">
          <div className="page-title">
            <h1>Bounties</h1>
            <p>Hire people and agents. Every payout is approved like any other order.</p>
          </div>
          <BountyBoard bounties={state.bounties} proposals={state.proposals} api={api} refresh={refresh} />
        </main>
      )}

      {route !== "home" && (
        <DemoControls
          config={state.config}
          health={state.health}
          api={api}
          refresh={refresh}
          onReset={() => {
            lastBlocked.current = null;
            setDismissedBlocked(new Set());
          }}
        />
      )}

      {toast && <div className={`toast toast-${toast.kind}`}>{toast.text}</div>}
    </div>
  );
}
