import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, API } from "./api.js";
import ProposalCard, { titleOf } from "./components/ProposalCard.jsx";
import BlockedCard from "./components/BlockedCard.jsx";
import BountyBoard from "./components/BountyBoard.jsx";
import Wallet from "./components/Wallet.jsx";
import Hire from "./components/Hire.jsx";
import Sell from "./components/Sell.jsx";
import Landing from "./components/Landing.jsx";
import DemoControls from "./components/DemoControls.jsx";
import TwoAgents from "./components/TwoAgents.jsx";
import Backdrop from "./components/Backdrop.jsx";
import Balances from "./components/Balances.jsx";
import ReceiptsFeed from "./components/Receipts.jsx";
import { usd, ago, parseFlag, buyerWallet } from "./format.js";

// Tabs follow the demo story left to right: give a task → approve → hire → sell → see the money.
// Routes: "#home" (landing, default), "#tasks", "#desk", "#hire", "#hire/bounties", "#sell", "#wallet"
const TABS = [
  ["tasks", "Tasks"],
  ["desk", "Approvals"],
  ["hire", "Hire"],
  ["sell", "Sell"],
  ["wallet", "Wallet"],
];
const ROUTES = ["home", ...TABS.map(([k]) => k)];
// Old links keep working.
const ALIASES = { agents: "tasks", specialists: "hire", bounties: "hire/bounties", activity: "wallet", ledger: "wallet" };

function useRoute() {
  const read = () => {
    let h = location.hash.slice(1);
    h = ALIASES[h] || h;
    const [base, sub] = h.split("/");
    return ROUTES.includes(base) ? { base, sub } : { base: "home" };
  };
  const [r, setRoute] = useState(read);
  useEffect(() => {
    const on = () => {
      setRoute(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [r, (to) => (location.hash = to)];
}

export default function App() {
  const [{ base: route, sub }, go] = useRoute();
  const [deskView, setDeskView] = useState("waiting");
  const [state, setState] = useState({ proposals: [], config: null, balances: {}, bounties: [], health: null });
  const [online, setOnline] = useState(true);
  const [toast, setToast] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [tick, setTick] = useState(0);
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
      setTick((t) => t + 1);

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
  const decided = state.proposals
    .filter((p) => p.status !== "pending")
    .sort((a, b) => (b.receipt?.at || b.decision?.at || 0) - (a.receipt?.at || a.decision?.at || 0));
  const buyer = buyerWallet(state.balances);
  const treasury = buyer.total;

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
      <Backdrop />
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
          {treasury !== null && (
            <button className="treasury-chip" onClick={() => go("wallet")} title={`${buyer.id}: ${buyer.partial ? "priced assets only; unpriced holdings are listed in the wallet" : "wallet balance"}. Updated ${buyer.w?.snapshot_at ? new Date(buyer.w.snapshot_at).toLocaleTimeString() : "from demo data"}`}>
              <span className="tc-label">{buyer.id}{buyer.w?.simulated !== false ? " · demo" : buyer.partial ? " · priced assets" : " · wallet"}</span>
              <span className="tc-amount num">{usd(treasury, 2)}</span>
            </button>
          )}
          {state.health?.stub_executor && (
            <span className="pill pill-soft" title="Stub executor posts simulated receipts">Simulated fills</span>
          )}
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

      {route === "tasks" && <TwoAgents />}

      {route === "desk" && (
        <main className="desk-layout">
          <div className="desk-main">
            {blocked.map((p) => (
              <div key={p.id} className="blocked-wrap">
                <BlockedCard p={p} />
                <button className="btn btn-ghost small dismiss" onClick={() => setDismissedBlocked(new Set([...dismissedBlocked, p.id]))}>
                  Dismiss
                </button>
              </div>
            ))}

            <div className="page-title">
              <h1>{deskView === "decided" ? "Decided" : pending.length === 0 ? "You're all caught up" : pending.length === 1 ? "1 decision waiting" : `${pending.length} decisions waiting`}</h1>
              <p>Nothing is paid until you approve it. There is no auto-approve.</p>
            </div>

            <div className="subtabs" role="tablist">
              <button role="tab" aria-selected={deskView === "waiting"} className={`subtab ${deskView === "waiting" ? "active" : ""}`} onClick={() => setDeskView("waiting")}>
                Waiting {pending.length > 0 && <span className="count">{pending.length}</span>}
              </button>
              <button role="tab" aria-selected={deskView === "decided"} className={`subtab ${deskView === "decided" ? "active" : ""}`} onClick={() => setDeskView("decided")}>
                Decided
              </button>
            </div>

            {deskView === "decided" ? (
              decided.length === 0 ? (
                <div className="empty">Nothing decided yet.</div>
              ) : (
                <div className="recent">
                  {decided.map((p) => (
                    <div key={p.id} className="recent-row">
                      <div className="grow">
                        <div className="recent-title">{titleOf(p)}</div>
                        <div className="recent-sub">
                          to {p.seller} · {ago(p.receipt?.at || p.decision?.at || p.created_at)}
                          {p.decision?.reason ? ` · “${p.blocked ? "Blocked by policy" : p.decision.reason}”` : ""}
                        </div>
                      </div>
                      <span className={`pill pill-${p.status}`}>{p.blocked ? "blocked" : p.status}</span>
                      <span className="recent-amt num">{usd(p.amount_usd)}</span>
                    </div>
                  ))}
                </div>
              )
            ) : current ? (
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
                <button className="btn small" onClick={() => go("wallet")}>
                  See wallet history
                </button>
              </div>
            )}

            {deskView === "waiting" && upNext.length > 0 && (
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
          </div>

          <aside className="desk-side">
            <Balances balances={state.balances} layout="stack" />

            <ReceiptsFeed
              receipts={state.proposals
                .filter((p) => p.receipt)
                .sort((a, b) => (b.receipt?.at || 0) - (a.receipt?.at || 0))}
            />
          </aside>
        </main>
      )}

      {route === "hire" && <Hire sub={sub} go={go} api={api} state={state} tick={tick} refresh={refresh} />}

      {route === "sell" && (
        <main className="page">
          <div className="page-title">
            <h1>Sell</h1>
            <p>Your agent's own services. Other agents hire it, pay through their own approval, and your agent gets paid.</p>
          </div>
          <Sell api={api} refreshKey={tick} />
        </main>
      )}

      {route === "wallet" && (
        <main className="page">
          <div className="page-title">
            <h1>Wallet</h1>
            <p>What the agent holds, what came in, what went out, and every transaction.</p>
          </div>
          <Wallet api={api} proposals={state.proposals} balances={state.balances} refreshKey={tick} />
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
