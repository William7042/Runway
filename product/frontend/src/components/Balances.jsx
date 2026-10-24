import React from "react";
import { usd, amt } from "../format.js";

const MODE = { endowment: "Endowment", pay_in_kind: "Pay in kind", auto_top_up: "Auto top-up" };

export default function Balances({ balances }) {
  const agents = Object.entries(balances || {});
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Agent wallets</h2>
      </div>
      {agents.length === 0 && <div className="muted">No wallets yet.</div>}
      {agents.map(([id, w]) => {
        const total = (w.assets || []).reduce((a, x) => a + Number(x.usd_value || 0), 0);
        return (
          <div key={id} className="wallet">
            <div className="wallet-head">
              <div>
                <div className="strong">{w.label || id}</div>
                <div className="muted small">
                  {MODE[w.treasury_mode] || w.treasury_mode}
                  {w.simulated && <span className="pill pill-soft">simulated</span>}
                </div>
              </div>
              <div className="big">{usd(total, 2)}</div>
            </div>
            <div className="alloc">
              {(w.assets || []).map((x) => (
                <div
                  key={x.asset}
                  className={`alloc-seg seg-${x.asset.toLowerCase()}`}
                  style={{ flex: Math.max(0.02, Number(x.usd_value || 0)) }}
                  title={`${x.asset} ${usd(x.usd_value)}`}
                />
              ))}
            </div>
            <table className="holdings">
              <tbody>
                {(w.assets || []).map((x) => (
                  <tr key={x.asset}>
                    <td>{x.asset}</td>
                    <td className="mono right">{amt(x.amount)}</td>
                    <td className="mono right">{usd(x.usd_value, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {w.cost_basis_usd !== undefined && (
              <div className="small muted">
                Principal {usd(w.cost_basis_usd, 2)} stays invested · spendable gains{" "}
                <span className="strong">{usd(Math.max(0, total - w.cost_basis_usd), 2)}</span>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
