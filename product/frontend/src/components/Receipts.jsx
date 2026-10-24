import React from "react";
import { usd, ago } from "../format.js";

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
        <span className={`pill ${r.status === "failed" ? "pill-bad" : "pill-ok"}`}>{r.status}</span>
        <span className="strong">{usd(p.amount_usd)}</span>
        <span className="muted small">→ {p.seller}</span>
        <span className="muted small push">{ago(r.at)}</span>
      </div>
      <div className="small">{p.purpose}</div>
      <div className="receipt-q small">
        <span>quote cost <span className="mono">{usd(q, 5)}</span></span>
        <span>fill cost <span className="mono">{usd(f, 5)}</span></span>
        {diff !== null && (
          <span className={diff > 0 ? "danger" : "good"}>
            {diff > 0 ? "+" : ""}
            {usd(diff, 5)} {diff > 0 ? "slippage" : "improvement"}
          </span>
        )}
      </div>
      <TxHash hash={r.tx_hash} stub={r.stub} />
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
