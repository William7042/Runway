"""Shared helpers for SIMULATED sellers.

Data is returned ONLY after payment is confirmed via the approval queue
(proposal status executed/dry_run, or a demo token). Sellers never call
True Markets; they only check Person C's queue / a local paid-token store.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import HTTPException

QUEUE_URL = os.getenv("APPROVAL_QUEUE_URL", "http://localhost:8000")

# Demo tokens issued after we observe an approved/executed proposal for this seller.
_PAID: set[str] = set()


def mark_paid(token: str) -> None:
    _PAID.add(token)


def require_payment(proposal_id: Optional[str], payment_token: Optional[str]) -> None:
    """Gate: return 402 until payment confirmed."""
    if payment_token and payment_token in _PAID:
        return
    if not proposal_id:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "payment_required",
                "simulated": True,
                "message": "SIMULATED seller: pass proposal_id of an approved+executed payment.",
            },
        )
    try:
        r = httpx.get(f"{QUEUE_URL}/proposals/{proposal_id}", timeout=10.0)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise HTTPException(402, detail=f"could not verify payment: {e}") from e

    status = data.get("status")
    if status not in ("executed", "approved"):
        # Allow 'approved' in dry demos before money layer writes receipt.
        raise HTTPException(
            status_code=402,
            detail={
                "error": "payment_not_confirmed",
                "simulated": True,
                "proposal_status": status,
                "message": "SIMULATED seller: waiting for human-approved payment.",
            },
        )
    mark_paid(proposal_id)
