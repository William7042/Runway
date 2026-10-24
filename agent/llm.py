"""Grok (xAI) client for the research agent and verifier.

Uses the OpenAI-compatible API at https://api.x.ai/v1.
Env: XAI_API_KEY (required for live calls). GROK_MODEL overrides model name.
When XAI_API_KEY is missing, falls back to a deterministic offline planner so
the demo still runs without network.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("runway.llm")

DEFAULT_MODEL = os.getenv("GROK_MODEL", "grok-4.7")
BASE_URL = "https://api.x.ai/v1"


def _client():
    key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("pip install openai") from e
    return OpenAI(api_key=key, base_url=BASE_URL)


def chat(
    messages: list[dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """Single chat completion. Returns assistant text (or offline stub)."""
    client = _client()
    if client is None:
        logger.warning("No XAI_API_KEY — using offline stub response")
        return _offline_response(messages, json_mode=json_mode)

    kwargs: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _offline_response(messages: list[dict[str, str]], *, json_mode: bool) -> str:
    """Deterministic fallback so demos work without an API key."""
    # Inspect the user turn only — system prompts mention words like "drain"
    # and must not false-trigger the verifier stub.
    user_blob = " ".join(
        m.get("content", "") for m in messages if m.get("role") == "user"
    ).lower()
    blob = " ".join(m.get("content", "") for m in messages).lower()

    # Verifier path
    if "proposed_transaction" in user_blob or "match or mismatch" in user_blob:
        suspicious = (
            "send everything",
            "drain",
            "0xevil",
            "attacker",
            "exfil",
            "safekeeping",
            "partner wallet",
            "page instructions",
            "forward treasury",
        )
        if any(x in user_blob for x in suspicious):
            return json.dumps(
                {
                    "verdict": "mismatch",
                    "reason": "Proposed transfer does not match the user's research question; looks like an exfiltration attempt.",
                }
            )
        return json.dumps(
            {
                "verdict": "match",
                "reason": "Payment purpose aligns with the user's research request.",
            }
        )

    # Research planner path
    if "plan" in blob or "paid inputs" in blob or "startup" in blob:
        return json.dumps(
            {
                "plan_summary": "Need a filing, a premium archive hit, and a human fact-check.",
                "purchases": [
                    {
                        "kind": "filing",
                        "seller_id": "seller_filings",
                        "amount_usd": 0.25,
                        "purpose": "Pull the latest Form D / SEC filing for the named startup to check registration status.",
                    },
                    {
                        "kind": "archive",
                        "seller_id": "seller_archive",
                        "amount_usd": 0.40,
                        "purpose": "Query the premium news archive for prior coverage and red flags on this startup.",
                    },
                    {
                        "kind": "bounty",
                        "seller_id": "bounty_board",
                        "amount_usd": 1.00,
                        "purpose": "Post a human fact-check bounty: verify the founders' prior exits and any litigation.",
                    },
                ],
            }
        )

    if json_mode:
        return json.dumps({"verdict": "match", "reason": "offline default"})
    return "offline stub"


def extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from a model reply, tolerating ``` fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)
