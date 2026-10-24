export const usd = (n, digits) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  const d = digits ?? (Math.abs(v) < 1 && v !== 0 ? 4 : 2);
  const sign = v < 0 ? "-" : "";
  return sign + "$" + Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: Math.min(d, 2), maximumFractionDigits: d });
};

export const amt = (n) => {
  const v = Number(n);
  if (Number.isNaN(v)) return String(n);
  return v.toLocaleString(undefined, { maximumFractionDigits: 6 });
};

export const ago = (t) => {
  if (!t) return "";
  const s = Math.max(0, Math.round(Date.now() / 1000 - t));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
};

export const flagText = (f) => (typeof f === "string" ? f : f?.message || f?.text || JSON.stringify(f));

// "POLICY_BLOCK: ..." -> {kind: "block", label: "Policy block", text: "..."}
export const parseFlag = (f) => {
  const t = flagText(f);
  const m = t.match(/^([A-Z_]+):\s*(.*)$/s);
  const tag = m ? m[1] : "";
  const text = m ? m[2] : t;
  const map = {
    POLICY_BLOCK: ["block", "Policy block"],
    INJECTION: ["block", "Prompt injection"],
    VERIFIER: ["warn", "Verifier"],
    VERIFIER_MISMATCH: ["warn", "Verifier mismatch"],
    POLICY: ["warn", "Policy"],
  };
  const [kind, label] = map[tag] || ["warn", tag ? tag.replace(/_/g, " ").toLowerCase() : "Warning"];
  return { kind, label, text };
};

export const costTotal = (c) => {
  if (c === null || c === undefined) return null;
  if (typeof c === "number") return c;
  return c.total_usd ?? (Number(c.price_impact_usd || 0) + Number(c.fees_usd || 0));
};

export const driftPct = (d) => {
  if (d === null || d === undefined) return null;
  if (typeof d === "number") return d;
  if (d.gap_pct !== undefined) return Number(d.gap_pct);
  if (d.onchain_price && d.reference_price)
    return (Math.abs(d.onchain_price - d.reference_price) / d.reference_price) * 100;
  return null;
};

export const sourceInfo = (s) => {
  if (!s) return { kind: "unknown", text: "" };
  if (typeof s === "string") return { kind: "source", text: s };
  return { kind: s.kind || "source", text: s.text || "", url: s.url, injected: s.injected_excerpt };
};

export const SOURCE_LABEL = {
  user_message: "User message",
  agent_plan: "Agent plan",
  fetched_page: "Fetched web page",
  seller_response: "Seller response",
  bounty_board: "Bounty board",
};
