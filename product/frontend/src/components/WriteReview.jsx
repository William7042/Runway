import React, { useEffect, useId, useState } from "react";

function savedTokens() {
  try { return JSON.parse(localStorage.getItem("runway.buyerTokens") || "{}"); } catch { return {}; }
}
export default function WriteReview({ specialist, api, onSubmitted }) {
  const id = useId();
  const [tokens, setTokens] = useState(savedTokens);
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState("");
  const [stars, setStars] = useState(5);
  const [review, setReview] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  useEffect(() => {
    let alive = true; setLoading(true);
    Promise.all(Object.entries(tokens).map(async ([jobId, token]) => {
      try { return await api.jobDelivery(jobId, token); } catch { return null; }
    })).then(results => {
      if (!alive) return;
      const eligible = results.filter(j => j && j.specialist_id === specialist.id && j.status === "complete" && !j.simulated && !j.rating && j.buyer !== j.seller);
      setJobs(eligible); setSelected(eligible[0]?.id || ""); setLoading(false);
    });
    return () => { alive = false; };
  }, [tokens, specialist.id, api]);
  async function importAccess(file) {
    setError("");
    try {
      if (!file || file.size > 16384) throw new Error("Choose your private buyer access JSON file.");
      const record = JSON.parse(await file.text());
      if (!/^job-[0-9a-f]{16}$/.test(record.job_id) || typeof record.buyer_token !== "string" || record.buyer_token.length < 20) throw new Error("Invalid buyer access file.");
      const next = { ...savedTokens(), [record.job_id]: record.buyer_token };
      localStorage.setItem("runway.buyerTokens", JSON.stringify(next)); setTokens(next);
    } catch (e) { setError(e.message); }
  }
  if (sent) return <p className="good small" role="status">Your review has been published. Thank you!</p>;
  return <form className="inline-form col" style={{ marginTop: 12 }} onSubmit={async e => {
    e.preventDefault(); if (!selected || busy) return;
    setBusy(true); setError("");
    try { await api.rateSpecialistJob(selected, tokens[selected], stars, review.trim()); setSent(true); onSubmitted(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }}>
    <label htmlFor={`${id}-purchase`}>Your completed purchase</label>
    <select id={`${id}-purchase`} value={selected} onChange={e => setSelected(e.target.value)} disabled={loading || !jobs.length}>
      {!jobs.length && <option value="">{loading ? "Checking purchases…" : "No eligible purchase connected"}</option>}
      {jobs.map(j => <option key={j.id} value={j.id}>{j.request.slice(0, 100)}</option>)}
    </select>
    {!loading && !jobs.length && <p className="small muted">Reviews require a completed paid purchase you haven't already rated. For MCP purchases, connect your saved buyer access file below. Older demo purchases may not have one.</p>}
    <label htmlFor={`${id}-stars`}>Rating</label>
    <select id={`${id}-stars`} value={stars} onChange={e => setStars(Number(e.target.value))}>
      {[5,4,3,2,1].map(n => <option key={n} value={n}>{n} star{n === 1 ? "" : "s"}</option>)}
    </select>
    <label htmlFor={`${id}-review`}>Your review</label>
    <textarea id={`${id}-review`} maxLength={2000} rows={3} placeholder="What went well? What could be better?" value={review} onChange={e => setReview(e.target.value)} />
    <button className="btn btn-primary small" disabled={!selected || busy || loading} type="submit">{busy ? "Publishing…" : "Publish review"}</button>
    <details className="small"><summary>Connect an MCP purchase</summary>
      <p>Choose the buyer access file saved by your agent. Its credentials stay private.</p>
      <input aria-label={`Connect purchase for ${specialist.name}`} type="file" accept="application/json,.json" onChange={e => importAccess(e.target.files?.[0])} />
    </details>
    {error && <p className="error" role="alert">{error}</p>}
  </form>;
}
