import React from "react";
import Balances from "./Balances.jsx";
import Ledger from "./Ledger.jsx";

/** Everything that isn't a decision: wallets, totals and the audit log. */
export default function Activity({ proposals, balances }) {
  return (
    <div className="stack">
      <Balances balances={balances} layout="row" />
      <Ledger proposals={proposals} balances={balances} />
    </div>
  );
}
