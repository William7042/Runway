"""SIMULATED filings seller — charges per request, returns data only after payment."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from sellers.common import require_payment

app = FastAPI(
    title="SimFilings (SIMULATED)",
    description="SIMULATED seller — not a real SEC data vendor.",
)


class FilingResponse(BaseModel):
    simulated: bool = True
    company: str
    form: str
    summary: str
    red_flags: list[str]


@app.get("/health")
def health():
    return {"ok": True, "simulated": True, "service": "SimFilings"}


@app.get("/v1/filing", response_model=FilingResponse)
def get_filing(
    company: str = Query(...),
    proposal_id: Optional[str] = None,
    payment_token: Optional[str] = None,
):
    require_payment(proposal_id, payment_token)
    return FilingResponse(
        company=company,
        form="Form D (mock)",
        summary=(
            f"[SIMULATED] {company} appears in a mock Form D corpus with a "
            f"$2.1M raise dated 2024-11. No live SEC call was made."
        ),
        red_flags=["mock: prior name change in 2023", "mock: thin operating history"],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8101)
