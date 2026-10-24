import React, { useState } from "react";
import { usd, amt } from "../format.js";
import "../styles/desk.css";

const MODE = { endowment: "Endowment", pay_in_kind: "Pay in kind", auto_top_up: "Auto top-up" };

export default function Balances({ balances, layout }) {
  const [showDemo, setShowDemo] = useState(false);
  const entries = Object.entries(balances || {});
  const real = entries.filter(([, wallet]) => wallet.simulated === false);
  const demo = entries.filter(([, wallet]) => wallet.simulated !== false);
  const agents = real.length ? [...real, ...(showDemo ? demo : [])] : demo;
  return (
    <section className={`panel ${layout === "row" ? "wallets-row" : ""}`}>
      <div className="panel-head">
        <h2>{real.length ? "Real agent wallets" : "Demo wallets"}</h2>
        {real.length > 0 && demo.length > 0 && <button className="btn btn-ghost small" onClick={() => setShowDemo(!showDemo)}>{showDemo ? "Hide" : "Show"} simulated wallets ({demo.length})</button>}
      </div>
      <div className="wallets">
      {agents.length === 0 && <div className="muted">No wallets yet.</div>}
      {agents.map(([id, w]) => {
        const assets = w.assets || [];
        const priced = assets.filter(x => x.usd_value !== null && x.usd_value !== undefined && Number.isFinite(Number(x.usd_value)));
        const total = priced.reduce((a, x) => a + Number(x.usd_value), 0);
        const partial = priced.length < assets.length;
        return (
          <div key={id} className="wallet">
            <div className="wallet-head">
              <div>
                <div className="strong">{w.label || id}</div>
                <div className="muted small">
                  {MODE[w.treasury_mode] || w.treasury_mode}
                  {w.simulated === false && <span className="pill pill-ok">live wallet</span>}
                  {w.simulated !== false && <span className="pill pill-soft">simulated</span>}
                </div>
              </div>
              <div className="right"><div className="big">{priced.length ? usd(total, 2) : "Not valued"}</div>{partial && <div className="small muted">Priced subtotal · other assets below</div>}</div>
            </div>
            <div className="alloc">
              {(w.assets || []).map((x) => (
                <div
                  key={x.asset_id || `${x.chain || ""}:${x.asset}`}
                  className={`alloc-seg seg-${x.asset.toLowerCase()}`}
                  style={{ flex: Math.max(0.02, Number(x.usd_value || 0)) }}
                  title={`${x.asset} ${usd(x.usd_value)}`}
                />
              ))}
            </div>
            <table className="holdings">
              <tbody>
                {(w.assets || []).map((x) => (
                  <tr key={x.asset_id || `${x.chain || ""}:${x.asset}`}>
                    <td>{x.asset}</td>
                    <td className="mono right">{amt(x.amount)}</td>
                    <td className="mono right">{usd(x.usd_value, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {w.valuation_note && <p className="small muted">{w.valuation_note}</p>}
            {w.snapshot_at && <p className="small muted">Updated {new Date(w.snapshot_at).toLocaleString()}</p>}
            {w.cost_basis_usd !== undefined && (
              <div className="small muted">
                Principal {usd(w.cost_basis_usd, 2)} stays invested · spendable gains{" "}
                <span className="strong">{usd(Math.max(0, total - w.cost_basis_usd), 2)}</span>
              </div>
            )}
          </div>
        );
      })}
      </div>
    </section>
  );
}
