"""Specialist agent registry.

Buyer searches by capability/fit and price; reputation comes from ledger history,
never from self-reported scores.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agent.models import SpecialistProfile
from agent.reputation import reputation_for, seed_demo_ledger

logger = logging.getLogger("runway.registry")

REGISTRY_PATH = Path("data/registry/specialists.json")

# SIMULATED sellers — labeled clearly. Not real marketplace counterparties.
DEFAULT_SPECIALISTS: list[SpecialistProfile] = [
    SpecialistProfile(
        id="seller_filings",
        name="SimFilings (SIMULATED)",
        capability="Return SEC / Form D style filing summaries for a company name",
        private_data="Indexed mock filing corpus the buyer does not hold",
        price_usd=0.25,
        accepted_assets=["USDC", "ETH"],
        endpoint="http://localhost:8101/v1/filing",
        wallet="wallet_sim_filings",
        simulated=True,
    ),
    SpecialistProfile(
        id="seller_archive",
        name="SimArchive (SIMULATED)",
        capability="Premium news/archive search for prior coverage and red flags",
        private_data="Paywalled mock archive index",
        price_usd=0.40,
        accepted_assets=["USDC"],
        endpoint="http://localhost:8102/v1/search",
        wallet="wallet_sim_archive",
        simulated=True,
    ),
    SpecialistProfile(
        id="seller_specialist_sec",
        name="SimSEC Analyst (SIMULATED)",
        capability="Summarize SEC filings and flag litigation / dilution risk",
        private_data="Private annotated filing notes",
        price_usd=0.35,
        accepted_assets=["USDC", "ETH"],
        endpoint="http://localhost:8103/v1/analyze",
        wallet="wallet_sim_sec_analyst",
        simulated=True,
    ),
]


def ensure_registry() -> list[SpecialistProfile]:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        payload = [s.model_dump() for s in DEFAULT_SPECIALISTS]
        REGISTRY_PATH.write_text(json.dumps(payload, indent=2))
        seed_demo_ledger()
    return list_specialists()


def list_specialists() -> list[SpecialistProfile]:
    if not REGISTRY_PATH.exists():
        return ensure_registry()
    raw = json.loads(REGISTRY_PATH.read_text())
    return [SpecialistProfile.model_validate(x) for x in raw]


def get(specialist_id: str) -> SpecialistProfile | None:
    for s in list_specialists():
        if s.id == specialist_id:
            return s
    return None


def search(capability_query: str, *, max_price: float | None = None) -> list[dict]:
    """Rank specialists by fit (substring) then price, annotate with ledger reputation."""
    q = capability_query.lower()
    scored: list[tuple[float, SpecialistProfile]] = []
    for s in list_specialists():
        hay = f"{s.capability} {s.private_data} {s.name}".lower()
        fit = 1.0 if q in hay or any(tok in hay for tok in q.split() if len(tok) > 3) else 0.2
        if max_price is not None and s.price_usd > max_price:
            continue
        # Prefer cheaper at equal fit.
        scored.append((fit * 10 - s.price_usd, s))

    scored.sort(key=lambda t: t[0], reverse=True)
    out = []
    for score, s in scored:
        rep = reputation_for(s.id)
        out.append(
            {
                "specialist": s.model_dump(),
                "fit_score": round(score, 3),
                "reputation": {
                    "jobs_completed": rep.jobs_completed,
                    "payouts_usd": rep.payouts_usd,
                    "refunds_usd": rep.refunds_usd,
                    "score": round(rep.score, 3),
                    "source": "ledger_history_not_self_reported",
                },
            }
        )
    return out


def known_seller_wallets() -> set[str]:
    return {s.wallet for s in list_specialists()} | {
        "wallet_bounty_worker",
        "escrow_board",  # bounty funding target before per-bounty wallet
    }
