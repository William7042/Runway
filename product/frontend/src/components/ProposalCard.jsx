import React, { useState } from "react";
import { usd, amt, parseFlag, costTotal, driftPct, sourceInfo, SOURCE_LABEL, ago } from "../format.js";
import { DriftBar } from "./DriftGauge.jsx";
import "../styles/desk.css";

export const titleOf = (p) => p.title || `Pay ${p.seller}`;

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

// Apply the demo reference-price guard to supported volatile assets.
const isVolatile = (asset) => ["SOL", "BTC", "ETH"].includes(asset);

/** Wallet → (sell) → pay → seller, drawn as a row of nodes. */
function PaymentFlow({ p }) {
  const sells = (p.path || []).filter((s) => s.type === "swap");
  const pays = (p.path || []).filter((s) => s.type === "transfer");
  const nodes = [{ kind: "wallet", top: "From", main: p.buyer }];
  sells.forEach((s) => nodes.push({ kind: "sell", top: "Sell", main: `${amt(s.amount)} ${s.asset}`, sub: s.to_asset ? `for ${s.to_asset}` : null }));
  pays.forEach((s) =>
    nodes.push({ kind: "pay", top: sells.length ? "Pay" : "Pay in kind", main: `${amt(s.amount)} ${s.asset}`, sub: sells.length ? null : "nothing is sold" })
  );
  nodes.push({ kind: "seller", top: "To", main: p.seller });
  return (
    <div className="flow" aria-label="How this payment moves">
      {nodes.map((n, i) => (
        <React.Fragment key={i}>
          {i > 0 && <div className="flow-arrow" aria-hidden="true" />}
          <div className={`flow-node flow-${n.kind}`}>
            <div className="flow-top">{n.top}</div>
            <div className="flow-main num">{n.main}</div>
            {n.sub && <div className="flow-sub">{n.sub}</div>}
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}

export default function ProposalCard({ p, config, onDecide, position, total }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const cost = costTotal(p.expected_cost);
  const d = driftPct(p.drift);
  const live = config?.drift_pct;
  const threshold = config?.drift_threshold_pct ?? 2;
  const sellsStock = (p.path || []).some((s) => s.type === "swap" && isVolatile(s.asset));
  const driftDanger = sellsStock && live !== undefined && live > threshold;
  const src = sourceInfo(p.source);
  const why = p.rationale || p.purpose;

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
    <article className="card decision">
      <div className="dc-head">
        <div className="dc-head-text">
          <div className="dc-eyebrow">
            {total > 1 && <span className="dc-pos">{position} of {total}</span>}
            <span>{p.buyer} is asking · {ago(p.created_at)}</span>
            {p.bounty_role && <span className="pill">bounty {p.bounty_role}</span>}
          </div>
          <h2 className="dc-title">{titleOf(p)}</h2>
          <div className="dc-to">to {p.seller}</div>
        </div>
        <div className="dc-amount num">{usd(p.amount_usd)}</div>
      </div>

      <div className="reason">
        <div className="reason-label">Why the agent wants this</div>
        <p>{why}</p>
      </div>

      <Flags flags={p.flags} />
      {driftDanger && (
        <div className="flag flag-block">
          <span className="flag-label">Price drift {live.toFixed(1)}%</span>
          <span>The simulated quote is too far from its reference price. Review the route before selling.</span>
        </div>
      )}

      <PaymentFlow p={p} />

      {(p.flags || []).some((f) => String(f).startsWith("SIMULATED")) && (
        <div className="sim-banner muted small">
          This path is <span className="pill pill-soft">simulated</span> — stub router / demo balances, not a live True Markets fill.
        </div>
      )}

      <div className="dc-facts">
        <div>
          <span className="fact-label">Fees and price impact</span>
          <span className="fact-value num">{usd(cost, 4)}</span>
        </div>
        {d !== null && (
          <div className="fact-drift">
            <span className="fact-label">Price drift</span>
            <DriftBar value={d} threshold={threshold} />
          </div>
        )}
        <div>
          <span className="fact-label">Triggered by</span>
          <span className={`fact-value ${src.kind === "fetched_page" ? "danger" : ""}`}>{SOURCE_LABEL[src.kind] || src.kind}</span>
        </div>
      </div>

      {p.alternatives?.length > 0 && (
        <div className="alts-block">
          <div className="fact-label">Rejected alternatives</div>
          {p.alternatives.map((a, i) => (
            <div key={i} className="alt">
              <div className="alt-path num">
                {(a.path || []).map((s) => `${s.type === "swap" ? "sell" : "pay"} ${amt(s.amount)} ${s.asset}`).join("  →  ")}
              </div>
              <div className="alt-why">{a.rejected_reason}</div>
            </div>
          ))}
        </div>
      )}

      <details className="alts dc-more">
        <summary>More details</summary>
        <div className="more-grid">
          {src.text && (
            <div>
              <div className="fact-label">What triggered it</div>
              <div className="more-quote">“{src.text}”</div>
            </div>
          )}
          {p.expected_cost && typeof p.expected_cost === "object" && (
            <div>
              <div className="fact-label">Cost breakdown</div>
              <div className="num">
                {usd(p.expected_cost.price_impact_usd, 4)} price impact + {usd(p.expected_cost.fees_usd, 4)} fees
              </div>
            </div>
          )}
        </div>
      </details>

      {err && <div className="error">{err}</div>}

      {!rejecting ? (
        <div className="dc-actions">
          <button className="btn btn-ghost btn-lg" disabled={busy} onClick={() => setRejecting(true)}>
            Reject
          </button>
          <button className="btn btn-primary btn-lg" disabled={busy} onClick={() => decide("approve")}>
            Approve and pay {usd(p.amount_usd)}
          </button>
        </div>
      ) : (
        <div className="reject-box">
          <textarea autoFocus placeholder="Reason (optional). The agent is told why." value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="dc-actions">
            <button className="btn btn-ghost btn-lg" disabled={busy} onClick={() => setRejecting(false)}>
              Cancel
            </button>
            <button className="btn btn-danger btn-lg" disabled={busy} onClick={() => decide("reject")}>
              Reject order
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
