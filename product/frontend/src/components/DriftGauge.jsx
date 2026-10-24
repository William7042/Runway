import React, { useEffect, useState } from "react";
import "../styles/desk.css";

const MAX = 5; // gauge scale, in %

export function DriftBar({ value, threshold = 2 }) {
  const pct = Math.min(100, (value / MAX) * 100);
  const th = Math.min(100, (threshold / MAX) * 100);
  const bad = value > threshold;
  return (
    <div className="driftbar">
      <div className="driftbar-track">
        <div className={`driftbar-fill ${bad ? "bad" : value > threshold * 0.6 ? "mid" : "ok"}`} style={{ width: `${pct}%` }} />
        <div className="driftbar-th" style={{ left: `${th}%` }} title={`limit ${threshold}%`} />
      </div>
      <span className={`mono small ${bad ? "danger" : ""}`}>{value.toFixed(2)}%</span>
    </div>
  );
}

export default function DriftGauge({ config, onChange }) {
  const threshold = config?.drift_threshold_pct ?? 2;
  const [local, setLocal] = useState(config?.drift_pct ?? 0);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!dragging && config) setLocal(config.drift_pct);
  }, [config, dragging]);

  const bad = local > threshold;

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>NVDAc price drift</h2>
        <span className={`pill ${bad ? "pill-bad" : "pill-ok"}`}>{bad ? "Selling paused" : "OK to sell"}</span>
      </div>
      <p className="panel-note">
        On-chain NVDAc vs. the real Nvidia price. Above {threshold}%, the agent won't sell and pays from USDC instead.
      </p>
      <div className="gauge-number">
        <span className={bad ? "danger" : ""}>{Number(local).toFixed(1)}%</span>
        <span className="muted small"> / limit {threshold}%</span>
      </div>
      <DriftBar value={Number(local)} threshold={threshold} />
      <label className="label slider-label">
        Simulated drift (demo control)
        <input
          type="range"
          min="0"
          max={MAX}
          step="0.1"
          value={local}
          onChange={(e) => setLocal(Number(e.target.value))}
          onPointerDown={() => setDragging(true)}
          onPointerUp={() => {
            setDragging(false);
            onChange(Number(local));
          }}
          onKeyUp={() => onChange(Number(local))}
        />
      </label>
    </section>
  );
}
