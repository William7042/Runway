"""Deterministic policy layer — plain code, not an LLM.

Violations BLOCK the proposal (it never reaches a human). Reasons are logged.
The language model cannot talk its way past these checks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("runway.policy")


@dataclass
class PolicyConfig:
    """Per-agent spend / allowlist / velocity limits."""

    agent_id: str
    spend_cap_usd: float = 5.0  # demo wallets hold a few dollars
    asset_allowlist: set[str] = field(
        default_factory=lambda: {"USDC", "NVDAc", "WETH", "ETH"}
    )
    recipient_allowlist: set[str] = field(default_factory=set)
    # Empty allowlist = allow any known seller; set explicitly to lock down.
    price_impact_limit_pct: float = 1.0  # max 100 bps impact
    velocity_limit: int = 10  # max proposals per window
    velocity_window_sec: float = 300.0  # 5 minutes
    max_single_payment_usd: float = 2.0


@dataclass
class PolicyResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return not self.ok


# Rolling timestamps of proposals per agent (velocity).
_VELOCITY: dict[str, list[float]] = {}


def _trim_velocity(agent_id: str, window: float, now: float) -> list[float]:
    stamps = [t for t in _VELOCITY.get(agent_id, []) if now - t <= window]
    _VELOCITY[agent_id] = stamps
    return stamps


def check_proposal(
    *,
    config: PolicyConfig,
    buyer: str,
    seller: str,
    amount_usd: float,
    assets_in_path: list[str],
    expected_cost: float,
    purpose: str,
    source: str,
) -> PolicyResult:
    """Return ok=False with logged reasons if any rule is violated."""
    reasons: list[str] = []
    now = time.time()

    if amount_usd <= 0:
        reasons.append("amount_usd must be positive")

    if amount_usd > config.max_single_payment_usd:
        reasons.append(
            f"single payment ${amount_usd:.2f} exceeds max ${config.max_single_payment_usd:.2f}"
        )

    # Spend cap = sum of recent proposal amounts in this process (demo-simple).
    # Real build would sum ledger. Here we approximate via velocity stamps + amount gate.
    if amount_usd > config.spend_cap_usd:
        reasons.append(
            f"amount ${amount_usd:.2f} exceeds agent spend cap ${config.spend_cap_usd:.2f}"
        )

    for asset in assets_in_path:
        if asset not in config.asset_allowlist:
            reasons.append(f"asset '{asset}' not on allowlist {sorted(config.asset_allowlist)}")

    if config.recipient_allowlist and seller not in config.recipient_allowlist:
        reasons.append(
            f"recipient '{seller}' not on recipient allowlist "
            f"({len(config.recipient_allowlist)} allowed)"
        )

    # Price impact: expected_cost / amount as a rough pct proxy in the stub.
    if amount_usd > 0:
        impact_pct = (expected_cost / amount_usd) * 100.0
        if impact_pct > config.price_impact_limit_pct:
            reasons.append(
                f"price impact {impact_pct:.3f}% exceeds limit {config.price_impact_limit_pct}%"
            )

    stamps = _trim_velocity(config.agent_id, config.velocity_window_sec, now)
    if len(stamps) >= config.velocity_limit:
        reasons.append(
            f"velocity limit: {len(stamps)} proposals in last "
            f"{config.velocity_window_sec:.0f}s (max {config.velocity_limit})"
        )

    # Hard block: obvious drain / exfil language in purpose when source is untrusted content.
    drain_markers = (
        "send everything",
        "drain wallet",
        "transfer all",
        "send all funds",
        "empty the wallet",
    )
    purpose_l = purpose.lower()
    source_l = source.lower()
    if any(m in purpose_l for m in drain_markers):
        reasons.append(f"purpose matches drain pattern: blocked by policy")
    if "fetched:" in source_l or "page:" in source_l or "url:" in source_l:
        # Payments triggered by fetched content are allowed to reach verifier+human
        # ONLY if amount is tiny; large amounts from pages are blocked here.
        if amount_usd > 0.50:
            reasons.append(
                "payment triggered by fetched content exceeds $0.50 page-origin cap"
            )

    if reasons:
        for r in reasons:
            logger.warning("POLICY BLOCK agent=%s buyer=%s: %s", config.agent_id, buyer, r)
        return PolicyResult(ok=False, reasons=reasons)

    stamps.append(now)
    _VELOCITY[config.agent_id] = stamps
    logger.info(
        "POLICY OK agent=%s seller=%s amount=%.4f purpose=%r",
        config.agent_id,
        seller,
        amount_usd,
        purpose[:80],
    )
    return PolicyResult(ok=True)


def default_research_policy(known_sellers: Optional[set[str]] = None) -> PolicyConfig:
    return PolicyConfig(
        agent_id="research_desk",
        spend_cap_usd=5.0,
        recipient_allowlist=set(known_sellers or []),
        max_single_payment_usd=2.0,
        velocity_limit=8,
    )
