import React, { useState } from 'react';
import { usd, buyerWallet } from '../format.js';
import '../styles/hire-advisor.css';

export default function HireAdvisor({ compare, api, balances, proposals, onOpenApprovals }) {
  const [question, setQuestion] = useState('Which data should I buy to assess a company’s financial health?');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [purchase, setPurchase] = useState(null);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [preparing, setPreparing] = useState(false);
  async function analyze() {
    setBusy(true); setError(''); setResult(null); setSelected(null); setPurchase(null); setRequestId(crypto.randomUUID());
    try { setResult(await api.hireRecommendations(question)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function prepare(s) {
    setPreparing(true); setError(''); setSelected(s.id);
    try {
      const payment = await api.prepareHirePayment({ question, specialist_id: s.id, buyer: buyerWallet(balances).id, request_id: requestId });
      setPurchase(payment);
    } catch (e) { setError(e.message); }
    finally { setPreparing(false); }
  }
  const options = result?.options || [];
  return <section className="hire-advisor card">
    <h2>{compare ? 'Compare buying options' : 'Find your best fit'}</h2>
    <label htmlFor="hire-need">What do you need the data or specialist for?</label>
    <textarea id="hire-need" rows={2} maxLength={3000} value={question} disabled={busy || preparing || !!purchase} onChange={e => { setQuestion(e.target.value); setResult(null); setSelected(null); setPurchase(null); setRequestId(crypto.randomUUID()); }} />
    <button className="btn btn-primary" disabled={busy || preparing || question.trim().length < 8} onClick={analyze}>{busy ? 'Analyzing catalog…' : compare ? 'Compare best options' : 'Find best option'}</button>
    <p className="small muted">AI analyzes available listings; it has not inspected the underlying datasets. Every payment still needs your approval.</p>
    {error && <p role="alert" className="danger">{error}</p>}
    {result && <div aria-live="polite">
      {compare && <div className="hire-summary"><h3>How the options compare</h3><p>{result.comparison}</p></div>}
      {!options.length && <p>No suitable buying option found. Try a more specific request.</p>}
      {compare && options.length > 0 && options.length < 2 && <p className="muted">Only one relevant option was found; no alternatives were invented.</p>}
      <div className="hire-choice-grid">{(compare ? options : options.slice(0, 1)).map((o, index) => {
        const s = o.listing;
        return <article key={s.id} className={`hire-choice ${selected === s.id ? 'selected' : ''}`}>
          <span className="label">{index === 0 ? 'AI best fit' : `Alternative ${index}`}</span><h3>{s.name}</h3>
          {s.simulated && <span className="pill">Simulated data</span>}
          <p><strong>{usd(s.price_usd, 2)}</strong> {s.unit} <span className="small muted">· fees quoted at payment</span></p>
          <p>{o.reason}</p>
          {compare && <dl><dt>Data strengths</dt><dd>{o.strengths}</dd><dt>Weaknesses & unknowns</dt><dd>{o.weaknesses}</dd></dl>}
          <button className="btn btn-primary" disabled={preparing || !!purchase} onClick={() => prepare(s)}>{preparing && selected === s.id ? 'Preparing payment…' : compare ? 'Choose & review payment' : 'Review recommended payment'}</button>
          {selected === s.id && purchase && <div className="hire-selection"><p>Payment prepared for {s.name}. Review the quoted fees and approve or reject it in Approvals.</p><button className="btn btn-ghost" onClick={onOpenApprovals}>Review payment in Approvals</button></div>}

        </article>;
      })}</div>
    </div>}
  </section>;
}
