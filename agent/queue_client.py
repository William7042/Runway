"""HTTP client for Person C's approval queue (default http://localhost:8000)."""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx

from agent.models import Proposal, ProposalStatus, Receipt

DEFAULT_QUEUE_URL = os.getenv("APPROVAL_QUEUE_URL", "http://localhost:8000")


class QueueClient:
    def __init__(self, base_url: str = DEFAULT_QUEUE_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create(self, proposal: Proposal) -> Proposal:
        r = httpx.post(
            f"{self.base_url}/proposals",
            json=proposal.model_dump(mode="json"),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return Proposal.model_validate(r.json())

    def list(self, status: Optional[str] = None) -> list[Proposal]:
        params = {"status": status} if status else {}
        r = httpx.get(f"{self.base_url}/proposals", params=params, timeout=self.timeout)
        r.raise_for_status()
        return [Proposal.model_validate(x) for x in r.json()]

    def get(self, proposal_id: str) -> Proposal:
        r = httpx.get(f"{self.base_url}/proposals/{proposal_id}", timeout=self.timeout)
        r.raise_for_status()
        return Proposal.model_validate(r.json())

    def decide(self, proposal_id: str, decision: str, reason: str = "") -> Proposal:
        r = httpx.post(
            f"{self.base_url}/proposals/{proposal_id}/decision",
            json={"decision": decision, "reason": reason},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return Proposal.model_validate(r.json())

    def receipt(self, proposal_id: str, receipt: Receipt) -> Proposal:
        r = httpx.post(
            f"{self.base_url}/proposals/{proposal_id}/receipt",
            json=receipt.model_dump(mode="json"),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return Proposal.model_validate(r.json())

    def wait_until_decided(
        self,
        proposal_id: str,
        *,
        poll_sec: float = 2.0,
        timeout_sec: float = 600.0,
    ) -> Proposal:
        """Agent waits for human approval; never executes itself."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            p = self.get(proposal_id)
            if p.status in (
                ProposalStatus.APPROVED,
                ProposalStatus.REJECTED,
                ProposalStatus.EXECUTED,
                ProposalStatus.FAILED,
            ):
                return p
            time.sleep(poll_sec)
        raise TimeoutError(f"proposal {proposal_id} still pending after {timeout_sec}s")
