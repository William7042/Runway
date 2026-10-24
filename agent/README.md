# Person B — Agent layer

Research agent, SIMULATED sellers, specialist registry, bounty board, deterministic policy, Grok verifier, prompt-injection demo.

**Never calls True Markets.** Payments go through Person A's `propose_payment` (stub in `stubs/router_stub.py` until the real router lands) and Person C's approval queue (`http://localhost:8000`).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: set XAI_API_KEY for live Grok

# Terminal 1 — approval queue (Person C contract; local stub)
uvicorn stubs.queue_service:app --reload --port 8000

# Terminal 2 — SIMULATED sellers (needed for paid→data)
python -m sellers.run_all

# Terminal 3 — research desk (proposes ~3 payments, does NOT execute)
DRY_RUN=1 python -m demo.run_research

# After you approve in the UI (stub executor posts a receipt), fetch seller data:
DRY_RUN=1 python -m demo.run_research --fetch

# Attack demo — policy blocks drain; flags show fetched_page source
DRY_RUN=1 python -m demo.attack_script

# Bounty board (app-managed escrow)
DRY_RUN=1 python -m demo.run_bounty
```

Planner picks from the specialist **registry** (price + ledger reputation). Without an API key,
planner/verifier use a deterministic offline stub so the demo still runs. Prefer `LLM_PROVIDER=xai`
(+ `XAI_API_KEY`) for Grok; Claude is used only if you set Anthropic keys / `LLM_PROVIDER=anthropic`.

## Ownership boundaries

| This layer does | This layer does not |
| --- | --- |
| Plan paid inputs with Grok | Call `gateway.*` / `defi.*` |
| Policy check + verifier flag | Auto-approve |
| `POST /proposals` to the queue | `execute(proposal_id)` (Person A) |
| Mock sellers + registry + bounties | Approval UI (Person C) |

## Contract reminders

- Proposal / Receipt shapes live in `agent/models.py` — tell A and C before changing.
- Only `status=approved` may execute; there is no auto-approve mode for the agent.
- Escrow is **app-managed**, not a smart contract (see `agent/bounty.py` + UI strings).
- Sellers are labeled **SIMULATED** in code and HTTP responses.
- Reputation is read from `data/ledger`, not self-reported.
