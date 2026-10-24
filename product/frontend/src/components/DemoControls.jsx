import React, { useState } from "react";
import DriftGauge from "./DriftGauge.jsx";
import "../styles/desk.css";

/** Floating presenter panel: drift slider, attack trigger, reset. Kept off the main screen. */
export default function DemoControls({ config, health, api, refresh, onReset }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`demo ${open ? "open" : ""}`}>
      {open && (
        <div className="demo-panel">
          <div className="demo-head">
            <span className="strong">Demo controls</span>
            <button className="btn btn-ghost small" onClick={() => setOpen(false)} aria-label="Close demo controls">
              Close
            </button>
          </div>
          <DriftGauge
            config={config}
            onChange={async (v) => {
              await api.setConfig({ drift_pct: v });
              refresh();
            }}
          />
          <div className="demo-actions">
            <button
              className="btn small"
              onClick={async () => {
                await api.attack();
                refresh();
              }}
            >
              Simulate injection attack
            </button>
            <button
              className="btn btn-ghost small"
              onClick={async () => {
                if (confirm("Reset all demo data to the seeded state?")) {
                  await api.reset();
                  onReset?.();
                  refresh();
                }
              }}
            >
              Reset demo data
            </button>
          </div>
          {health?.stub_executor && <div className="demo-note">Stub router is on: receipts are simulated.</div>}
        </div>
      )}
      <button className="demo-fab" onClick={() => setOpen(!open)}>
        Demo
      </button>
    </div>
  );
}
