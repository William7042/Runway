"""Runway approval queue (Person C, product layer).

Run:  uvicorn app:app --reload --port 8000      (from product/queue_service)

Contract endpoints (shared with Persons A and B, do not change without telling them):
  POST /proposals                      create, status forced to "pending"
  GET  /proposals?status=              list
  POST /proposals/{id}/decision        {"decision": "approve"|"reject", "reason": str}
  POST /proposals/{id}/receipt         {quote, fill, tx_hash, status}

Product-layer extensions (additive, nothing in the contract changes):
  GET  /proposals/{id}                 one proposal
  GET  /receipts                       ledger: every proposal that has a receipt
  GET  /config  PUT /config            drift slider value + threshold (Person A reads GET /config)
  GET  /balances  PUT /balances/{agent} wallet snapshots (Person A pushes real ones)
  /bounties ...                        bounty board state machine
  POST /demo/attack  POST /demo/reset  demo helpers

This service never signs or sends anything. Money only moves in Person A's execute().
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import random
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

import seed

DATA_FILE = Path(os.getenv("QUEUE_DATA_FILE", Path(__file__).parent / "data" / "store.json"))
STUB_EXECUTOR = os.getenv("STUB_EXECUTOR", "1") != "0"   # set STUB_EXECUTOR=0 once Person A's router is live
STUB_DELAY_S = float(os.getenv("STUB_DELAY_S", "2.0"))

STATUSES = ("pending", "approved", "rejected", "executed", "failed")
BLOCK_PREFIX = "POLICY_BLOCK"

# ---------------------------------------------------------------- storage

_lock = threading.RLock()


def _now() -> float:
    return time.time()


def _fresh_store() -> dict:
    t = _now()
    proposals = []
    for i, p in enumerate(seed.seed_proposals()):
        p.setdefault("created_at", t - 300 + i * 20)
        p.setdefault("seed", True)
        proposals.append(p)
    return {
        "proposals": proposals,
        "bounties": seed.seed_bounties(),
        "balances": seed.seed_balances(),
        "config": dict(seed.DEFAULT_CONFIG),
    }


def _load() -> dict:
    if not DATA_FILE.exists():
        store = _fresh_store()
        _save(store)
        return store
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(store: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    # OneDrive / antivirus can briefly lock the file on Windows, so retry.
    for attempt in range(10):
        try:
            os.replace(tmp, DATA_FILE)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    raise RuntimeError(f"Could not write {DATA_FILE}")


class Store:
    """with Store() as s: ... mutate s ...  -> saved on exit, all under one lock."""

    def __enter__(self) -> dict:
        _lock.acquire()
        self.data = _load()
        return self.data

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                _save(self.data)
        finally:
            _lock.release()


def _find(items: list, item_id: str, kind: str) -> dict:
    for it in items:
        if it.get("id") == item_id:
            return it
    raise HTTPException(404, f"{kind} {item_id} not found")


def _flag_text(flag: Any) -> str:
    if isinstance(flag, dict):
        return str(flag.get("message") or flag.get("text") or flag)
    return str(flag)


def _is_blocked(p: dict) -> bool:
    return any(_flag_text(f).upper().startswith(BLOCK_PREFIX) for f in p.get("flags") or [])


# ---------------------------------------------------------------- models

class Step(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Literal["swap", "transfer"]
    asset: str            # swap: what is SOLD.  transfer: what is PAID.
    amount: float


class Alternative(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: list[Step] = []
    rejected_reason: str = ""


class ProposalIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    buyer: str
    seller: str
    purpose: str
    amount_usd: float
    path: list[Step] = []
    expected_cost: Any = None
    alternatives: list[Alternative] = []
    drift: Any = None
    flags: list[Any] = []
    source: Any = None
    status: Optional[str] = None   # ignored: always created as pending


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = ""


class ReceiptIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    quote: Any = None
    fill: Any = None
    tx_hash: Optional[str] = None
    status: Literal["executed", "failed"] = "executed"


class ConfigIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    drift_pct: Optional[float] = Field(default=None, ge=0, le=50)
    drift_threshold_pct: Optional[float] = Field(default=None, ge=0, le=50)


class BountyIn(BaseModel):
    title: str
    description: str = ""
    price_usd: float = Field(gt=0)
    asset: str = "USDC"
    poster: str = "research-agent"
    deadline: str = ""


class ClaimIn(BaseModel):
    claimant: str = Field(min_length=1, max_length=100)


class SubmitIn(BaseModel):
    submission: str = Field(min_length=1, max_length=50000)


class VerifyIn(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = ""


# ---------------------------------------------------------------- proposals

def _create_proposal(s: dict, body: dict) -> dict:
    p = copy.deepcopy(body)
    p["id"] = p.get("id") or f"prop-{uuid.uuid4().hex[:8]}"
    if any(x["id"] == p["id"] for x in s["proposals"]):
        raise HTTPException(409, f"proposal {p['id']} already exists")
    p["status"] = "pending"
    p["created_at"] = _now()
    p.setdefault("flags", [])
    p.setdefault("alternatives", [])
    if _is_blocked(p):
        # A policy block is final and never reaches a person.
        p["status"] = "rejected"
        p["blocked"] = True
        p["decision"] = {
            "decision": "reject",
            "by": "policy",
            "reason": "; ".join(_flag_text(f) for f in p["flags"] if _flag_text(f).upper().startswith(BLOCK_PREFIX)),
            "at": _now(),
        }
    s["proposals"].append(p)
    return p


def _settle_bounty(s: dict, proposal: dict) -> None:
    """When a bounty payout/refund proposal is executed, close the bounty."""
    bid, role = proposal.get("bounty_id"), proposal.get("bounty_role")
    if not bid or not role:
        return
    for b in s["bounties"]:
        if b["id"] != bid:
            continue
        if proposal["status"] == "executed":
            if role == "payout":
                b["status"] = "paid"
                b["history"].append({"status": "paid", "note": f"Paid out via {proposal['id']}", "at": _now()})
            elif role == "refund":
                b["status"] = "refunded"
                b["history"].append({"status": "refunded", "note": f"Refunded via {proposal['id']}", "at": _now()})
            elif role == "funding":
                b["escrow_funded"] = True
                b["history"].append({"status": b["status"], "note": "Escrow funded", "at": _now()})
        elif proposal["status"] == "failed":
            b["history"].append({"status": b["status"], "note": f"{role} transfer failed ({proposal['id']})", "at": _now()})


def _write_receipt(s: dict, p: dict, receipt: dict) -> dict:
    if p["status"] != "approved":
        raise HTTPException(409, f"proposal {p['id']} is {p['status']}; only approved proposals can be executed")
    receipt = dict(receipt)
    receipt["at"] = _now()
    p["receipt"] = receipt
    p["status"] = receipt.get("status", "executed")
    _settle_bounty(s, p)
    return p


# ---------------------------------------------------------------- stub executor

def _stub_receipt(p: dict) -> dict:
    cost = p.get("expected_cost")
    quoted_cost = cost.get("total_usd", 0) if isinstance(cost, dict) else float(cost or 0)
    if isinstance(cost, dict):
        fee = float(cost.get("fees_usd") or 0)
    else:
        fee = 0.0
    slip = round(random.uniform(-0.00005, 0.00012), 6)
    invoice = float(p.get("amount_usd") or 0)
    return {
        "quote": {
            "amount_usd": invoice,
            "cost_usd": quoted_cost,
            "invoice_usd": invoice,
            "fee_usd": fee,
            "seller_net_usd": invoice,
            "gross_debit_usd": invoice + fee,
            "simulated": True,
        },
        "fill": {
            "amount_usd": invoice,
            "cost_usd": max(0.0, round(quoted_cost + slip, 6)),
            "invoice_usd": invoice,
            "fee_usd": fee,
            "seller_net_usd": invoice,
            "gross_debit_usd": invoice + fee,
            "simulated": True,
        },
        "tx_hash": "STUB-" + uuid.uuid4().hex[:16],
        "status": "executed",
        "stub": True,
        "simulated": True,
        "note": "SIMULATED fill — stub executor; not a chain transaction.",
    }


def _seller_key(seller: str) -> str:
    return str(seller).split(" ")[0]


def _apply_simulated_balances(s: dict, p: dict) -> None:
    """Stub mode only: move SIMULATED wallet balances so the demo shows money moving.
    Never touches a wallet Person A has marked as real (simulated: false)."""
    bal = s["balances"]
    buyer = bal.get(p.get("buyer"))
    seller = bal.get(_seller_key(p.get("seller", "")))

    def asset_row(w, asset):
        for a in w.setdefault("assets", []):
            if a["asset"] == asset:
                return a
        row = {"asset": asset, "amount": 0.0, "usd_value": 0.0}
        w["assets"].append(row)
        return row

    for step in p.get("path") or []:
        amount = float(step.get("amount") or 0)
        if buyer and buyer.get("simulated"):
            src = asset_row(buyer, step["asset"])
            unit = (src["usd_value"] / src["amount"]) if src["amount"] else (1.0 if step["asset"] == "USDC" else 0)
            if step["type"] == "swap":
                src["amount"] = round(max(0.0, src["amount"] - amount), 8)
                src["usd_value"] = round(src["amount"] * unit, 4)
                to = asset_row(buyer, step.get("to_asset", "USDC"))
                to["amount"] = round(to["amount"] + amount * unit, 8)
                to["usd_value"] = round(to["usd_value"] + amount * unit, 4)
                continue
            src["amount"] = round(max(0.0, src["amount"] - amount), 8)
            src["usd_value"] = round(src["amount"] * unit, 4)
        if step["type"] == "transfer" and seller and seller.get("simulated"):
            dst = asset_row(seller, step["asset"])
            usd_in = float(p.get("amount_usd") or 0)
            dst["amount"] = round(dst["amount"] + amount, 8)
            dst["usd_value"] = round(dst["usd_value"] + usd_in, 4)


async def _stub_loop():
    while True:
        await asyncio.sleep(0.5)
        try:
            with Store() as s:
                for p in s["proposals"]:
                    decided = (p.get("decision") or {}).get("at", 0)
                    if p["status"] == "approved" and "receipt" not in p and _now() - decided >= STUB_DELAY_S:
                        _write_receipt(s, p, _stub_receipt(p))
                        _apply_simulated_balances(s, p)
        except Exception as e:  # never let the demo helper crash the service
            print("stub executor error:", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with Store():
        pass  # creates and seeds the store on first run
    task = asyncio.create_task(_stub_loop()) if STUB_EXECUTOR else None
    print(f"Runway queue: data={DATA_FILE}  stub_executor={'ON' if STUB_EXECUTOR else 'OFF'}")
    yield
    if task:
        task.cancel()


app = FastAPI(title="Runway approval queue", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "stub_executor": STUB_EXECUTOR}


@app.post("/proposals", status_code=201)
def create_proposal(body: ProposalIn):
    with Store() as s:
        return _create_proposal(s, body.model_dump(exclude_none=False))


@app.get("/proposals")
def list_proposals(status: Optional[str] = Query(default=None)):
    if status and status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    with Store() as s:
        items = [p for p in s["proposals"] if not status or p["status"] == status]
    return sorted(items, key=lambda p: p.get("created_at", 0), reverse=True)


@app.get("/proposals/{pid}")
def get_proposal(pid: str):
    with Store() as s:
        return _find(s["proposals"], pid, "proposal")


@app.post("/proposals/{pid}/decision")
def decide(pid: str, body: DecisionIn):
    with Store() as s:
        p = _find(s["proposals"], pid, "proposal")
        if p.get("blocked"):
            raise HTTPException(409, "blocked by policy; this proposal can never be approved")
        if p["status"] != "pending":
            raise HTTPException(409, f"proposal is already {p['status']}")
        p["status"] = "approved" if body.decision == "approve" else "rejected"
        p["decision"] = {"decision": body.decision, "by": "human", "reason": body.reason, "at": _now()}
        return p


@app.post("/proposals/{pid}/receipt")
def receipt(pid: str, body: ReceiptIn):
    with Store() as s:
        p = _find(s["proposals"], pid, "proposal")
        return _write_receipt(s, p, body.model_dump())


@app.get("/receipts")
def receipts():
    with Store() as s:
        items = [p for p in s["proposals"] if "receipt" in p]
    return sorted(items, key=lambda p: p["receipt"].get("at", 0), reverse=True)


# ---------------------------------------------------------------- config & balances

@app.get("/config")
def get_config():
    with Store() as s:
        return s["config"]


@app.put("/config")
def put_config(body: ConfigIn):
    with Store() as s:
        s["config"].update({k: v for k, v in body.model_dump().items() if v is not None})
        return s["config"]


@app.get("/balances")
def get_balances():
    with Store() as s:
        return s["balances"]


@app.put("/balances/{agent}")
def put_balance(agent: str, body: dict):
    """Person A: push a real snapshot, e.g. {"label":..., "treasury_mode":..., "assets":[{asset, amount, usd_value}]}."""
    with Store() as s:
        s["balances"][agent] = {**s["balances"].get(agent, {}), **body, "simulated": body.get("simulated", False)}
        return s["balances"][agent]


# ---------------------------------------------------------------- bounties

def _bounty_proposal(s: dict, b: dict, role: str, seller: str, purpose: str, source_text: str) -> dict:
    return _create_proposal(s, {
        "buyer": b["escrow_wallet"] if role != "funding" else b["poster"],
        "seller": seller,
        "purpose": purpose,
        "title": {"funding": f"Fund bounty escrow: {b['title']}",
                  "payout": f"Pay {seller} for bounty work",
                  "refund": f"Refund bounty escrow to {seller}"}[role],
        "rationale": {"funding": "Posting a bounty locks its reward in a dedicated escrow wallet, so the money can't be spent on anything else.",
                      "payout": f"The submitted work for \"{b['title']}\" was approved. This releases the escrowed reward to the worker.",
                      "refund": f"The submitted work for \"{b['title']}\" was rejected. This returns the escrowed reward to the poster."}[role],
        "amount_usd": b["price_usd"],
        "path": [{"type": "transfer", "asset": b["asset"], "amount": b["price_usd"]}],
        "expected_cost": {"price_impact_usd": 0.0, "fees_usd": 0.0, "total_usd": 0.0},
        "alternatives": [],
        "drift": None,
        "flags": [],
        "source": {"kind": "bounty_board", "text": source_text},
        "bounty_id": b["id"],
        "bounty_role": role,
    })


@app.get("/bounties")
def list_bounties():
    with Store() as s:
        return list(reversed(s["bounties"]))


@app.post("/bounties", status_code=201)
def post_bounty(body: BountyIn):
    with Store() as s:
        bid = f"bounty-{uuid.uuid4().hex[:6]}"
        b = {
            "id": bid, **body.model_dump(), "status": "open", "escrow_wallet": f"escrow-{bid}",
            "escrow_funded": False, "claimant": None, "submission": None,
            "history": [{"status": "open", "note": f"Posted by {body.poster}", "at": _now()}],
        }
        s["bounties"].append(b)
        fund = _bounty_proposal(s, b, "funding", b["escrow_wallet"],
                                f"Fund escrow for bounty: {b['title']}", f"Bounty posted: {b['title']}")
        b["funding_proposal_id"] = fund["id"]
        return b


def _transition(bid: str, expect: str, new: str, note: str, **fields):
    with Store() as s:
        b = _find(s["bounties"], bid, "bounty")
        if b["status"] != expect:
            raise HTTPException(409, f"bounty is {b['status']}, expected {expect}")
        b.update(fields)
        b["status"] = new
        b["history"].append({"status": new, "note": note, "at": _now()})
        return b


@app.post("/bounties/{bid}/claim")
def claim(bid: str, body: ClaimIn):
    return _transition(bid, "open", "claimed", f"Claimed by {body.claimant}", claimant=body.claimant)


@app.post("/bounties/{bid}/submit")
def submit(bid: str, body: SubmitIn):
    return _transition(bid, "claimed", "submitted", "Work submitted", submission=body.submission)


@app.post("/bounties/{bid}/verify")
def verify(bid: str, body: VerifyIn):
    """Approving work does NOT pay. It creates a payout proposal that a human must approve like any other order."""
    with Store() as s:
        b = _find(s["bounties"], bid, "bounty")
        if b["status"] != "submitted":
            raise HTTPException(409, f"bounty is {b['status']}, expected submitted")
        if b.get("settlement_proposal_id"):
            raise HTTPException(409, "settlement already proposed")
        if body.decision == "approve":
            p = _bounty_proposal(s, b, "payout", b["claimant"],
                                 f"Pay {b['claimant']} for approved bounty work: {b['title']}",
                                 f"Verifier approved submission. {body.reason}".strip())
            note = "Work approved; payout awaiting approval"
        else:
            p = _bounty_proposal(s, b, "refund", b["poster"],
                                 f"Refund escrow to {b['poster']}: submission rejected for {b['title']}",
                                 f"Verifier rejected submission. {body.reason}".strip())
            note = f"Work rejected; refund awaiting approval. {body.reason}".strip()
        b["settlement_proposal_id"] = p["id"]
        b["verification"] = {"decision": body.decision, "reason": body.reason, "at": _now()}
        b["history"].append({"status": b["status"], "note": note, "at": _now()})
        return b


# ---------------------------------------------------------------- specialists

@app.get("/specialists")
def specialists():
    """Registry of specialist sellers. Reputation = seeded history + what this ledger shows (not self-reported)."""
    with Store() as s:
        out = []
        for sp in [*seed.SPECIALISTS, *s.get("registered_specialists", [])]:
            linked = {j.get("proposal_id") for j in s.get("specialist_jobs", []) if j['specialist_id'] == sp['id']}
            mine = [p for p in s["proposals"] if p['id'] in linked] if sp.get('payout_user') else [p for p in s["proposals"] if str(p.get("seller", "")).startswith(sp["id"])]
            done = [p for p in mine if p["status"] == "executed"]
            jobs = sp["base"]["jobs"] + len(done)
            refunds = sp["base"]["refunds"] + len([p for p in mine if p["status"] == "failed"])
            wallet = s["balances"].get(sp.get("payout_user", sp["id"]), {"assets": []})
            out.append({
                **{k: v for k, v in sp.items() if k not in {"base", "owner_token_hash"}},
                "jobs": jobs,
                "jobs_completed": len([j for j in s.get("specialist_jobs", []) if j["specialist_id"] == sp["id"] and j["status"] == "complete"]),
                "earned_usd": round(sp["base"]["earned_usd"] + sum(float(p.get("amount_usd") or 0) for p in done), 4),
                "refunds": refunds,
                "success_rate": round(100 * (jobs - refunds) / jobs, 1) if jobs else None,
                "pending": len([p for p in mine if p["status"] == "pending"]),
                "wallet": wallet,
                "wallet_usd": round(sum(float(a.get("usd_value") or 0) for a in wallet.get("assets", [])), 4),
            })
        return out


# ---------------------------------------------------------------- demo helpers

@app.post("/demo/attack", status_code=201)
def demo_attack():
    """Inject the canned prompt-injection proposal (Person B's attack script can POST its own instead)."""
    with Store() as s:
        return _create_proposal(s, seed.attack_proposal())


@app.post("/demo/reset")
def demo_reset():
    with Store() as s:
        s.clear()
        s.update(_fresh_store())
        return {"ok": True}


from marketplace import install as install_marketplace
install_marketplace(app, Store, _find)
