"""Claude Haiku or Grok client for the research agent and verifier.

Claude keys: ANTHROPIC_API_KEY or CLAUDE_API_KEY; defaults to cheap Haiku 4.5.
Grok keys: XAI_API_KEY, GROK_API_KEY, or X_API_KEY. LLM_PROVIDER selects an API.
Only callers that explicitly allow offline operation receive a stub when keys
are absent. Live demo callers always require a real provider response.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

try:
    from dotenv import load_dotenv, dotenv_values

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("runway.llm")

DEFAULT_MODEL = os.getenv("GROK_MODEL", "grok-4.7")
BASE_URL = "https://api.x.ai/v1"


def configuration():
    """Prefer a saved Claude key; explicit LLM_PROVIDER can select either API."""
    from pathlib import Path
    saved = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    def value(name):
        return saved.get(name) or os.getenv(name)
    claude = value("ANTHROPIC_API_KEY") or value("CLAUDE_API_KEY")
    provider = value("LLM_PROVIDER") or ("anthropic" if claude else "xai")
    if provider == "anthropic":
        return provider, claude, value("CLAUDE_MODEL") or "claude-haiku-4-5-20251001"
    if provider != "xai":
        raise ValueError("LLM_PROVIDER must be anthropic or xai")
    key = next((value(n) for n in ("XAI_API_KEY", "GROK_API_KEY", "X_API_KEY") if value(n)), None)
    return provider, key, value("GROK_MODEL") or "grok-4.7"


class ModelAPIError(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Model API rejected request (HTTP {status_code})")


class ClaudeMessages:
    def __init__(self, key):
        self.key = key

    def complete(self, messages, *, model, temperature, json_mode):
        import httpx
        system = "\n".join(m['content'] for m in messages if m['role'] == 'system')
        if json_mode:
            system += "\nReturn ONLY one valid JSON object. No markdown or explanatory text."
        payload = {'model': model, 'max_tokens': 1200, 'temperature': temperature,
                   'system': system,
                   'messages': [m for m in messages if m['role'] != 'system']}
        response = httpx.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key': self.key, 'anthropic-version': '2023-06-01'},
            json=payload, timeout=60)
        if not response.is_success:
            raise ModelAPIError(response.status_code)
        data = response.json()
        if data.get('stop_reason') == 'max_tokens':
            raise RuntimeError('Model answer exceeded output budget')
        return "\n".join(block['text'] for block in data.get('content', []) if block.get('type') == 'text')


def _client():
    provider, key, _ = configuration()
    if not key:
        return None
    if provider == "anthropic":
        return ClaudeMessages(key)
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("pip install openai") from e
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=60, max_retries=0)


def chat(
    messages: list[dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    json_mode: bool = False,
    require_live: bool = False,
) -> str:
    """Single chat completion. Returns assistant text (or offline stub)."""
    client = _client()
    if client is None:
        if require_live:
            raise RuntimeError("Save a Claude key as ANTHROPIC_API_KEY or an xAI key as XAI_API_KEY in .env")
        logger.warning("No model API key — using offline stub response")
        return _offline_response(messages, json_mode=json_mode)

    selected_model = model or configuration()[2]
    if isinstance(client, ClaudeMessages):
        return client.complete(messages, model=selected_model, temperature=temperature, json_mode=json_mode)

    kwargs: dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1200,
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
