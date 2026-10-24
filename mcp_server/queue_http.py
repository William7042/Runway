"""Thin HTTP client for Person C's approval queue (default http://localhost:8000)."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

BASE = os.getenv("APPROVAL_QUEUE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.getenv("RUNWAY_MCP_TIMEOUT", "30"))


class QueueError(RuntimeError):
    def __init__(self, status: int, detail: Any):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


def _req(method: str, path: str, *, json: Any = None, params: Optional[dict] = None) -> Any:
    r = httpx.request(
        method,
        f"{BASE}{path}",
        json=json,
        params=params,
        timeout=TIMEOUT,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if r.is_error:
        raise QueueError(r.status_code, data.get("detail", data) if isinstance(data, dict) else data)
    return data


def health() -> Any:
    return _req("GET", "/health")


def list_proposals(status: Optional[str] = None) -> Any:
    params = {"status": status} if status else None
    return _req("GET", "/proposals", params=params)


def get_proposal(proposal_id: str) -> Any:
    return _req("GET", f"/proposals/{proposal_id}")


def create_proposal(body: dict) -> Any:
    return _req("POST", "/proposals", json=body)


def decide(proposal_id: str, decision: str, reason: str = "") -> Any:
    return _req(
        "POST",
        f"/proposals/{proposal_id}/decision",
        json={"decision": decision, "reason": reason},
    )


def attach_receipt(proposal_id: str, body: dict) -> Any:
    return _req("POST", f"/proposals/{proposal_id}/receipt", json=body)


def list_receipts() -> Any:
    return _req("GET", "/receipts")


def get_config() -> Any:
    return _req("GET", "/config")


def set_config(patch: dict) -> Any:
    return _req("PUT", "/config", json=patch)


def get_balances() -> Any:
    return _req("GET", "/balances")


def set_balance(agent: str, body: dict) -> Any:
    return _req("PUT", f"/balances/{agent}", json=body)


def list_bounties() -> Any:
    return _req("GET", "/bounties")


def post_bounty(body: dict) -> Any:
    return _req("POST", "/bounties", json=body)


def claim_bounty(bounty_id: str, claimant: str) -> Any:
    return _req("POST", f"/bounties/{bounty_id}/claim", json={"claimant": claimant})


def submit_bounty(bounty_id: str, submission: str) -> Any:
    return _req("POST", f"/bounties/{bounty_id}/submit", json={"submission": submission})


def verify_bounty(bounty_id: str, decision: str, reason: str = "") -> Any:
    return _req(
        "POST",
        f"/bounties/{bounty_id}/verify",
        json={"decision": decision, "reason": reason},
    )


def demo_attack() -> Any:
    return _req("POST", "/demo/attack")


def demo_reset() -> Any:
    return _req("POST", "/demo/reset")
