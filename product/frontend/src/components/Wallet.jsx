import React, { useEffect, useState } from "react";
import Balances from "./Balances.jsx";
import Ledger from "./Ledger.jsx";
import EarningsChart from "./EarningsChart.jsx";
import { loadTokens } from "./Sell.jsx";
import { usd } from "../format.js";

/** Wallet = money: what you have, what came in and went out, and the full history. (Replaces Activity.) */
export default function Wallet({ api, proposals, balances, refreshKey }) {
  const [specialists, setSpecialists] = useState([]);
  useEffect(() => {
    let alive = true;
    api.specialists().then((x) => alive && setSpecialists(Array.isArray(x) ? x : [])).catch(() => {});
    return () => {
      alive = false;
    };
  }, [api, refreshKey]);

  const tokens = loadTokens();
  // Services listed through Sell (they have a payout user). Prefer the ones this browser holds tokens for;
  // otherwise count every listed service, so earnings still show on another laptop.
  const listed = specialists.filter((s) => s.payout_user);
  const withToken = listed.filter((s) => tokens[s.id]);
  const mine = withToken.length ? withToken : listed;
  const earnedSellers = [...new Set(mine.map((s) => s.payout_user).filter(Boolean))];
  const earned = mine.reduce((a, s) => a + Number(s.earned_usd || 0), 0);

  const executed = proposals.filter((p) => p.status === "executed" && !earnedSellers.includes(p.seller));
  const spent = executed.reduce((a, p) => a + Number(p.amount_usd || 0), 0);
  const blocked = proposals.filter((p) => p.blocked).length;
  const principal = balances?.["research-agent"]?.cost_basis_usd;
  const net = earned - spent;

  // Every completed payment becomes a point on the chart: money in (to your listings) or money out.
  const events = proposals
    .filter((p) => p.status === "executed" && p.receipt?.at)
    .map((p) => ({
      t: Number(p.receipt.at) * 1000,
      amount: Number(p.amount_usd || 0),
      kind: earnedSellers.includes(p.seller) ? "earned" : "spent",
    }));

  return (
    <div className="stack">
      <Balances balances={balances} layout="row" />
      <div className="stats">
        <div className="stat">
          <div className="label">Earned</div>
          <div className="big good">{usd(earned, 2)}</div>
        </div>
        <div className="stat">
          <div className="label">Spent</div>
          <div className="big">{usd(spent, 2)}</div>
        </div>
        <div className="stat">
          <div className="label">Net</div>
          <div className={`big ${net >= 0 ? "good" : "danger"}`}>{usd(net, 2)}</div>
        </div>
        {principal !== undefined && (
          <div className="stat">
            <div className="label">Principal still invested</div>
            <div className="big">{usd(principal, 2)}</div>
          </div>
        )}
        <div className="stat">
          <div className="label">Blocked by policy</div>
          <div className="big danger">{blocked}</div>
        </div>
      </div>
      <EarningsChart events={events} />
      <Ledger proposals={proposals} balances={balances} showStats={false} earnedSellers={earnedSellers} />
    </div>
  );
}
