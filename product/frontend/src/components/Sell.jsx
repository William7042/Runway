import React, { useEffect, useState } from "react";
import { usd, ago } from "../format.js";
import "../styles/sell.css";

// Seller tokens are this browser's convenience copy only; the backend stores just a hash.
const KEY = "runway.sellerTokens";
export const loadTokens = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}") || {};
  } catch {
    return {};
  }
};
const saveTokens = (t) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(t));
  } catch {
    /* private mode: keep in memory only */
  }
};

const JOB_LABEL = { awaiting_payment: "Waiting for buyer's payment", paid: "Paid, ready to deliver", complete: "Delivered", rejected: "Buyer rejected", failed: "Payment failed" };

function JobRow({ job, onDeliver }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState("");
  return (
    <div className="job">
      <div className="job-top">
        <div className="grow">
          <div className="job-title">{job.request}</div>
          <div className="job-sub">
            from {job.buyer} · {ago(job.created_at)} · {job.id}
          </div>
        </div>
        <div className="right">
          <div className="job-amt num">{usd(job.price_usd, 2)}</div>
          <span className={`pill ${job.status === "complete" ? "pill-ok" : job.status === "paid" ? "pill-warn" : "pill-soft"}`}>
            {JOB_LABEL[job.status] || job.status}
          </span>
        </div>
      </div>
      {job.status === "paid" && (
        <div className="inline-form col">
          <textarea placeholder="Delivery notes or the result your agent produced" value={text} onChange={(e) => setText(e.target.value)} />
          <label className="small">Attach deliverables (up to 5 files; 10 MiB each)
            <input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files || []))} />
          </label>
          {files.map((file) => <div className="small" key={file.name}>{file.name} · {Math.ceil(file.size / 1024)} KB</div>)}
          {error && <div className="error" role="alert">{error}</div>}
          <button
            className="btn btn-primary"
            disabled={busy || (!text.trim() && !files.length) || files.length > 5}
            onClick={async () => {
              setBusy(true);
              try {
                await onDeliver(job, text.trim(), files);
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Deliver result
          </button>
        </div>
      )}
      {job.status === "complete" && job.result && <div className="job-result">“{job.result}”</div>}
      {job.artifact_count > 0 && <div className="small muted">{job.artifact_count} file(s) attached to this delivery</div>}
    </div>
  );
}

/** Sell: your agent's own services, the paid jobs it has to deliver, and what it has earned. */
export default function Sell({ api, refreshKey }) {
  const [all, setAll] = useState([]);
  const [tokens, setTokens] = useState(loadTokens);
  const [credentialsSaved, setCredentialsSaved] = useState(false);
  useEffect(() => {
    let alive = true;
    const owned = Object.entries(tokens);
    if (!owned.length) return;
    const [id, token] = owned[owned.length - 1];
    api.health().then(h => h.demo_seller_autosave ? api.saveSellerCredentials(id, token) : null)
      .then(result => alive && setCredentialsSaved(Boolean(result?.credentials_saved)))
      .catch(() => alive && setCredentialsSaved(false));
    return () => { alive = false; };
  }, [api, Object.keys(tokens).join(",")]);
  const [jobs, setJobs] = useState({});
  const [jobTab, setJobTab] = useState("active");
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ name: "", capability: "", price_usd: "0.10", payout_user: "test2", accepts: "PYUSD", simulated: false });
  const [justRegistered, setJustRegistered] = useState(null);
  const [saving, setSaving] = useState(false);
  const [link, setLink] = useState({ id: "", token: "" });

  useEffect(() => {
    let alive = true;
    api.specialists().then((x) => alive && setAll(Array.isArray(x) ? x : [])).catch((e) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
  }, [api, refreshKey, tokens]);

  const mine = all.filter((s) => tokens[s.id]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const next = {};
      for (const s of mine) {
        try {
          next[s.id] = await api.sellerJobs(s.id, tokens[s.id]);
        } catch {
          next[s.id] = null;
        }
      }
      if (alive) setJobs(next);
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, refreshKey, all.length, Object.keys(tokens).join(",")]);

  function remember(id, token) {
    const t = { ...tokens, [id]: token };
    setTokens(t);
    saveTokens(t);
  }

  async function register() {
    setSaving(true);
    setErr("");
    try {
      const r = await api.registerSpecialist({
        ...form,
        price_usd: Number(form.price_usd),
        accepts: form.accepts.split(",").map((s) => s.trim()).filter(Boolean),
      });
      remember(r.id, r.owner_token);
      setJustRegistered(r);
      setCredentialsSaved(Boolean(r.credentials_saved));
      setForm({ ...form, name: "", capability: "" });
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggle(s) {
    try {
      await api.updateSpecialist(s.id, { owner_token: tokens[s.id], active: !s.active });
      setAll(await api.specialists());
    } catch (e) {
      setErr(e.message);
    }
  }

  async function deliver(job, result, files = []) {
    try {
      for (const file of files) await api.uploadArtifact(job.id, tokens[job.specialist_id], file);
      await api.submitResult(job.id, tokens[job.specialist_id], result);
      setJobs({ ...jobs, [job.specialist_id]: await api.sellerJobs(job.specialist_id, tokens[job.specialist_id]) });
    } catch (e) {
      setErr(e.message);
      throw e;
    }
  }

  const earned = mine.reduce((a, s) => a + Number(s.earned_usd || 0), 0);
  const delivered = mine.reduce((a, s) => a + Number(s.jobs_completed || 0), 0);
  const toDeliver = Object.values(jobs).flat().filter((j) => j && j.status === "paid").length;

  return (
    <div className="stack">
      <div className="stats sell-stats">
        <div className="stat">
          <div className="label">Earned</div>
          <div className="big good">{usd(earned, 2)}</div>
        </div>
        <div className="stat">
          <div className="label">Jobs delivered</div>
          <div className="big">{delivered}</div>
        </div>
        <div className="stat">
          <div className="label">Paid, waiting on you</div>
          <div className={`big ${toDeliver ? "warn-text" : ""}`}>{toDeliver}</div>
        </div>
        <div className="stat">
          <div className="label">Services listed</div>
          <div className="big">{mine.length}</div>
        </div>
      </div>

      {err && <div className="error">{err}</div>}

      {credentialsSaved && <p className="good small" role="status">Seller setup saved automatically. Codex can read .runway/demo-seller.json; no token copying needed.</p>}
      <div className="sell-layout">
        <section className="stack">
          <h2 className="section-title">Your services</h2>
          {mine.length === 0 && (
            <div className="empty">
              Your agent isn't selling anything yet. List a service on the right and other agents can hire it.
            </div>
          )}
          <div className="subtabs" role="tablist" aria-label="Seller orders">
            {[['active', 'Active'], ['completed', 'Completed']].map(([id, label]) => (
              <button key={id} role="tab" aria-selected={jobTab === id}
                className={`subtab ${jobTab === id ? 'active' : ''}`} onClick={() => setJobTab(id)}>
                {label} · {Object.values(jobs).flat().filter(j => j && (id === 'completed' ? j.status === 'complete' : j.status !== 'complete')).length}
              </button>
            ))}
          </div>
          {mine.map((s) => {
            const list = jobs[s.id];
            const visibleJobs = list?.filter(j => jobTab === 'completed' ? j.status === 'complete' : j.status !== 'complete');
            return (
              <article key={s.id} className="card listing">
                <div className="listing-top">
                  <div className="grow">
                    <h3>{s.name}</h3>
                    <div className="listing-sub">
                      {s.id} · pays out to {s.payout_user} {s.simulated && <span className="pill">simulated</span>}
                    </div>
                  </div>
                  <div className="right">
                    <div className="listing-price num">{usd(s.price_usd, 2)}</div>
                    <div className="listing-unit">{s.unit || "per job"} · {(s.accepts || []).join(", ")}</div>
                  </div>
                </div>
                <p className="listing-cap">{s.capability}</p>
                <div className="listing-rep">
                  <span>
                    <span className="num strong">{usd(s.earned_usd, 2)}</span> earned
                  </span>
                  <span>
                    <span className="num strong">{s.jobs_completed ?? 0}</span> delivered
                  </span>
                  <button className={`btn small ${s.active === false ? "" : "btn-ghost"}`} onClick={() => toggle(s)}>
                    {s.active === false ? "Turn on" : "Pause listing"}
                  </button>
                  {s.active === false && <span className="pill pill-soft">paused</span>}
                </div>
                <div className="jobs">
                  <div className="label">{jobTab === 'completed' ? 'Completed orders' : 'Active orders'}</div>
                  {list === null && <div className="muted small">Couldn't load orders. Is the seller token right?</div>}
                  {visibleJobs?.length === 0 && (
                    <div className="muted small">{jobTab === 'completed' ? 'No completed orders yet. Delivered work will appear here.' : 'No active orders. New work appears after payment confirms.'}</div>
                  )}
                  {visibleJobs?.map((j) => <JobRow key={j.id} job={j} onDeliver={deliver} />)}
                </div>
              </article>
            );
          })}
        </section>

        <aside className="stack">
          <section className="panel">
            <h2>List a service</h2>
            <p className="panel-note">
              Your agent does the work. Runway lists it, the buyer's payment goes through their own approval, and your result is only released after
              payment confirms.
            </p>
            <div className="inline-form col">
              <input aria-label="Service name" placeholder="Service name, e.g. Nvidia research brief" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <textarea aria-label="What it delivers" placeholder="What does the buyer get?" value={form.capability} onChange={(e) => setForm({ ...form, capability: e.target.value })} />
              <div className="inline-form">
                <input aria-label="Price in USD" type="number" min="0.01" max="5" step="0.01" value={form.price_usd} onChange={(e) => setForm({ ...form, price_usd: e.target.value })} />
                <select aria-label="Accepted token" value={form.accepts} onChange={(e) => setForm({ ...form, accepts: e.target.value })}>
                  {["USDC", "PYUSD", "SOL", "BTC", "ETH"].map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </div>
              <input aria-label="True Markets payout user" placeholder="Payout user (True Markets)" value={form.payout_user} onChange={(e) => setForm({ ...form, payout_user: e.target.value })} />
              <label className="small">
                <input type="checkbox" checked={form.simulated} onChange={(e) => setForm({ ...form, simulated: e.target.checked })} /> Simulated seller (demo only, no live delivery)
              </label>
              <button
                className="btn btn-primary"
                disabled={saving || form.name.trim().length < 2 || form.capability.trim().length < 8 || !form.payout_user.trim() || !(Number(form.price_usd) > 0)}
                onClick={register}
              >
                {saving ? "Listing…" : "List service"}
              </button>
            </div>
            {justRegistered && !credentialsSaved && (
              <div className="token-box" role="status">
                <div className="strong">Listed {justRegistered.name}</div>
                <p className="small">
                  This is your private seller token. It's shown once. Copy it somewhere safe: your agent needs it to fetch orders and deliver results.
                </p>
                <input aria-label="Private seller token" readOnly value={justRegistered.owner_token} onFocus={(e) => e.target.select()} />
              </div>
            )}
          </section>

          <details className="panel">
            <summary className="strong">Add a service you listed somewhere else</summary>
            <div className="inline-form col" style={{ marginTop: 12 }}>
              <input placeholder="Listing id (specialist-…)" value={link.id} onChange={(e) => setLink({ ...link, id: e.target.value.trim() })} />
              <input placeholder="Seller token" value={link.token} onChange={(e) => setLink({ ...link, token: e.target.value.trim() })} />
              <button
                className="btn small"
                disabled={!link.id || !link.token}
                onClick={() => {
                  remember(link.id, link.token);
                  setLink({ id: "", token: "" });
                }}
              >
                Add to this browser
              </button>
            </div>
          </details>
        </aside>
      </div>
    </div>
  );
}
