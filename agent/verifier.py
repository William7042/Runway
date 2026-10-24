"""Independent verifier — a SECOND Grok call.

Sees ONLY:
  - the proposed transaction (purpose, amount, seller, path summary)
  - the user's original request

Does NOT see the web page / seller message that triggered the payment.
Mismatch -> flag on the proposal (does NOT block). Policy blocks; verifier flags.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent import llm

logger = logging.getLogger("runway.verifier")


@dataclass
class VerifierResult:
    verdict: str  # "match" | "mismatch"
    reason: str

    @property
    def is_mismatch(self) -> bool:
        return self.verdict.lower() == "mismatch"

    def flag_text(self) -> str:
        return f"verifier:{self.verdict}:{self.reason}"


SYSTEM = """You are a payment verifier for an AI agent treasury.
You receive (1) the user's original request and (2) a proposed payment.
Decide whether the payment clearly serves that request.
Reply ONLY with JSON: {"verdict":"match"|"mismatch","reason":"..."}.
Be strict: transfers to unrelated addresses, wallet-emptying instructions, or
payments that do not relate to the user's question are mismatches.
You never approve or block funds — you only label match/mismatch."""


def verify(
    *,
    user_request: str,
    purpose: str,
    amount_usd: float,
    seller: str,
    path_summary: str,
    buyer: str,
) -> VerifierResult:
    """Second-model check. Intentionally does NOT receive fetched page content."""
    user_msg = (
        f"USER_ORIGINAL_REQUEST:\n{user_request}\n\n"
        f"PROPOSED_TRANSACTION:\n"
        f"  buyer: {buyer}\n"
        f"  seller: {seller}\n"
        f"  amount_usd: {amount_usd}\n"
        f"  purpose: {purpose}\n"
        f"  path: {path_summary}\n\n"
        "Return match or mismatch with a short reason."
    )
    raw = llm.chat(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        json_mode=True,
        temperature=0.0,
    )
    try:
        data: dict[str, Any] = llm.extract_json(raw)
        verdict = str(data.get("verdict", "mismatch")).lower()
        reason = str(data.get("reason", "no reason"))
        if verdict not in ("match", "mismatch"):
            verdict = "mismatch"
            reason = f"invalid verdict from model; treated as mismatch ({reason})"
    except Exception as e:
        logger.exception("verifier parse failed")
        verdict, reason = "mismatch", f"verifier parse error: {e}"

    result = VerifierResult(verdict=verdict, reason=reason)
    logger.info("VERIFIER %s — %s", result.verdict, result.reason)
    return result
