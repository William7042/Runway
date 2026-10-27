import React, { useEffect, useState } from "react";
import { usd, amt, buyerWallet } from "../format.js";
import "../styles/specialists.css";
import SellerReviews from "./SellerReviews.jsx";
import BuyerDeliveries from "./BuyerDeliveries.jsx";

const treasuryOf = (balances) => {
  const buyer = buyerWallet(balances);
  const { w, total } = buyer;
  return { ...buyer, spendable: total === null ? null : w?.cost_basis_usd !== undefined ? Math.max(0, total - w.cost_basis_usd) : total };
};

/** Specialist agents the research agent can hire. (Listing your own service lives on the Sell tab.) */
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
          <div className="tb-label">{t.id} · {t.partial ? "priced subtotal" : "available balance"}</div>
          <div className="tb-amount num">{usd(t.spendable, 2)}</div>
          <div className="tb-sub">
            {t.w?.cost_basis_usd !== undefined ? `Principal ${usd(t.w.cost_basis_usd, 2)} stays invested` : t.partial ? "Unpriced holdings are shown separately below" : "Real wallet balance"}
            {t.w?.snapshot_at && <> · updated {new Date(t.w.snapshot_at).toLocaleTimeString()}</>}
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

            <SellerReviews specialist={s} api={api} refreshKey={refreshKey} />

            {s.pending > 0 && (
              <button className="spec-pending" onClick={onOpenApprovals}>
                {s.pending} payment{s.pending > 1 ? "s" : ""} to this specialist waiting for you →
              </button>
            )}
          </article>
        ))}
      </div>
      <p className="small muted">Ratings come from completed real purchases. Payment and delivery statistics are shown separately.</p>
    </div>
  );
}
