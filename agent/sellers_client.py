"""HTTP client for SIMULATED sellers.

The research agent fetches paid data ONLY after the approval queue shows
approved/executed. Sellers never talk to True Markets.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from agent.models import ProposalStatus
from agent.queue_client import QueueClient
from agent.registry import get

logger = logging.getLogger("runway.sellers_client")

# Kind → query param / body field the SIMULATED seller endpoints expect.
_KIND_QUERY_KEY = {
    "filing": "company",
    "archive": "q",
    "specialist": "company",
}


def company_from_question(question: str) -> str:
    """Best-effort name extraction for seller query params."""
    m = re.search(
        r"(?:is|about|for|on)\s+([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*){0,3})",
        question,
    )
    if m:
        return m.group(1).strip(" ?.!")
    # Fallback: first Title-Case run of 1–4 words.
    m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", question)
    return m.group(1) if m else "Unknown Co"


def wait_until_paid(
    proposal_id: str,
    *,
    queue: Optional[QueueClient] = None,
    poll_sec: float = 1.5,
    timeout_sec: float = 180.0,
):
    """Poll until the human decision settles far enough for sellers to unlock data.

    Accepts approved (dry demos before receipt) or executed/failed/rejected.
    """
    import time

    q = queue or QueueClient()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        p = q.get(proposal_id)
        if p.status in (
            ProposalStatus.APPROVED,
            ProposalStatus.EXECUTED,
            ProposalStatus.REJECTED,
            ProposalStatus.FAILED,
        ):
            return p
        time.sleep(poll_sec)
    raise TimeoutError(f"proposal {proposal_id} still pending after {timeout_sec}s")


def fetch_paid_data(
    seller_id: str,
    proposal_id: str,
    *,
    query: str,
    kind: str = "",
    timeout: float = 15.0,
) -> dict[str, Any]:
    """GET/POST the SIMULATED seller endpoint with proposal_id as payment proof.

    Returns a dict always including simulated=True on success.
    Raises httpx.HTTPStatusError on 4xx/5xx (including 402 payment_required).
    """
    spec = get(seller_id)
    if spec is None:
        raise KeyError(f"unknown seller_id {seller_id}")
    if not spec.simulated:
        raise RuntimeError(f"refusing non-simulated seller {seller_id}")

    endpoint = spec.endpoint.rstrip("/")
    kind_key = _KIND_QUERY_KEY.get(kind) or (
        "q" if "/search" in endpoint else "company"
    )

    # Specialist uses POST JSON; filings/archive use GET query params.
    if endpoint.endswith("/analyze") or kind == "specialist":
        payload = {"company": query, "proposal_id": proposal_id}
        r = httpx.post(endpoint, json=payload, timeout=timeout)
    else:
        params = {kind_key: query, "proposal_id": proposal_id}
        r = httpx.get(f"{endpoint}?{urlencode(params)}", timeout=timeout)

    if r.status_code == 402:
        detail = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        raise PermissionError(f"SIMULATED seller payment not confirmed: {detail}")
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        data = {"data": data}
    data.setdefault("simulated", True)
    data["_seller_id"] = seller_id
    data["_endpoint"] = endpoint
    logger.info("Fetched SIMULATED data from %s for proposal %s", seller_id, proposal_id)
    return data
