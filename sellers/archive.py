"""SIMULATED premium archive seller."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from sellers.common import require_payment

app = FastAPI(
    title="SimArchive (SIMULATED)",
    description="SIMULATED seller — not a real paywalled archive.",
)


class ArchiveHit(BaseModel):
    simulated: bool = True
    query: str
    hits: list[dict]


@app.get("/health")
def health():
    return {"ok": True, "simulated": True, "service": "SimArchive"}


@app.get("/v1/search", response_model=ArchiveHit)
def search(
    q: str = Query(...),
    proposal_id: Optional[str] = None,
    payment_token: Optional[str] = None,
):
    require_payment(proposal_id, payment_token)
    return ArchiveHit(
        query=q,
        hits=[
            {
                "title": f"[SIMULATED] Coverage snippet for '{q}'",
                "outlet": "MockWire",
                "date": "2025-06-12",
                "note": "Paywalled archive entry — fabricated for the hackathon demo.",
            },
            {
                "title": f"[SIMULATED] Founder profile mention: {q}",
                "outlet": "MockJournal",
                "date": "2024-02-01",
                "note": "No real crawl performed.",
            },
        ],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)
