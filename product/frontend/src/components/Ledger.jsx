import React, { useState } from "react";
import { usd, ago, costTotal } from "../format.js";
import "../styles/ledger.css";
import { TxHash } from "./Receipts.jsx";

const cost = (x) => (x && typeof x === "object" ? x.cost_usd ?? x.total_usd : x);

const FILTERS = [
  ["all", "All"],
  ["paid", "Paid out"],
  ["earned", "Earned"],
  ["rejected", "Rejected"],
  ["blocked", "Blocked"],
];

export default function Ledger({ proposals, balances, showStats = true, earnedSellers = [] }) {
  const [filter, setFilter] = useState("all");
  const isEarned = (p) => earnedSellers.includes(p.seller);
  const decided = proposals.filter((p) => p.status !== "pending");
  const shown = decided.filter((p) =>
    filter === "all" ? true
      : filter === "paid" ? p.status === "executed" && !isEarned(p)
      : filter === "earned" ? p.status === "executed" && isEarned(p)
      : filter === "rejected" ? p.status === "rejected" && !p.blocked
      : p.blocked
  );
  const executed = decided.filter((p) => p.status === "executed");
  const spent = executed.reduce((a, p) => a + Number(p.amount_usd || 0), 0);
  const fees = executed.reduce((a, p) => a + Number(cost(p.receipt?.fill) || 0), 0);
  const blocked = decided.filter((p) => p.blocked).length;
  const rejected = decided.filter((p) => p.status === "rejected" && !p.blocked).length;
  const ra = balances?.["research-agent"];
  const principal = ra?.cost_basis_usd;

  return (
    <div className="stack">
      {showStats && <div className="stats">
        <div className="stat"><div className="label">Paid out</div><div className="big">{usd(spent, 2)}</div></div>
        <div className="stat"><div className="label">Execution cost</div><div className="big">{usd(fees, 4)}</div></div>
        <div className="stat"><div className="label">Rejected by human</div><div className="big">{rejected}</div></div>
        <div className="stat"><div className="label">Blocked by policy</div><div className="big danger">{blocked}</div></div>
        {principal !== undefined && (
          <div className="stat"><div className="label">Principal still invested</div><div className="big good">{usd(principal, 2)}</div></div>
        )}
      </div>}

      <section className="panel">
        <div className="panel-head">
          <h2>History</h2>
          <div className="chips" role="group" aria-label="Filter history">
            {FILTERS.map(([k, label]) => (
              <button key={k} className={`chip-btn ${filter === k ? "active" : ""}`} onClick={() => setFilter(k)}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="table-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>When</th><th>Purpose</th><th>To</th><th className="right">Amount</th>
                <th className="right">Quote</th><th className="right">Fill</th><th>Status</th><th>Decision</th><th>Tx</th>
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 && (
                <tr><td colSpan="9" className="muted">{decided.length === 0 ? "Nothing decided yet." : "Nothing matches this filter."}</td></tr>
              )}
              {shown.map((p) => (
                <tr key={p.id} className={p.blocked ? "row-blocked" : ""}>
                  <td className="muted small">{ago(p.receipt?.at || p.decision?.at || p.created_at)}</td>
                  <td>{p.purpose}</td>
                  <td className="small">{p.seller}</td>
                  <td className="mono right">{usd(p.amount_usd)}</td>
                  <td className="mono right">{p.receipt ? usd(cost(p.receipt.quote), 5) : usd(costTotal(p.expected_cost), 5)}</td>
                  <td className="mono right">{p.receipt ? usd(cost(p.receipt.fill), 5) : "—"}</td>
                  <td><span className={`pill pill-${p.status}`}>{p.blocked ? "blocked" : p.status}</span></td>
                  <td className="small">
                    {p.decision?.by === "policy" ? "policy" : p.decision?.decision}
                    {p.decision?.reason && <div className="muted">{p.decision.by === "policy" ? (p.flags || []).length + " rules hit" : p.decision.reason}</div>}
                  </td>
                  <td>{p.receipt ? <TxHash hash={p.receipt.tx_hash} stub={p.receipt.stub} /> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
