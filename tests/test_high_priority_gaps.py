"""Smoke tests for high-priority demo gaps (purchase loop, registry plan, stub DRY_RUN)."""

from __future__ import annotations

import os

from agent.registry import ensure_registry, search
from agent.research_agent import _catalog_for_planner, _normalize_purchases
from agent.sellers_client import company_from_question


def test_company_from_question():
    assert "Acme" in company_from_question("Is Acme Robotics legit? Check filings.")


def test_registry_search_ranks():
    ensure_registry()
    hits = search("SEC filing Form D", max_price=1.0)
    assert hits
    assert hits[0]["specialist"]["id"] == "seller_filings"
    assert hits[0]["reputation"]["source"] == "ledger_history_not_self_reported"


def test_normalize_purchases_maps_unknown_to_registry():
    catalog = _catalog_for_planner()
    plan = {
        "plan_summary": "test",
        "purchases": [
            {
                "kind": "filing",
                "seller_id": "totally_invented",
                "amount_usd": 0,
                "purpose": "get filing",
            }
        ],
    }
    fixed = _normalize_purchases(plan, catalog)
    assert fixed["purchases"][0]["seller_id"] == "seller_filings"
    assert fixed["purchases"][0]["amount_usd"] == 0.25


def test_money_stub_dry_run_does_not_claim_executed(monkeypatch):
    from runway_money.stub import StubRouter

    class FakeQueue:
        def approved(self, proposal_id):
            return {
                "id": proposal_id,
                "amount_usd": 1.0,
                "path": [{"type": "transfer", "asset": "USDC", "amount": 1.0}],
            }

        def receipt(self, *a, **k):
            raise AssertionError("DRY_RUN must not post a success receipt")

    monkeypatch.setenv("DRY_RUN", "1")
    r = StubRouter(queue=FakeQueue())
    receipt = r.execute("prop_test")
    assert receipt["status"] == "dry_run"
    assert receipt["tx_hash"] is None
    assert receipt.get("stub") is True
    assert "dry_run" in receipt["quote"]


def test_money_stub_live_posts_simulated_receipt(monkeypatch):
    from runway_money.stub import StubRouter

    posted = {}

    class FakeQueue:
        def approved(self, proposal_id):
            return {
                "id": proposal_id,
                "amount_usd": 1.0,
                "path": [{"type": "transfer", "asset": "USDC", "amount": 1.0}],
            }

        def receipt(self, proposal_id, receipt):
            posted["id"] = proposal_id
            posted["receipt"] = receipt

    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("RUNWAY_PAYMENT_FEE_USD", "1")
    r = StubRouter(queue=FakeQueue())
    receipt = r.execute("prop_test")
    assert receipt["status"] == "executed"
    assert receipt["fill"]["fee_usd"] == 1.0
    assert receipt["fill"]["seller_net_usd"] == 1.0
    assert receipt["tx_hash"].startswith("STUB-")
    assert posted["receipt"]["stub"] is True
