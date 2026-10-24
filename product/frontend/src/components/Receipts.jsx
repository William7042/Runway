import React from "react";
import { usd, ago } from "../format.js";
import "../styles/desk.css";

const cost = (x) => (x && typeof x === "object" ? x.cost_usd ?? x.total_usd ?? x.price : x);

export function TxHash({ hash, stub }) {
  if (!hash) return <span className="muted">no tx</span>;
  const short = hash.length > 18 ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : hash;
  return (
    <span className="tx mono" title={hash}>
      {short}
      {(stub || hash.startsWith("STUB")) && <span className="pill pill-soft">stub</span>}
    </span>
  );
}

export function ReceiptRow({ p }) {
  const r = p.receipt || {};
  const q = cost(r.quote);
  const f = cost(r.fill);
  const diff = typeof q === "number" && typeof f === "number" ? f - q : null;
  return (
    <div className={`receipt ${r.status === "failed" ? "failed" : ""}`}>
      <div className="receipt-top">
        <div className="grow">
          <div className="receipt-title">{p.seller}</div>
          <div className="receipt-sub">{ago(r.at)} · <TxHash hash={r.tx_hash} stub={r.stub} /></div>
        </div>
        <div className="right">
          <div className="receipt-amt num">{usd(p.amount_usd)}</div>
          {r.status === "failed" ? (
            <span className="pill pill-bad">failed</span>
          ) : (
            diff !== null && (
              <div className={`receipt-diff num ${diff > 0 ? "danger" : "good"}`}>
                {diff === 0 ? "filled at quote" : `${diff > 0 ? "+" : ""}${usd(diff, 5)} vs quote`}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

export default function ReceiptsFeed({ receipts }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Live receipts</h2>
        <span className="pill pill-soft">{receipts.length}</span>
      </div>
      {receipts.length === 0 && <div className="muted small">Approved orders show up here once they fill.</div>}
      <div className="receipts">
        {receipts.slice(0, 8).map((p) => (
          <ReceiptRow key={p.id} p={p} />
        ))}
      </div>
    </section>
  );
}
