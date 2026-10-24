# Live two-agent demo

Open http://127.0.0.1:5173/#agents. Buyer `test` plans a review, requests a
payment to specialist `test2`, and waits for a human decision. After the router
confirms the transfer, a separate model conversation performs the specialist
review. The buyer then summarizes it. These are separate roles/conversations
with separate wallets, running inside one local service.

The fixed invoice is **$4 net to test2 plus a $1 transfer fee: $5 total**.
No demo code approves payments. Review the exact amount, recipient, purpose,
and flags in **Approval desk** before approving. Rejection stops the run.

Set `XAI_API_KEY` in the ignored project `.env` (the aliases `GROK_API_KEY` and
`X_API_KEY` also work). Corrected saved keys are picked up on the next call.
The service requires live model calls; it does not substitute offline answers.
The specialist uses the supplied Runway project brief; it does not browse or
claim current market research.

Keep the existing queue on port 8000 with `STUB_EXECUTOR=0` and frontend on
5173. Start the additional service from the repository root:

```sh
RUNWAY_MODE=live DRY_RUN=1 .venv/bin/uvicorn demo.two_agents:app --host 127.0.0.1 --port 8200
```

`DRY_RUN=1` still requires queue approval to preview execution, but never signs,
sends funds, or unlocks paid specialist work. For a real run, restart that
command with `DRY_RUN=0`. This process can execute only its own externally
approved payment proposal, through the money router's fresh simulation and
approval checks. It never polls unrelated proposals for execution.

Runs and answers are persisted under ignored `.runway/agent-runs/`. Only one
job may be active. The approval wait expires after 30 minutes. On a service
restart, inspect unfinished jobs before creating another payment; the service
refuses to silently duplicate one. After a confirmed payment, a failed model
answer can be retried from the dashboard **without paying again**. Failed or
ambiguous payments must be reconciled before any new attempt.

The public proposal/router/queue contracts are unchanged. The new service has
`GET /health`, `GET /runs`, `POST /runs {question}`, `GET /runs/{id}`, and
`POST /runs/{id}/retry-delivery` on port 8200. There is no approval endpoint.

## Claude Haiku testing

Save `ANTHROPIC_API_KEY` (or `CLAUDE_API_KEY`) in `.env`. Claude is selected
automatically when that key exists, using `claude-haiku-4-5-20251001` with a
1,200 output-token limit per call. `CLAUDE_MODEL` overrides the model, and
`LLM_PROVIDER=anthropic` or `xai` explicitly selects a provider. All three
roles (buyer, verifier, specialist) use that provider. Keys stay on the server.
