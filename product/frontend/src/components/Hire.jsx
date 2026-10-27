import React, { useRef, useState } from "react";
import HireAdvisor from "./HireAdvisor.jsx";
import Specialists from "./Specialists.jsx";
import BountyBoard from "./BountyBoard.jsx";

const SUBS = {
  specialists: {
    label: "Specialists",
    title: "Hire a specialist",
    blurb: "Buy a ready-made service from an agent. Fixed price, delivered right away.",
  },
  bounties: {
    label: "Bounties",
    title: "Post a bounty",
    blurb: "Post a task anyone can claim, people or agents. Paid directly after you approve the work and the payment.",
  },
};

/** Hire = everything your agent can buy: specialists (catalog) and bounties (open tasks). */
export default function Hire({ sub, go, api, state, tick, refresh }) {
  const [compare, setCompare] = useState(false);
  const advisor = useRef(null);
  const s = SUBS[sub] ? sub : "specialists";
  return (
    <main className="page">
      <div className="page-title">
        <h1>{SUBS[s].title}</h1>
        <p>{SUBS[s].blurb}</p>
      </div>
      <div className="hire-toolbar">
      <div className="subtabs" role="tablist">
        {Object.entries(SUBS).map(([k, v]) => (
          <button key={k} role="tab" aria-selected={s === k} className={`subtab ${s === k ? "active" : ""}`} onClick={() => go(k === "specialists" ? "hire" : `hire/${k}`)}>
            {v.label}
          </button>
        ))}
      </div>
      {s === "specialists" && <div className="hire-toolbar-actions">
        <label className="hire-toggle" title="Off: one AI recommendation. On: compare up to three options.">
          <span>Decision mode</span><input type="checkbox" role="switch" aria-label="Compare buying options" checked={compare} onChange={e => setCompare(e.target.checked)} /><span className="hire-toggle-track" aria-hidden="true" /><strong>{compare ? 'Compare options' : 'AI pick'}</strong>
        </label>
        <button className="hire-advisor-link" onClick={() => advisor.current.showModal()}>Find a service ↗</button>
      </div>}
      </div>
      {s === "specialists" ? (
        <><dialog className="hire-advisor-dialog" ref={advisor} aria-label="Find a service"><button className="hire-dialog-close btn btn-ghost" autoFocus onClick={() => advisor.current.close()} aria-label="Close recommendations">Close ×</button><HireAdvisor compare={compare} api={api} balances={state.balances} proposals={state.proposals} onOpenApprovals={() => { advisor.current.close(); go("desk"); }} /></dialog><Specialists api={api} balances={state.balances} refreshKey={tick} onOpenApprovals={() => go("desk")} /></>
      ) : (
        <BountyBoard bounties={state.bounties} proposals={state.proposals} api={api} refresh={refresh} />
      )}
    </main>
  );
}
