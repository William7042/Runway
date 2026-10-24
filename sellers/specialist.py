"""SIMULATED specialist SEC analyst agent — pay-per-job."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from sellers.common import require_payment

app = FastAPI(
    title="SimSEC Analyst (SIMULATED)",
    description="SIMULATED specialist agent — private annotated notes are fake.",
)


class AnalyzeRequest(BaseModel):
    company: str
    proposal_id: Optional[str] = None
    payment_token: Optional[str] = None


class AnalyzeResponse(BaseModel):
    simulated: bool = True
    company: str
    capability: str = "Summarize SEC filings / flag litigation & dilution risk"
    analysis: str
    risk_score: int


@app.get("/health")
def health():
    return {"ok": True, "simulated": True, "service": "SimSEC Analyst"}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest):
    require_payment(body.proposal_id, body.payment_token)
    return AnalyzeResponse(
        company=body.company,
        analysis=(
            f"[SIMULATED] Specialist notes on {body.company}: dilution risk moderate; "
            f"no material litigation in the mock annotated corpus. "
            f"This endpoint is a stand-in for a private-data specialist agent."
        ),
        risk_score=42,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8103)
