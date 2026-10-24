import React, { useState } from "react";
import { usd, amt, parseFlag, costTotal, driftPct, sourceInfo, SOURCE_LABEL, ago } from "../format.js";
import { DriftBar } from "./DriftGauge.jsx";

export function Steps({ path }) {
  const sells = (path || []).filter((s) => s.type === "swap");
  const pays = (path || []).filter((s) => s.type === "transfer");
  return (
    <div className="steps">
      <div className="step-col">
        <div className="label">Sells</div>
        {sells.length === 0 ? (
          <div className="muted">Nothing. Paid in kind, holdings stay invested.</div>
        ) : (
          sells.map((s, i) => (
            <div key={i} className="step sell">
              <span className="mono">{amt(s.amount)}</span> {s.asset}
              {s.to_asset && <span className="muted"> → {s.to_asset}</span>}
            </div>
          ))
        )}
      </div>
      <div className="arrow">→</div>
      <div className="step-col">
        <div className="label">Pays</div>
        {pays.length === 0 ? (
          <div className="muted">No transfer</div>
        ) : (
          pays.map((s, i) => (
            <div key={i} className="step pay">
              <span className="mono">{amt(s.amount)}</span> {s.asset}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function Flags({ flags }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className="flags">
      {flags.map((f, i) => {
        const p = parseFlag(f);
        return (
          <div key={i} className={`flag flag-${p.kind}`}>
            <span className="flag-label">{p.kind === "block" ? "⛔" : "⚠"} {p.label}</span>
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
      <div className="label">Triggered by · {SOURCE_LABEL[s.kind] || s.kind}</div>
      {s.url && <div className="mono small">{s.url}</div>}
      {s.text && <div className="source-text">“{s.text}”</div>}
    </div>
  );
}

function sellsTokenizedStock(path) {
  // Tokenized stocks use a lowercase "c" suffix, e.g. NVDAc, TSLAc.
  return (path || []).some((s) => s.type === "swap" && /^[A-Z]+c$/.test(s.asset));
}

export default function ProposalCard({ p, config, onDecide }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

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
    <article className={`card proposal ${p.flags?.length ? "has-flags" : ""}`}>
      <header className="card-head">
        <div>
          <div className="eyebrow">
            {p.buyer} → {p.seller}
            {p.bounty_role && <span className="pill pill-soft">bounty {p.bounty_role}</span>}
          </div>
          <h3>{p.purpose}</h3>
        </div>
        <div className="amount">
          <div className="big">{usd(p.amount_usd)}</div>
          <div className="muted small">{ago(p.created_at)}</div>
        </div>
      </header>

      <Flags flags={p.flags} />

      <Steps path={p.path} />

      <div className="meta-row">
        <div>
          <div className="label">Expected cost</div>
          <div className="mono">{usd(cost, 4)}</div>
          {p.expected_cost && typeof p.expected_cost === "object" && (
            <div className="muted small">
              impact {usd(p.expected_cost.price_impact_usd, 4)} · fees {usd(p.expected_cost.fees_usd, 4)}
            </div>
          )}
        </div>
        <div className="grow">
          <div className="label">Drift at quote (on-chain vs reference)</div>
          {d === null ? <div className="muted">n/a, no tokenized stock involved</div> : <DriftBar value={d} threshold={threshold} />}
        </div>
      </div>

      {driftDanger && (
        <div className="flag flag-block">
          <span className="flag-label">⛔ Drift now {live.toFixed(1)}%</span>
          <span>Above the {threshold}% limit. The router will refuse to sell tokenized stock at this gap.</span>
        </div>
      )}

      <Source source={p.source} />

      {p.alternatives?.length > 0 && (
        <details className="alts">
          <summary>{p.alternatives.length} alternative path{p.alternatives.length > 1 ? "s" : ""} rejected</summary>
          {p.alternatives.map((a, i) => (
            <div key={i} className="alt">
              <div className="alt-path mono small">
                {(a.path || []).map((s) => `${s.type === "swap" ? "sell" : "pay"} ${amt(s.amount)} ${s.asset}`).join("  →  ")}
              </div>
              <div className="small">{a.rejected_reason}</div>
            </div>
          ))}
        </details>
      )}

      {err && <div className="error">{err}</div>}

      {!rejecting ? (
        <div className="actions">
          <button className="btn btn-approve" disabled={busy} onClick={() => decide("approve")}>
            Approve &amp; sign
          </button>
          <button className="btn btn-ghost" disabled={busy} onClick={() => setRejecting(true)}>
            Reject
          </button>
        </div>
      ) : (
        <div className="reject-box">
          <textarea
            autoFocus
            placeholder="Why? (optional, the agent is told this reason)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="actions">
            <button className="btn btn-reject" disabled={busy} onClick={() => decide("reject")}>
              Confirm reject
            </button>
            <button className="btn btn-ghost" disabled={busy} onClick={() => setRejecting(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
