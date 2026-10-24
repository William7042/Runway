import React, { useEffect, useState } from 'react';
import '../styles/agents.css';

const BASE = import.meta.env.VITE_AGENT_URL || 'http://127.0.0.1:8200';
async function request(path, options) {
  const r = await fetch(BASE + path, options);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || 'Agent service unavailable');
  return data;
}
const active = r => r && ['starting', 'planning', 'awaiting_approval', 'paying', 'working'].includes(r.status);

export default function TwoAgents() {
  const [question, setQuestion] = useState('Review Runway’s payment flow and identify the top three risks to address before our hackathon demo.');
  const [run, setRun] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const [h, list] = await Promise.all([request('/health'), request('/runs')]);
        if (alive) { setHealth(h); setRun(list[0] || null); }
      } catch { if (alive) setHealth(null); }
    };
    refresh(); const timer = setInterval(refresh, 2000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  async function start() {
    setBusy(true); setError('');
    try {
      const r = await request('/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
      setRun(r);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <main className="page agent-page">
    <div className="page-title"><h1>Two agents. One human in control.</h1><p>A buyer hires a specialist. You approve the payment before work begins.</p></div>
    <div className="agent-roles">
      <section><span className="label">BUYER / TEST</span><h2>Research lead</h2><p>Plans the task, requests payment, then summarizes the specialist’s answer.</p></section>
      <span className="agent-arrow" aria-hidden="true">→</span>
      <section><span className="label">SPECIALIST / TEST2</span><h2>Independent reviewer</h2><p>Uses a separate model conversation. Delivers after confirmed payment.</p></section>
    </div>
    <section className="agent-compose">
      <label htmlFor="agent-question" className="strong">What should they work on?</label>
      <textarea id="agent-question" value={question} maxLength={3000} onChange={e => setQuestion(e.target.value)} rows={3} />
      <div className="agent-action"><p><strong>$4 specialist + $1 transfer fee = $5 total</strong><br /><span className="small muted">Real PYUSD between your two wallets. Every new payment needs approval.</span></p>
      <button className="btn btn-primary" disabled={busy || active(run) || !health?.key_configured || question.trim().length < 8} onClick={start}>{busy ? 'Starting…' : active(run) ? 'Run in progress' : 'Start two-agent job'}</button></div>
      <p className="small muted">{health ? `${health.model} · ${health.dry_run ? 'DRY RUN: no funds sent' : 'Live payment mode'} · ${health.key_configured ? 'key saved (validated on request)' : 'model API key missing'}` : 'Agent service offline — start demo.two_agents on port 8200.'}</p>
      {error && <p role="alert" className="danger">{error}</p>}
    </section>
    {run && <section className="agent-run">
      <div className="agent-action"><h2>Current run</h2><span className="pill pill-soft">{run.status.replaceAll('_', ' ')}</span></div>
      <p className="muted">{run.question}</p>
      {run.proposal_id && <div className="agent-approval"><a className="btn btn-primary" href="#desk">Review payment in Approval desk</a><span className="mono small">{run.proposal_id}</span></div>}
      <ol className="agent-timeline">{run.events.map((e, i) => <li key={i}><div className="label">{e.actor} · {new Date(e.time * 1000).toLocaleTimeString()}</div><p>{e.text}</p></li>)}</ol>
      {run.receipt?.tx_hash && <p className="small">Payment receipt: <a target="_blank" rel="noreferrer" href={`https://solscan.io/tx/${run.receipt.tx_hash}`}>View Solana transaction ↗</a></p>}
      {run.status === 'failed' && <p className="small danger">Stopped ({run.error_type || 'error'}). Check the API key or receipt. Starting a new job creates a new payment proposal.</p>}
      {run.status === 'failed' && run.receipt?.status === 'executed' && <button className="btn btn-ghost" onClick={async () => {
        try { setError(''); await request(`/runs/${run.id}/retry-delivery`, { method: 'POST' }); } catch (e) { setError(e.message); }
      }}>Retry answer using the existing payment</button>}
    </section>}
  </main>;
}
