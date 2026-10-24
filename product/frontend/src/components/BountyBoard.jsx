import React, { useState } from "react";
import { usd, ago } from "../format.js";

const FLOW = ["open", "claimed", "submitted", "paid"];

function Stepper({ status }) {
  const steps = status === "refunded" ? ["open", "claimed", "submitted", "refunded"] : FLOW;
  const idx = steps.indexOf(status);
  return (
    <div className="stepper">
      {steps.map((s, i) => (
        <div key={s} className={`stepper-item ${i <= idx ? "done" : ""} ${i === idx ? "current" : ""} ${s === "refunded" ? "refund" : ""}`}>
          <div className="dot" />
          <span>{s}</span>
        </div>
      ))}
    </div>
  );
}

function BountyCard({ b, proposalsById, act }) {
  const [name, setName] = useState("");
  const [work, setWork] = useState("");
  const [reason, setReason] = useState("");
  const settlement = b.settlement_proposal_id && proposalsById[b.settlement_proposal_id];
  const funding = b.funding_proposal_id && proposalsById[b.funding_proposal_id];

  return (
    <article className="card bounty">
      <header className="card-head">
        <div>
          <div className="eyebrow">
            {b.id} · posted by {b.poster} {b.deadline && <>· due {b.deadline}</>}
          </div>
          <h3>{b.title}</h3>
          {b.description && <p className="small">{b.description}</p>}
        </div>
        <div className="amount">
          <div className="big">{usd(b.price_usd, 2)}</div>
          <div className="muted small">{b.asset}</div>
        </div>
      </header>

      <Stepper status={b.status} />

      <div className="small muted">
        Escrow wallet <span className="mono">{b.escrow_wallet}</span>
        {funding && <> · funding order <span className={`pill pill-${funding.status}`}>{funding.status}</span></>}
        {b.escrow_funded && <span className="pill pill-ok">funded</span>}
      </div>

      {b.claimant && (
        <div className="small">
          Claimed by <span className="strong">{b.claimant}</span>
        </div>
      )}
      {b.submission && <div className="submission">“{b.submission}”</div>}

      {b.status === "open" && (
        <div className="inline-form">
          <input placeholder="Your name (worker)" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn" disabled={!name.trim()} onClick={() => act(() => b.claim(name.trim()))}>
            Claim
          </button>
        </div>
      )}
      {b.status === "claimed" && (
        <div className="inline-form col">
          <textarea placeholder="Submit the work" value={work} onChange={(e) => setWork(e.target.value)} />
          <button className="btn" disabled={!work.trim()} onClick={() => act(() => b.submit(work.trim()))}>
            Submit work
          </button>
        </div>
      )}
      {b.status === "submitted" && !settlement && (
        <div className="inline-form col">
          <input placeholder="Note for the worker (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="actions">
            <button className="btn btn-approve" onClick={() => act(() => b.verify("approve", reason))}>
              Approve work
            </button>
            <button className="btn btn-reject" onClick={() => act(() => b.verify("reject", reason))}>
              Reject &amp; refund
            </button>
          </div>
          <div className="small muted">Approving work doesn't pay yet. It creates a payout order that you approve on the Desk.</div>
        </div>
      )}
      {settlement && b.status === "submitted" && (
        <div className="small">
          {settlement.bounty_role === "payout" ? "Payout" : "Refund"} order{" "}
          <span className={`pill pill-${settlement.status}`}>{settlement.status}</span>
          {settlement.status === "pending" && <> · approve it on the Desk tab</>}
        </div>
      )}

      <details className="alts">
        <summary>History</summary>
        {(b.history || []).map((h, i) => (
          <div key={i} className="small">
            <span className="pill pill-soft">{h.status}</span> {h.note} <span className="muted">{ago(h.at)}</span>
          </div>
        ))}
      </details>
    </article>
  );
}

export default function BountyBoard({ bounties, proposals, api, refresh }) {
  const [form, setForm] = useState({ title: "", description: "", price_usd: "0.25", asset: "USDC", deadline: "" });
  const [err, setErr] = useState("");
  const proposalsById = Object.fromEntries(proposals.map((p) => [p.id, p]));

  async function act(fn) {
    setErr("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setErr(e.message);
    }
  }

  const wrapped = bounties.map((b) => ({
    ...b,
    claim: (n) => api.claim(b.id, n),
    submit: (w) => api.submit(b.id, w),
    verify: (d, r) => api.verify(b.id, d, r),
  }));

  return (
    <div className="bounty-layout">
      <section className="panel">
        <div className="panel-head">
          <h2>Post a bounty</h2>
        </div>
        <p className="muted small">Funds go into a dedicated escrow wallet. Funding is an order like any other and needs approval.</p>
        <div className="inline-form col">
          <input placeholder="Task title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <textarea
            placeholder="What exactly should the worker do?"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <div className="inline-form">
            <input type="number" step="0.01" min="0.01" value={form.price_usd} onChange={(e) => setForm({ ...form, price_usd: e.target.value })} />
            <select value={form.asset} onChange={(e) => setForm({ ...form, asset: e.target.value })}>
              <option>USDC</option>
              <option>NVDAc</option>
            </select>
            <input placeholder="Deadline" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
          </div>
          <button
            className="btn btn-approve"
            disabled={!form.title.trim() || !(Number(form.price_usd) > 0)}
            onClick={() =>
              act(async () => {
                await api.postBounty({ ...form, price_usd: Number(form.price_usd) });
                setForm({ ...form, title: "", description: "" });
              })
            }
          >
            Post bounty
          </button>
        </div>
        {err && <div className="error">{err}</div>}
      </section>

      <div className="stack">
        {wrapped.length === 0 && <div className="empty">No bounties yet.</div>}
        {wrapped.map((b) => (
          <BountyCard key={b.id} b={b} proposalsById={proposalsById} act={act} />
        ))}
      </div>
    </div>
  );
}
