import React, { useEffect, useState } from "react";

const KEY = "runway.buyerTokens";
function savedTokens() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
}

function Delivery({ job, token, api, reload }) {
  const [error, setError] = useState("");
  const [stars, setStars] = useState(5);
  const [review, setReview] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview]);
  async function fileAction(file, show = false) {
    setError("");
    try {
      const blob = await api.downloadArtifact(job.id, file.id, token);
      if (show && /^(text\/(plain|csv)|application\/json)$/.test(file.mime_type) && blob.size <= 1024 * 1024) {
        setPreview({ text: await blob.text(), filename: file.filename });
      } else if (show && /^image\/(png|jpeg|gif|webp)$/.test(file.mime_type)) {
        setPreview({ url: URL.createObjectURL(new Blob([blob], { type: file.mime_type })), filename: file.filename });
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a"); link.href = url; link.download = file.filename; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (e) { setError(e.message); }
  }
  return <article className="card listing">
    <h3>{job.request}</h3>
    <p className="small muted">{job.status === "complete" ? "Delivered" : "Waiting for delivery"} · {job.seller}</p>
    {job.result && <p style={{ whiteSpace: "pre-wrap" }}>{job.result}</p>}
    {(job.artifacts || []).map((file) => <div className="panel" key={file.id}>
      <strong>{file.filename}</strong><div className="small muted">{file.mime_type} · {Math.ceil(file.size_bytes / 1024)} KB</div>
      {file.description && <p>{file.description}</p>}
      <button className="btn small" onClick={() => fileAction(file)}>Download</button>{" "}
      {(/^(text\/(plain|csv)|application\/json|image\/(png|jpeg|gif|webp))$/.test(file.mime_type)) && <button className="btn small" onClick={() => fileAction(file, true)}>Preview</button>}
    </div>)}
    {preview && <div className="panel"><button className="btn small" onClick={() => setPreview(null)}>Close preview</button>
      {preview.url ? <img src={preview.url} alt={preview.filename} style={{ maxWidth: "100%" }} /> : <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{preview.text}</pre>}
    </div>}
    {job.status === "complete" && !job.simulated && !job.rating && <div className="inline-form col">
      <label>Rate this purchase <select value={stars} onChange={(e) => setStars(Number(e.target.value))}>{[5,4,3,2,1].map((n) => <option key={n} value={n}>{n} stars</option>)}</select></label>
      <textarea maxLength={2000} placeholder="How useful was the delivered work?" value={review} onChange={(e) => setReview(e.target.value)} />
      <button className="btn small" disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await api.rateSpecialistJob(job.id, token, stars, review); await reload(); } catch(e) { setError(e.message); } finally { setBusy(false); } }}>Submit rating</button>
    </div>}
    {job.rating && <p className="good small">Your verified rating: {job.rating.stars}/5 · {job.rating.review}</p>}
    {error && <div className="error" role="alert">{error}</div>}
  </article>;
}

export default function BuyerDeliveries({ api, refreshKey }) {
  const [tokens, setTokens] = useState(savedTokens);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  async function reload() {
    const results = await Promise.all(Object.entries(tokens).map(async ([id, token]) => {
      try { return await api.jobDelivery(id, token); } catch { return null; }
    }));
    setJobs(results.filter(Boolean));
  }
  useEffect(() => { reload(); }, [api, refreshKey, tokens]);
  async function importFile(file) {
    setError("");
    try {
      if (!file || file.size > 16384) throw new Error("Choose a private buyer job credential JSON file");
      const value = JSON.parse(await file.text());
      if (!/^job-[0-9a-f]{16}$/.test(value.job_id) || typeof value.buyer_token !== "string" || value.buyer_token.length < 20) throw new Error("Invalid buyer job credentials");
      const next = { ...tokens, [value.job_id]: value.buyer_token };
      localStorage.setItem(KEY, JSON.stringify(next)); setTokens(next);
    } catch (e) { setError(e.message); }
  }
  return <section className="stack">
    <h2>Your deliveries</h2>
    <p className="muted small">Privately import the buyer job credential saved by your MCP agent to view files and rate a purchase. Credentials are never displayed.</p>
    <input aria-label="Import private buyer job credentials" type="file" accept="application/json,.json" onChange={(e) => importFile(e.target.files?.[0])} />
    {error && <div className="error">{error}</div>}
    {!jobs.length && <div className="empty">Completed purchases appear here once you import their buyer access file. Pending and unpaid jobs do not unlock files.</div>}
    {jobs.map((job) => <Delivery key={job.id} job={job} token={tokens[job.id]} api={api} reload={reload} />)}
  </section>;
}
