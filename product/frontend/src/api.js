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
  specialists: () => req("GET", "/specialists"),
  registerSpecialist: (body) => req("POST", "/specialists", body),
  updateSpecialist: (id, body) => req("PATCH", `/specialists/${id}`, body),
  saveSellerCredentials: (id, owner_token) => req("POST", `/specialists/${id}/demo-credentials`, { owner_token }),
  sellerJobs: (id, owner_token) => req("POST", `/specialists/${id}/jobs`, { owner_token }),
  submitResult: (jobId, owner_token, result) => req("POST", `/specialist-jobs/${jobId}/result`, { owner_token, result }),
  attack: () => req("POST", "/demo/attack"),
  reset: () => req("POST", "/demo/reset"),
};

// Artifact credentials stay in request bodies, never in download URLs.
api.jobDelivery = (id, buyer_token) => req("POST", `/specialist-jobs/${id}/delivery`, { buyer_token });
api.rateSpecialistJob = (id, buyer_token, stars, review) => req("POST", `/specialist-jobs/${id}/rating`, { buyer_token, stars, review });
api.specialistReviews = (id) => req("GET", `/specialists/${id}/reviews`);
api.uploadArtifact = async (id, owner_token, file, description = "") => {
  if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Files must contain 1 byte to 10 MiB");
  const content_base64 = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
  return req("POST", `/specialist-jobs/${id}/artifacts`, { owner_token, filename: file.name, mime_type: file.type || "application/octet-stream", description, content_base64 });
};
api.downloadArtifact = async (id, artifactId, buyer_token) => {
  const response = await fetch(API + `/specialist-jobs/${id}/artifacts/${artifactId}/download`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ buyer_token }),
  });
  if (!response.ok) throw new Error("Download unavailable: check buyer access and delivery status");
  return response.blob();
};

api.hireRecommendations = (question) => req('POST', '/hire/recommendations', { question });
api.prepareHirePayment = (body) => req('POST', '/hire/prepare-payment', body);
