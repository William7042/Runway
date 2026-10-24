import React, { useEffect, useRef, useState } from "react";
import { usd, ago } from "../format.js";
import "../styles/bounty.css";

const FLOW = ["open", "claimed", "submitted", "paid"];

// Deadlines are stored as local date-time strings ("2026-10-24T16:00") from a date picker.
// Older free-text deadlines (e.g. "Today 4:00 PM") are shown as-is.
const pad = (n) => String(n).padStart(2, "0");
const toLocalInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const timeLabel = (hhmm) => {
  const [h, m] = hhmm.split(":").map(Number);
  return new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
};
// Every 15 minutes, 00:00 to 23:45.
const TIMES = Array.from({ length: 96 }, (_, i) => `${pad(Math.floor(i / 4))}:${pad((i % 4) * 15)}`);
// Round up to the next quarter hour.
const nextQuarter = (d) => {
  const x = new Date(d);
  x.setSeconds(0, 0);
  x.setMinutes(Math.ceil((x.getMinutes() + 1) / 15) * 15);
  return x;
};

// "2:37 pm", "2:37p", "3pm", "930a", "14:37", "1437", "9" -> "HH:MM" or null.
function parseTime(text) {
  const t = text.trim().toLowerCase().replace(/\s+/g, "").replace(/\./g, "");
  const m = t.match(/^(\d{1,2})(?::?(\d{2}))?(am|pm|a|p)?$/);
  if (!m) return null;
  let h = Number(m[1]);
  const min = m[2] ? Number(m[2]) : 0;
  const ap = m[3];
  if (min > 59) return null;
  if (ap) {
    if (h < 1 || h > 12) return null;
    if (ap.startsWith("p") && h !== 12) h += 12;
    if (ap.startsWith("a") && h === 12) h = 0;
  } else if (h > 23) return null;
  return `${pad(h)}:${pad(min)}`;
}

/** Type a time, or pick from a list of 15-minute steps. */
function TimeInput({ value, onChange, options, disabled, earliest }) {
  const [text, setText] = useState(value ? timeLabel(value) : "");
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(-1);
  const [err, setErr] = useState("");
  const [typing, setTyping] = useState(false);
  const listRef = useRef(null);
  const wrapRef = useRef(null);
  const committed = useRef(false); // set when Enter/click already saved, so blur doesn't re-save the typed text

  useEffect(() => {
    if (!typing) setText(value ? timeLabel(value) : "");
  }, [value, typing]);

  // While typing, narrow the list to times that start like what was typed ("3" -> 3:00, 3:15…).
  const q = text.trim().toLowerCase().replace(/\s+/g, "");
  const shown = typing && q ? options.filter((t) => timeLabel(t).toLowerCase().replace(/\s+/g, "").startsWith(q) || t.startsWith(q)) : options;

  useEffect(() => {
    if (!open || !listRef.current) return;
    const idx = hi >= 0 ? hi : shown.indexOf(value);
    const el = listRef.current.children[idx >= 0 ? idx : 0];
    if (el) el.scrollIntoView({ block: "nearest" });
  }, [open, hi, value, shown.length]);

  useEffect(() => {
    const close = (e) => wrapRef.current && !wrapRef.current.contains(e.target) && setOpen(false);
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  function commit(raw) {
    committed.current = true;
    setTyping(false);
    setOpen(false);
    setHi(-1);
    if (!raw.trim()) return setText(value ? timeLabel(value) : "");
    const t = parseTime(raw);
    if (!t) {
      setErr("Try a time like 2:30 PM or 14:30");
      return setText(value ? timeLabel(value) : "");
    }
    if (earliest && t < earliest) {
      setErr("That time has already passed today");
      return setText(value ? timeLabel(value) : "");
    }
    setErr("");
    onChange(t);
    setText(timeLabel(t));
  }

  return (
    <div className="time-input" ref={wrapRef}>
      <input
        type="text"
        inputMode="text"
        aria-label="Due time"
        placeholder="Time"
        disabled={disabled}
        value={text}
        onFocus={(e) => {
          committed.current = false;
          setOpen(true);
          e.target.select();
        }}
        onChange={(e) => {
          setTyping(true);
          setText(e.target.value);
          setOpen(true);
          setHi(-1);
          setErr("");
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            const step = e.key === "ArrowDown" ? 1 : -1;
            const last = shown.length - 1;
            setHi((h) => {
              if (h < 0) {
                const sel = shown.indexOf(value);
                return sel < 0 ? (step > 0 ? 0 : last) : Math.min(last, Math.max(0, sel + step));
              }
              return Math.min(last, Math.max(0, h + step));
            });
          } else if (e.key === "Enter") {
            e.preventDefault();
            if (open && hi >= 0 && shown[hi]) commit(shown[hi]);
            else commit(text);
            e.currentTarget.blur();
          } else if (e.key === "Escape") {
            setOpen(false);
            setTyping(false);
            setText(value ? timeLabel(value) : "");
          } else if (e.key === "Tab") {
            if (open && hi >= 0 && shown[hi]) commit(shown[hi]);
            else commit(text);
          }
        }}
        onBlur={() => {
          if (typing && !committed.current) commit(text);
        }}
      />
      <button type="button" className="time-toggle" aria-label="Show times" tabIndex={-1} disabled={disabled} onClick={() => setOpen(!open)}>
        ▾
      </button>
      {open && !disabled && shown.length > 0 && (
        <ul className="time-list" role="listbox" ref={listRef}>
          {shown.map((t, i) => (
            <li
              key={t}
              role="option"
              aria-selected={t === value}
              className={`${t === value ? "selected" : ""} ${i === hi ? "hi" : ""}`}
              onPointerDown={(e) => {
                e.preventDefault();
                commit(t);
              }}
            >
              {timeLabel(t)}
            </li>
          ))}
        </ul>
      )}
      {err && <div className="time-err">{err}</div>}
    </div>
  );
}

/** Date picker + typeable time (with a 15-minute list) + one-click presets. Value is "YYYY-MM-DDTHH:MM" (local) or "". */
function DeadlinePicker({ value, onChange }) {
  const now = new Date();
  const today = toLocalInput(now).slice(0, 10);
  const [date, time] = value ? value.split("T") : ["", ""];
  const earliestQuarter = toLocalInput(nextQuarter(now)).slice(11, 16);
  const earliestTyped = toLocalInput(new Date(now.getTime() + 60 * 1000)).slice(11, 16);
  const times = date === today ? TIMES.filter((t) => t >= earliestQuarter) : TIMES;

  const setDate = (d) => {
    if (!d) return onChange("");
    let t = time || "17:00";
    if (d === today && t < earliestTyped) t = earliestQuarter;
    onChange(`${d}T${t}`);
  };
  const setTime = (t) => onChange(`${date || today}T${t}`);

  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const presets = [
    ["In 1 hour", toLocalInput(nextQuarter(new Date(now.getTime() + 60 * 60 * 1000)))],
    ["Today 5 PM", now.getHours() < 17 ? `${today}T17:00` : null],
    ["Tomorrow 9 AM", `${toLocalInput(tomorrow).slice(0, 10)}T09:00`],
    ["In 1 week", `${toLocalInput(new Date(now.getTime() + 7 * 864e5)).slice(0, 10)}T17:00`],
  ].filter(([, v]) => v);

  return (
    <div className="deadline-field">
      <span className="label">Due</span>
      <div className="deadline-row">
        <input type="date" aria-label="Due date" min={today} value={date} onChange={(e) => setDate(e.target.value)} />
        <TimeInput value={time} onChange={setTime} options={times} disabled={!date} earliest={date === today ? earliestTyped : null} />
      </div>
      <div className="deadline-presets">
        {presets.map(([label, v]) => (
          <button key={label} type="button" className={`chip-btn ${value === v ? "active" : ""}`} onClick={() => onChange(v)}>
            {label}
          </button>
        ))}
        {value && (
          <button type="button" className="chip-btn" onClick={() => onChange("")}>
            No deadline
          </button>
        )}
      </div>
      {value && <div className="deadline-preview">Due {formatDeadline(value)}</div>}
    </div>
  );
}

function formatDeadline(value) {
  if (!value) return "";
  const d = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) ? new Date(value) : null;
  if (!d || Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function Stepper({ status }) {
  const steps = ["refunded", "rejected"].includes(status) ? ["open", "claimed", "submitted", status] : FLOW;
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
            {b.id} · posted by {b.poster} {b.deadline && <>· due {formatDeadline(b.deadline)}</>}
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
        {b.payment_mode === "direct" ? "Direct payment after work review and your payment approval. Reward funds remain in the poster’s wallet; they are not reserved." : <>
          Legacy escrow entry <span className="mono">{b.escrow_wallet}</span>
          {funding && <> · funding order <span className={`pill pill-${funding.status}`}>{funding.status}</span></>}
          {b.escrow_funded && <span className="pill pill-ok">funded</span>}
        </>}
      </div>

      {b.claimant && (
        <div className="small">
          Claimed by <span className="strong">{b.claimant}</span>
        </div>
      )}
      {b.submission && <div className="submission">“{b.submission}”</div>}

      {b.status === "open" && (
        <div className="inline-form">
          <input placeholder="Registered worker user (e.g. test2)" value={name} onChange={(e) => setName(e.target.value)} />
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
              {b.payment_mode === "direct" ? "Reject work" : "Reject & refund"}
            </button>
          </div>
          <div className="small muted">Approving work doesn't pay yet. It creates a payout order that you approve on the Desk.</div>
        </div>
      )}
      {settlement && b.status === "submitted" && (
        <div className="small">
          {settlement.bounty_role === "payout" ? "Payout" : "Refund"} order{" "}
          <span className={`pill pill-${settlement.status}`}>{settlement.status}</span>
          {settlement.status === "pending" && <> · approve it in Approvals</>}
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
  const [form, setForm] = useState({ title: "", description: "", price_usd: "4", asset: "PYUSD", poster: "test", deadline: "" });
  const minDeadline = toLocalInput(new Date());
  const deadlineOk = !form.deadline || form.deadline >= minDeadline;
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
        <p className="muted small">Post a reward, review the submitted work, then approve a direct payment to the worker. The $4 PYUSD demo reward has a separately quoted $1 transfer fee.</p>
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
              <option>PYUSD</option>
              <option>SOL</option>
              <option>BTC</option>
              <option>ETH</option>
            </select>
            <input aria-label="Poster payout user" placeholder="Poster user (test)" value={form.poster} onChange={(e) => setForm({ ...form, poster: e.target.value })} />
            <DeadlinePicker value={form.deadline} onChange={(deadline) => setForm({ ...form, deadline })} />
          </div>
          <button
            className="btn btn-approve"
            disabled={!form.title.trim() || !(Number(form.price_usd) > 0) || !deadlineOk}
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
