import React from "react";
import { usd, ago } from "../format.js";
import "../styles/desk.css";

const cost = (x) => (x && typeof x === "object" ? x.cost_usd ?? x.total_usd ?? x.price : x);
const num = (x, key) => (x && typeof x === "object" && typeof x[key] === "number" ? x[key] : null);

function explorerUrl(hash) {
  if (!hash || typeof hash !== "string") return null;
  if (hash.startsWith("STUB") || hash.startsWith("0xdryrun")) return null;
  // Solana base58 tx signatures are typically 87–88 chars; EVM is 0x + 64 hex.
  if (hash.startsWith("0x") && hash.length >= 66) return `https://etherscan.io/tx/${hash}`;
  if (hash.length >= 64 && !hash.startsWith("0x")) return `https://solscan.io/tx/${hash}`;
  return null;
}

export function TxHash({ hash, stub }) {
  if (!hash) return <span className="muted">no tx</span>;
  const short = hash.length > 18 ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : hash;
  const href = explorerUrl(hash);
  const isStub = stub || hash.startsWith("STUB") || hash.startsWith("0xdryrun");
  const inner = href ? (
    <a className="tx-link" href={href} target="_blank" rel="noreferrer" title={hash}>
      {short}
    </a>
  ) : (
    <span title={hash}>{short}</span>
  );
  return (
    <span className="tx mono">
      {inner}
      {isStub && <span className="pill pill-soft">simulated</span>}
    </span>
  );
}

export function ReceiptRow({ p }) {
  const r = p.receipt || {};
  const q = cost(r.quote);
  const f = cost(r.fill);
  const diff = typeof q === "number" && typeof f === "number" ? f - q : null;
  const fee = num(r.fill, "fee_usd") ?? num(r.quote, "fee_usd");
  const net = num(r.fill, "seller_net_usd") ?? num(r.quote, "seller_net_usd");
  const gross = num(r.fill, "gross_debit_usd") ?? num(r.quote, "gross_debit_usd");
  return (
    <div className={`receipt ${r.status === "failed" ? "failed" : ""}`}>
      <div className="receipt-top">
        <div className="grow">
          <div className="receipt-title">{p.seller}</div>
          <div className="receipt-sub">
            {ago(r.at)} · <TxHash hash={r.tx_hash} stub={r.stub || r.simulated} />
          </div>
          {(fee != null || net != null) && (
            <div className="receipt-fee muted small">
              {net != null && <>seller net {usd(net, 4)}</>}
              {fee != null && fee > 0 && <> · fee {usd(fee, 4)}</>}
              {gross != null && <> · gross {usd(gross, 4)}</>}
            </div>
          )}
          {r.note && <div className="receipt-note muted small">{r.note}</div>}
        </div>
        <div className="right">
          <div className="receipt-amt num">{usd(p.amount_usd)}</div>
          {r.status === "failed" ? (
            <span className="pill pill-bad">failed</span>
          ) : r.status === "dry_run" ? (
            <span className="pill pill-warn">dry run</span>
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
