// Approval queue base URL. Override with VITE_API_URL in frontend/.env.local
// (e.g. VITE_API_URL=http://192.168.1.20:8000 to point at a teammate's laptop).
export const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function req(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : `${res.status} ${res.statusText}`);
  return data;
}

export const api = {
  health: () => req("GET", "/health"),
  proposals: (status) => req("GET", "/proposals" + (status ? `?status=${status}` : "")),
  decide: (id, decision, reason = "") => req("POST", `/proposals/${id}/decision`, { decision, reason }),
  receipts: () => req("GET", "/receipts"),
  config: () => req("GET", "/config"),
  setConfig: (patch) => req("PUT", "/config", patch),
  balances: () => req("GET", "/balances"),
  bounties: () => req("GET", "/bounties"),
  postBounty: (b) => req("POST", "/bounties", b),
  claim: (id, claimant) => req("POST", `/bounties/${id}/claim`, { claimant }),
  submit: (id, submission) => req("POST", `/bounties/${id}/submit`, { submission }),
  verify: (id, decision, reason = "") => req("POST", `/bounties/${id}/verify`, { decision, reason }),
  attack: () => req("POST", "/demo/attack"),
  reset: () => req("POST", "/demo/reset"),
};
