import React from "react";
import { usd, amt, parseFlag, sourceInfo, SOURCE_LABEL, ago } from "../format.js";

function Highlight({ text, needle }) {
  if (!needle || !text || !text.includes(needle)) return <>{text}</>;
  const [before, ...rest] = text.split(needle);
  return (
    <>
      {before}
      <mark className="injected">{needle}</mark>
      {rest.join(needle)}
    </>
  );
}

export default function BlockedCard({ p }) {
  const s = sourceInfo(p.source);
  const flags = (p.flags || []).map(parseFlag);
  return (
    <article className="card blocked">
      <div className="blocked-banner">
        <span className="blocked-icon">⛔</span>
        <div>
          <div className="blocked-title">Blocked by policy</div>
          <div className="small">This order never reached a human. It cannot be approved. {ago(p.created_at)}</div>
        </div>
      </div>

      <div className="blocked-grid">
        <div>
          <div className="label">What the agent was told to do</div>
          <h3>{p.purpose}</h3>
          <div className="blocked-amount">
            {(p.path || []).map((st, i) => (
              <div key={i} className="mono">
                {st.type === "swap" ? "SELL" : "SEND"} {amt(st.amount)} {st.asset}
                {st.type === "transfer" && <> → {p.seller}</>}
              </div>
            ))}
            <div className="big danger">{usd(p.amount_usd)}</div>
          </div>
        </div>

        <div>
          <div className="label">Where the instruction came from · {SOURCE_LABEL[s.kind] || s.kind}</div>
          {s.url && <div className="mono small url">{s.url}</div>}
          <div className="page-snippet">
            <Highlight text={s.text} needle={s.injected} />
          </div>
          {s.injected && <div className="small muted">Highlighted text was hidden on the page (display:none).</div>}
        </div>
      </div>

      <div className="label">Why it was stopped</div>
      <ol className="why">
        {flags.map((f, i) => (
          <li key={i} className={`why-${f.kind}`}>
            <strong>{f.label}.</strong> {f.text}
          </li>
        ))}
      </ol>
      <div className="small muted">
        Spend caps and allowlists are plain code. The language model cannot talk its way past them.
      </div>
    </article>
  );
}
