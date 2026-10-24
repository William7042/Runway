# Runway

Hackathon project: AI agents hold a portfolio and pay for data / bounties / specialists via True Markets, with a human approving every order.

See [DESIGN.md](DESIGN.md) for the full design. This repo currently ships **Person B (agent layer)** plus local stubs for Person A's router and Person C's approval queue so the agent loop can demo before those land.

## Person B — Agent layer

| Piece | Path |
| --- | --- |
| Research agent (Grok) | `agent/research_agent.py` |
| Policy (deterministic) | `agent/policy.py` |
| Verifier (2nd Grok call) | `agent/verifier.py` |
| Specialist registry | `agent/registry.py` |
| Bounty board (app-managed escrow) | `agent/bounty.py` |
| SIMULATED sellers | `sellers/` (ports 8101–8103) |
| Router stub (Person A shape) | `stubs/router_stub.py` |
| Approval queue stub (Person C contract) | `stubs/queue_service.py` |
| Attack demo | `demo/attack_script.py` |

Details: [agent/README.md](agent/README.md)

## Quick demo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional XAI_API_KEY for live Grok

uvicorn stubs.queue_service:app --port 8000   # terminal 1

DRY_RUN=1 python -m demo.run_research         # proposes 3 payments
DRY_RUN=1 python -m demo.attack_script        # policy block + verifier flag
```

**Safety:** demo wallets hold a few dollars. `DRY_RUN=1` means nothing is signed or sent. Technical demo, not financial advice. No auto-approve mode.
