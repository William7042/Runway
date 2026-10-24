import React, { useEffect, useState } from "react";
import { usd, amt } from "../format.js";
import "../styles/specialists.css";

const treasuryOf = (balances) => {
  const w = balances?.["research-agent"];
  const total = (w?.assets || []).reduce((a, x) => a + Number(x.usd_value || 0), 0);
  return { w, total, spendable: w?.cost_basis_usd !== undefined ? Math.max(0, total - w.cost_basis_usd) : total };
};

/** Specialist agents the research agent can hire, with their wallets front and center. */
export default function Specialists({ api, balances, refreshKey, onOpenApprovals }) {
  const [list, setList] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    api
      .specialists()
      .then((x) => alive && (setList(Array.isArray(x) ? x : []), setErr("")))
      .catch((e) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
  }, [api, refreshKey]);

  const t = treasuryOf(balances);

  return (
    <div className="stack">
      <section className="treasury-banner">
        <div>
          <div className="tb-label">Research agent can spend</div>
          <div className="tb-amount num">{usd(t.spendable, 2)}</div>
          <div className="tb-sub">
            of {usd(t.total, 2)} in its wallet · principal {usd(t.w?.cost_basis_usd, 2)} stays invested
          </div>
        </div>
        <div className="tb-assets">
          {(t.w?.assets || []).map((a) => (
            <div key={a.asset} className="tb-asset">
              <span className={`asset-dot dot-${a.asset.toLowerCase()}`} />
              <span className="strong">{a.asset}</span>
              <span className="num">{amt(a.amount)}</span>
              <span className="num muted">{usd(a.usd_value, 2)}</span>
            </div>
          ))}
        </div>
      </section>

      {err && <div className="error">{err}</div>}

      <div className="spec-grid">
        {list.map((s) => (
          <article key={s.id} className="card spec">
            <div className="spec-top">
              <div className="spec-avatar" aria-hidden="true">
                {s.name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
              </div>
              <div className="grow">
                <h3>{s.name}</h3>
                <div className="spec-id">
                  {s.id} {s.simulated && <span className="pill">simulated</span>}
                </div>
              </div>
            </div>

            <div className="spec-wallet">
              <div className="spec-wallet-label">Wallet balance</div>
              <div className="spec-wallet-amount num">{usd(s.wallet_usd, 2)}</div>
              <div className="spec-wallet-assets">
                {(s.wallet?.assets || []).map((a) => (
                  <span key={a.asset} className="chip num">
                    <span className={`asset-dot dot-${a.asset.toLowerCase()}`} />
                    {amt(a.amount)} {a.asset}
                  </span>
                ))}
              </div>
            </div>

            <p className="spec-cap">{s.capability}</p>

            <dl className="spec-facts">
              <div>
                <dt>Price</dt>
                <dd className="num">
                  {usd(s.price_usd, 2)} <span className="muted">{s.unit}</span>
                </dd>
              </div>
              <div>
                <dt>Accepts</dt>
                <dd>{s.accepts.join(", ")}</dd>
              </div>
              <div>
                <dt>Has that the agent doesn't</dt>
                <dd>{s.private_asset}</dd>
              </div>
            </dl>

            <div className="spec-rep">
              <div>
                <span className="num strong">{s.jobs}</span> jobs
              </div>
              <div>
                <span className="num strong">{s.success_rate ?? "—"}%</span> delivered
              </div>
              <div>
                <span className="num strong">{usd(s.earned_usd, 2)}</span> earned
              </div>
            </div>

            {s.pending > 0 && (
              <button className="spec-pending" onClick={onOpenApprovals}>
                {s.pending} payment{s.pending > 1 ? "s" : ""} to this specialist waiting for you →
              </button>
            )}
          </article>
        ))}
      </div>
      <p className="small muted">Reputation comes from the payment ledger (jobs paid, refunds issued), not from the seller's own claims.</p>
    </div>
  );
}
