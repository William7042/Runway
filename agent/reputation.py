"""Reputation from transaction history (ledger), not self-reported.

Jobs completed, payouts received, refunds issued — read from data/ledger.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("runway.reputation")

LEDGER_DIR = Path("data/ledger")


@dataclass
class Reputation:
    seller_id: str
    jobs_completed: int = 0
    payouts_usd: float = 0.0
    refunds_usd: float = 0.0

    @property
    def score(self) -> float:
        """Simple hackathon score: completed jobs minus refund penalty."""
        if self.jobs_completed == 0 and self.payouts_usd == 0:
            return 0.0
        refund_ratio = self.refunds_usd / max(self.payouts_usd, 0.01)
        return max(0.0, self.jobs_completed * (1.0 - min(refund_ratio, 1.0)))


def _iter_ledger() -> list[dict[str, Any]]:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for fp in LEDGER_DIR.glob("*.json"):
        try:
            rows.append(json.loads(fp.read_text()))
        except Exception:
            logger.exception("bad ledger row %s", fp)
    return rows


def append_ledger(row: dict[str, Any]) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    rid = row.get("id") or row.get("tx_hash") or f"row_{len(list(LEDGER_DIR.glob('*.json')))}"
    (LEDGER_DIR / f"{rid}.json").write_text(json.dumps(row, indent=2))


def reputation_for(seller_id: str) -> Reputation:
    rep = Reputation(seller_id=seller_id)
    for row in _iter_ledger():
        if row.get("seller") != seller_id and row.get("seller_id") != seller_id:
            continue
        kind = row.get("kind") or row.get("type")
        amount = float(row.get("amount_usd") or 0)
        if kind in ("payout", "job_complete", "purchase"):
            rep.jobs_completed += 1
            rep.payouts_usd += amount
        elif kind == "refund":
            rep.refunds_usd += amount
    return rep


def seed_demo_ledger() -> None:
    """Seed a few history rows so registry ranking is non-empty at demo start."""
    if any(LEDGER_DIR.glob("*.json")):
        return
    samples = [
        {"id": "hist_1", "seller_id": "seller_filings", "kind": "job_complete", "amount_usd": 0.25},
        {"id": "hist_2", "seller_id": "seller_filings", "kind": "job_complete", "amount_usd": 0.25},
        {"id": "hist_3", "seller_id": "seller_archive", "kind": "job_complete", "amount_usd": 0.40},
        {"id": "hist_4", "seller_id": "seller_archive", "kind": "refund", "amount_usd": 0.40},
        {"id": "hist_5", "seller_id": "seller_specialist_sec", "kind": "job_complete", "amount_usd": 0.35},
        {"id": "hist_6", "seller_id": "seller_specialist_sec", "kind": "job_complete", "amount_usd": 0.35},
        {"id": "hist_7", "seller_id": "seller_specialist_sec", "kind": "job_complete", "amount_usd": 0.35},
    ]
    for s in samples:
        append_ledger(s)
