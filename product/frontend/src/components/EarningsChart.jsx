import React, { useEffect, useMemo, useRef, useState } from "react";
import { usd } from "../format.js";
import "../styles/wallet.css";

// Time ranges: label, total span, bucket size. "all" sizes itself to the data.
const H = 3600 * 1000;
const D = 24 * H;
const RANGES = [
  { key: "1h", label: "1H", span: H, step: 5 * 60 * 1000 },
  { key: "24h", label: "24H", span: D, step: H },
  { key: "7d", label: "7D", span: 7 * D, step: D },
  { key: "14d", label: "14D", span: 14 * D, step: D },
  { key: "30d", label: "30D", span: 30 * D, step: D },
  { key: "all", label: "All", span: null, step: null },
];

// One series: net. Lime while ahead (validated for the dark surface), status red while behind.
const UP = "#7f9f15";
const DOWN = "#ff4d3d";

function bucketLabel(t, step) {
  const d = new Date(t);
  if (step < D) return d.toLocaleTimeString(undefined, { hour: "numeric", minute: step < H ? "2-digit" : undefined });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function fullLabel(t, step) {
  const d = new Date(t);
  return step < D
    ? d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}
function nice(v) {
  if (v <= 0) return 0;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}
const signed = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + usd(Math.abs(v), 2);

/** Running net (earned − spent) over time, with range tabs, crosshair tooltip and a table view. */
export default function EarningsChart({ events }) {
  const now = Date.now();
  const earliest = events.length ? Math.min(...events.map((e) => e.t)) : now;
  // Default to the smallest range that still shows all activity.
  const auto = (RANGES.find((r) => r.span && now - earliest <= r.span) || RANGES[RANGES.length - 1]).key;
  const [rangeKey, setRangeKey] = useState(null);
  const range = RANGES.find((r) => r.key === (rangeKey || auto));

  const wrapRef = useRef(null);
  const [width, setWidth] = useState(800);
  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, e.contentRect.width)));
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);
  const [hover, setHover] = useState(null);

  const data = useMemo(() => {
    let span = range.span;
    let step = range.step;
    if (!span) {
      span = Math.max(H, now - earliest + 60 * 1000);
      step = span <= 2 * H ? 5 * 60 * 1000 : span <= 2 * D ? H : D;
    }
    const start = now - span;
    const n = Math.ceil(span / step);
    const base = { earned: 0, spent: 0 };
    for (const e of events) if (e.t < start) base[e.kind] += e.amount;
    const tot = { ...base };
    const points = [];
    const sorted = [...events].filter((e) => e.t >= start).sort((a, b) => a.t - b.t);
    let i = 0;
    for (let b = 0; b <= n; b++) {
      const end = Math.min(now, start + b * step);
      const delta = { earned: 0, spent: 0 };
      while (i < sorted.length && sorted[i].t <= end) {
        tot[sorted[i].kind] += sorted[i].amount;
        delta[sorted[i].kind] += sorted[i].amount;
        i++;
      }
      points.push({ t: end, net: tot.earned - tot.spent, earned: tot.earned, spent: tot.spent, dEarned: delta.earned, dSpent: delta.spent });
    }
    return {
      points,
      step,
      inRange: { earned: tot.earned - base.earned, spent: tot.spent - base.spent },
      total: tot,
    };
  }, [events, range, now, earliest]);

  const height = 240;
  const pad = { l: 56, r: 76, t: 16, b: 28 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const nets = data.points.map((p) => p.net);
  const hi = nice(Math.max(0, ...nets) * 1.15);
  const lo = -nice(Math.max(0, -Math.min(0, ...nets)) * 1.15);
  const yTop = hi || (lo ? 0 : 0.1);
  const yBot = lo;
  const x = (t) => pad.l + ((t - data.points[0].t) / Math.max(1, data.points[data.points.length - 1].t - data.points[0].t)) * iw;
  const y = (v) => pad.t + ((yTop - v) / (yTop - yBot)) * ih;
  const zeroY = y(0);
  const line = data.points.map((p, j) => `${j ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.net).toFixed(1)}`).join("");
  const area = `${line}L${x(data.points[data.points.length - 1].t).toFixed(1)},${zeroY}L${x(data.points[0].t).toFixed(1)},${zeroY}Z`;
  const yTicks = [...new Set([yTop, yTop > 0 && yBot < 0 ? null : yTop / 2, 0, yBot < 0 ? yBot : null].filter((v) => v !== null))];
  const xTickEvery = Math.max(1, Math.ceil(data.points.length / Math.max(2, Math.floor(iw / 90))));
  const last = data.points[data.points.length - 1];
  // Hard color switch exactly at the zero line (same y in both gradients).
  const zeroFrac = Math.min(1, Math.max(0, (zeroY - pad.t) / ih));

  function onMove(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * width;
    let best = 0;
    data.points.forEach((p, j) => {
      if (Math.abs(x(p.t) - px) < Math.abs(x(data.points[best].t) - px)) best = j;
    });
    setHover(best);
  }

  const hp = hover != null ? data.points[hover] : null;
  const tipLeft = hp ? Math.min(Math.max(x(hp.t) - 105, 4), width - 214) : 0;
  const netRange = data.inRange.earned - data.inRange.spent;
  const netAll = data.total.earned - data.total.spent;

  return (
    <section className="panel earnings">
      <div className="earn-head">
        <div>
          <h2>Net earnings over time</h2>
          <div className={`earn-big num ${netRange < 0 ? "danger" : ""}`}>{signed(netRange)}</div>
          <div className="earn-sub">
            net in this range · {usd(data.inRange.earned, 2)} earned · {usd(data.inRange.spent, 2)} spent · {signed(netAll)} all time
          </div>
        </div>
        <div className="chips" role="tablist" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r.key} role="tab" aria-selected={range.key === r.key} className={`chip-btn ${range.key === r.key ? "active" : ""}`} onClick={() => setRangeKey(r.key)}>
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="earn-plot" ref={wrapRef}>
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`Running net ${signed(last.net)}: earned ${usd(last.earned, 2)}, spent ${usd(last.spent, 2)}`}
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id="net-stroke" gradientUnits="userSpaceOnUse" x1="0" y1={pad.t} x2="0" y2={pad.t + ih}>
              <stop offset={zeroFrac} stopColor={UP} />
              <stop offset={zeroFrac} stopColor={DOWN} />
            </linearGradient>
            <linearGradient id="net-fill" gradientUnits="userSpaceOnUse" x1="0" y1={pad.t} x2="0" y2={pad.t + ih}>
              <stop offset="0" stopColor="rgba(210, 255, 57, 0.22)" />
              <stop offset={zeroFrac} stopColor="rgba(210, 255, 57, 0.04)" />
              <stop offset={zeroFrac} stopColor="rgba(255, 77, 61, 0.04)" />
              <stop offset="1" stopColor="rgba(255, 77, 61, 0.22)" />
            </linearGradient>
          </defs>
          {yTicks.map((v) => (
            <g key={v}>
              <line className={v === 0 ? "earn-zero" : "earn-grid"} x1={pad.l} x2={width - pad.r} y1={y(v)} y2={y(v)} />
              <text className="earn-tick" x={pad.l - 8} y={y(v) + 4} textAnchor="end">
                {v === 0 ? "$0" : signed(v)}
              </text>
            </g>
          ))}
          {data.points.map((p, j) =>
            j % xTickEvery === 0 || j === data.points.length - 1 ? (
              <text key={p.t} className="earn-tick" x={x(p.t)} y={height - 8} textAnchor={j === 0 ? "start" : j === data.points.length - 1 ? "end" : "middle"}>
                {j === data.points.length - 1 ? "Now" : bucketLabel(p.t, data.step)}
              </text>
            ) : null
          )}
          <path d={area} fill="url(#net-fill)" />
          <path d={line} fill="none" stroke="url(#net-stroke)" strokeWidth="2" strokeLinejoin="round" />
          <circle cx={x(last.t)} cy={y(last.net)} r="4" fill={last.net < 0 ? DOWN : UP} stroke="#111317" strokeWidth="2" />
          <text className="earn-end" x={x(last.t) + 10} y={y(last.net) + 4}>
            {signed(last.net)}
          </text>
          {hp && (
            <g pointerEvents="none">
              <line className="earn-cross" x1={x(hp.t)} x2={x(hp.t)} y1={pad.t} y2={pad.t + ih} />
              <circle cx={x(hp.t)} cy={y(hp.net)} r="4.5" fill={hp.net < 0 ? DOWN : UP} stroke="#111317" strokeWidth="2" />
            </g>
          )}
          <rect x={pad.l} y={pad.t} width={iw} height={ih} fill="transparent" />
        </svg>
        {hp && (
          <div className="earn-tip" style={{ left: tipLeft }}>
            <div className="tip-when">{fullLabel(hp.t, data.step)}</div>
            <div className="tip-row">
              <i style={{ background: hp.net < 0 ? DOWN : UP }} />
              <span className={`tip-val num ${hp.net < 0 ? "danger" : ""}`}>{signed(hp.net)}</span>
              <span className="tip-lab">net so far</span>
            </div>
            <div className="tip-sub">
              {usd(hp.earned, 2)} earned · {usd(hp.spent, 2)} spent
            </div>
            {(hp.dEarned > 0 || hp.dSpent > 0) && (
              <div className="tip-sub">
                This period: {hp.dEarned > 0 && `+${usd(hp.dEarned, 2)} in`}
                {hp.dEarned > 0 && hp.dSpent > 0 && ", "}
                {hp.dSpent > 0 && `−${usd(hp.dSpent, 2)} out`}
              </div>
            )}
          </div>
        )}
        {events.length === 0 && <div className="earn-empty">No payments yet. List a service on the Sell tab and paid jobs will show up here.</div>}
      </div>

      <details className="alts">
        <summary>View as table</summary>
        <div className="table-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>When</th>
                <th className="right">In</th>
                <th className="right">Out</th>
                <th className="right">Net so far</th>
              </tr>
            </thead>
            <tbody>
              {data.points
                .filter((p) => p.dEarned || p.dSpent)
                .reverse()
                .map((p) => (
                  <tr key={p.t}>
                    <td>{fullLabel(p.t, data.step)}</td>
                    <td className="mono right">{usd(p.dEarned, 2)}</td>
                    <td className="mono right">{usd(p.dSpent, 2)}</td>
                    <td className="mono right">{signed(p.net)}</td>
                  </tr>
                ))}
              {!data.points.some((p) => p.dEarned || p.dSpent) && (
                <tr>
                  <td colSpan="4" className="muted">No activity in this range.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
