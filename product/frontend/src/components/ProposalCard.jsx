import React, { useState } from "react";
import { usd, amt, parseFlag, costTotal, driftPct, sourceInfo, SOURCE_LABEL, ago } from "../format.js";
import { DriftBar } from "./DriftGauge.jsx";
import "../styles/desk.css";

export function Flags({ flags }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className="flags">
      {flags.map((f, i) => {
        const p = parseFlag(f);
        return (
          <div key={i} className={`flag flag-${p.kind}`}>
            <span className="flag-label">{p.label}</span>
            <span>{p.text}</span>
          </div>
        );
      })}
    </div>
  );
}

export function Source({ source }) {
  const s = sourceInfo(source);
  return (
    <div className={`source source-${s.kind}`}>
      <span className="source-kind">{SOURCE_LABEL[s.kind] || s.kind}</span>
      {s.text && <span className="source-text">“{s.text}”</span>}
    </div>
  );
}

// Tokenized stocks use a lowercase "c" suffix, e.g. NVDAc, TSLAc.
const sellsTokenizedStock = (path) => (path || []).some((s) => s.type === "swap" && /^[A-Z]+c$/.test(s.asset));

export default function ProposalCard({ p, config, onDecide }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const sells = (p.path || []).filter((s) => s.type === "swap");
  const pays = (p.path || []).filter((s) => s.type === "transfer");
  const cost = costTotal(p.expected_cost);
  const d = driftPct(p.drift);
  const live = config?.drift_pct;
  const threshold = config?.drift_threshold_pct ?? 2;
  const driftDanger = sellsTokenizedStock(p.path) && live !== undefined && live > threshold;

  async function decide(decision) {
    setBusy(true);
    setErr("");
    try {
      await onDecide(p.id, decision, reason);
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  }

  return (
    <article className="card pc">
      <div className="pc-top">
        <div className="pc-who">
          <div className="pc-seller">{p.seller}</div>
          <div className="pc-sub">
            Requested by {p.buyer} · {ago(p.created_at)}
            {p.bounty_role && <span className="pill">bounty {p.bounty_role}</span>}
          </div>
        </div>
        <div className="pc-amount num">{usd(p.amount_usd)}</div>
      </div>

      <p className="pc-purpose">{p.purpose}</p>

      <Flags flags={p.flags} />

      <dl className="kv">
        <div>
          <dt>Sells</dt>
          <dd>
            {sells.length === 0 ? (
              <span className="subtle">Nothing, paid in kind</span>
            ) : (
              sells.map((s, i) => (
                <div key={i} className="num">
                  {amt(s.amount)} {s.asset}
                </div>
              ))
            )}
          </dd>
        </div>
        <div>
          <dt>Pays</dt>
          <dd>
            {pays.map((s, i) => (
              <div key={i} className="num">
                {amt(s.amount)} {s.asset}
              </div>
            ))}
          </dd>
        </div>
        <div>
          <dt>Expected cost</dt>
          <dd className="num">
            {usd(cost, 4)}
            {p.expected_cost && typeof p.expected_cost === "object" && (
              <div className="kv-note">
                {usd(p.expected_cost.price_impact_usd, 4)} impact · {usd(p.expected_cost.fees_usd, 4)} fees
              </div>
            )}
          </dd>
        </div>
        <div>
          <dt>Price drift</dt>
          <dd>{d === null ? <span className="subtle">Not applicable</span> : <DriftBar value={d} threshold={threshold} />}</dd>
        </div>
      </dl>

      {driftDanger && (
        <div className="flag flag-block">
          <span className="flag-label">Drift now {live.toFixed(1)}%</span>
          <span>Above the {threshold}% limit. The router will refuse to sell tokenized stock at this gap.</span>
        </div>
      )}

      <Source source={p.source} />

      {p.alternatives?.length > 0 && (
        <details className="alts">
          <summary>
            {p.alternatives.length} other path{p.alternatives.length > 1 ? "s" : ""} considered
          </summary>
          {p.alternatives.map((a, i) => (
            <div key={i} className="alt">
              <div className="alt-path num">
                {(a.path || []).map((s) => `${s.type === "swap" ? "sell" : "pay"} ${amt(s.amount)} ${s.asset}`).join("  →  ")}
              </div>
              <div className="alt-why">{a.rejected_reason}</div>
            </div>
          ))}
        </details>
      )}

      {err && <div className="error">{err}</div>}

      {!rejecting ? (
        <div className="pc-actions">
          <button className="btn btn-ghost" disabled={busy} onClick={() => setRejecting(true)}>
            Reject
          </button>
          <button className="btn btn-primary" disabled={busy} onClick={() => decide("approve")}>
            Approve and sign
          </button>
        </div>
      ) : (
        <div className="reject-box">
          <textarea
            autoFocus
            placeholder="Reason (optional). The agent is told why."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="pc-actions">
            <button className="btn btn-ghost" disabled={busy} onClick={() => setRejecting(false)}>
              Cancel
            </button>
            <button className="btn btn-danger" disabled={busy} onClick={() => decide("reject")}>
              Reject order
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
