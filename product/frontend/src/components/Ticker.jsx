import React, { useEffect, useState } from "react";
import { usd } from "../format.js";
import "../styles/ticker.css";

// Turn real queue activity into short ticker lines, newest first.
function toItems(proposals, earnedSellers) {
  const when = (p) => p.receipt?.at || p.decision?.at || p.created_at || 0;
  return [...proposals]
    .filter((p) => p.status !== "pending")
    .sort((a, b) => when(b) - when(a))
    .slice(0, 10)
    .map((p) => {
      const amount = usd(p.amount_usd, 2);
      const seller = String(p.seller || "").split(" ")[0];
      if (p.blocked) return { id: p.id, kind: "bad", text: `Blocked ${amount} · ${p.flags?.some((f) => String(f).startsWith("INJECTION")) ? "prompt injection" : "policy"}` };
      if (p.status === "rejected") return { id: p.id, kind: "muted", text: `Rejected ${amount} → ${seller}` };
      if (p.status === "failed") return { id: p.id, kind: "bad", text: `Failed ${amount} → ${seller}` };
      if (p.status === "approved") return { id: p.id, kind: "muted", text: `Approved ${amount} → ${seller} · sending` };
      if (earnedSellers.includes(p.seller)) return { id: p.id, kind: "good", text: `Earned ${amount} from ${p.buyer}` };
      if (p.bounty_role === "payout") return { id: p.id, kind: "good", text: `Bounty paid ${amount} → ${seller}` };
      return { id: p.id, kind: "good", text: `Paid ${amount} → ${seller}` };
    });
}

/** One thin strip under the top bar that scrolls real payment events. The only moving part. */
export default function Ticker({ api, proposals, refreshKey }) {
  const [earnedSellers, setEarnedSellers] = useState([]);
  useEffect(() => {
    let alive = true;
    api
      .specialists()
      .then((list) => alive && setEarnedSellers([...new Set((Array.isArray(list) ? list : []).map((s) => s.payout_user).filter(Boolean))]))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [api, refreshKey]);

  const items = toItems(proposals || [], earnedSellers);
  const pending = (proposals || []).filter((p) => p.status === "pending").length;
  const lead = pending ? [{ id: "pending", kind: "warn", text: `${pending} waiting for your approval` }] : [];
  const all = [...lead, ...items];

  if (all.length === 0) {
    return (
      <div className="ticker" aria-label="Activity">
        <div className="ticker-static">
          <span className="ticker-item muted">
            <i /> No activity yet · every order waits for your approval
          </span>
        </div>
      </div>
    );
  }

  // Duplicate the list so the loop is seamless; speed scales with length so it reads at a steady pace.
  const seconds = Math.max(24, all.length * 6);
  return (
    <div className="ticker" aria-label="Recent activity">
      <div className="ticker-track" style={{ animationDuration: `${seconds}s` }}>
        {[0, 1].map((copy) => (
          <div key={copy} className="ticker-run" aria-hidden={copy === 1 ? "true" : undefined}>
            {all.map((it) => (
              <span key={`${copy}-${it.id}`} className={`ticker-item ${it.kind}`}>
                <i />
                {it.text}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
