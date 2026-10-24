"""Minimal approval-queue FastAPI service matching Person C's contract.

Person C owns the real product UI; this JSON-file store lets the agent layer
demo end-to-end at http://localhost:8000 until theirs lands.

Endpoints:
  POST /proposals
  GET  /proposals?status=
  POST /proposals/{id}/decision  body {"decision":"approve"|"reject","reason":str}
  POST /proposals/{id}/receipt   body {quote, fill, tx_hash, status}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.models import Decision, Proposal, ProposalStatus, Receipt
from stubs import router_stub

DATA_DIR = Path(os.getenv("RUNWAY_DATA", "data/proposals"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Runway Approval Queue (stub / Person C contract)")


def _path(pid: str) -> Path:
    return DATA_DIR / f"{pid}.json"


def _save(p: Proposal) -> None:
    _path(p.id).write_text(p.model_dump_json(indent=2))


def _load(pid: str) -> Proposal:
    fp = _path(pid)
    if not fp.exists():
        raise HTTPException(404, f"proposal {pid} not found")
    return Proposal.model_validate_json(fp.read_text())


@app.post("/proposals", response_model=Proposal)
def create_proposal(proposal: Proposal) -> Proposal:
    proposal.status = ProposalStatus.PENDING
    _save(proposal)
    # Keep Person A stub in sync so execute() sees the same object.
    router_stub._PROPOSALS[proposal.id] = proposal
    return proposal


@app.get("/proposals", response_model=list[Proposal])
def list_proposals(status: Optional[str] = None) -> list[Proposal]:
    out: list[Proposal] = []
    for fp in sorted(DATA_DIR.glob("*.json")):
        p = Proposal.model_validate_json(fp.read_text())
        if status is None or p.status.value == status:
            out.append(p)
    return out


@app.get("/proposals/{proposal_id}", response_model=Proposal)
def get_proposal(proposal_id: str) -> Proposal:
    return _load(proposal_id)


@app.post("/proposals/{proposal_id}/decision", response_model=Proposal)
def decide(proposal_id: str, body: Decision) -> Proposal:
    p = _load(proposal_id)
    if p.status != ProposalStatus.PENDING:
        raise HTTPException(400, f"cannot decide on status={p.status.value}")
    if body.decision == "approve":
        p.status = ProposalStatus.APPROVED
    else:
        p.status = ProposalStatus.REJECTED
        if body.reason:
            p.flags.append(f"rejected: {body.reason}")
    _save(p)
    router_stub.mark_status(p.id, p.status)
    return p


@app.post("/proposals/{proposal_id}/receipt", response_model=Proposal)
def attach_receipt(proposal_id: str, body: Receipt) -> Proposal:
    p = _load(proposal_id)
    if p.status != ProposalStatus.APPROVED:
        raise HTTPException(400, "receipt only after approve")
    p.status = ProposalStatus.EXECUTED if body.status in ("executed", "dry_run") else ProposalStatus.FAILED
    # Persist receipt alongside proposal for audit.
    receipt_path = DATA_DIR / f"{proposal_id}.receipt.json"
    receipt_path.write_text(body.model_dump_json(indent=2))
    _save(p)
    router_stub.mark_status(p.id, p.status)
    return p


@app.get("/health")
def health() -> dict:
    return {"ok": True, "store": str(DATA_DIR.resolve())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
