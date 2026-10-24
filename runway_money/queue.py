"""Person C's existing HTTP contract; no approval endpoint is exposed here."""
import httpx


class ApprovalError(RuntimeError):
    pass


class HTTPQueue:
    def __init__(self, url="http://localhost:8000", client=None, strict_live=False):
        self.client = client or httpx.Client(base_url=url, timeout=15)
        self.strict_live = strict_live

    def create(self, proposal):
        r = self.client.post("/proposals", json=proposal)
        r.raise_for_status()
        return r.json()

    def get(self, proposal_id):
        # Contract has a list endpoint, not GET /proposals/{id}.
        r = self.client.get("/proposals")
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else data["proposals"]
        return next((p for p in items if p["id"] == proposal_id), None)

    def approved(self, proposal_id):
        if self.strict_live:
            health = self.client.get('/health')
            if health.status_code != 404:
                health.raise_for_status()
                if health.json().get('stub_executor'):
                    raise ApprovalError('Disable Person C simulated executor before live execution')
        p = self.get(proposal_id)
        if not p or p["status"] != "approved":
            raise ApprovalError("Human approval required in the queue")
        return p

    def receipt(self, proposal_id, receipt):
        existing = self.get(proposal_id)
        if existing and existing.get('status') in {'executed', 'failed'}:
            saved = existing.get('receipt', {})
            if all(saved.get(k) == receipt.get(k) for k in ('quote', 'fill', 'tx_hash', 'status')):
                return existing
            raise ApprovalError('Terminal queue receipt differs from local receipt; reconcile manually')
        r = self.client.post(f"/proposals/{proposal_id}/receipt", json=receipt)
        r.raise_for_status()
        return r.json()
