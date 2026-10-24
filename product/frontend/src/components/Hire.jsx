import React from "react";
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
  const s = SUBS[sub] ? sub : "specialists";
  return (
    <main className="page">
      <div className="page-title">
        <h1>{SUBS[s].title}</h1>
        <p>{SUBS[s].blurb}</p>
      </div>
      <div className="subtabs" role="tablist">
        {Object.entries(SUBS).map(([k, v]) => (
          <button key={k} role="tab" aria-selected={s === k} className={`subtab ${s === k ? "active" : ""}`} onClick={() => go(k === "specialists" ? "hire" : `hire/${k}`)}>
            {v.label}
          </button>
        ))}
      </div>
      {s === "specialists" ? (
        <Specialists api={api} balances={state.balances} refreshKey={tick} onOpenApprovals={() => go("desk")} />
      ) : (
        <BountyBoard bounties={state.bounties} proposals={state.proposals} api={api} refresh={refresh} />
      )}
    </main>
  );
}
