# Runway

Hackathon project: AI agents hold a portfolio and pay for data / bounties / specialists via True Markets, with a human approving every order.

See [DESIGN.md](DESIGN.md) for the full design. The repo includes the agent layer, Person C's dashboard/queue, and the True Markets money layer. The live agent adapter and a real human-approved SOL order are verified; offline stubs remain available. See [MONEY.md](MONEY.md) for execution limits and the transfer hold.

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

## Cursor MCP

Project MCP config: [`.cursor/mcp.json`](.cursor/mcp.json). After `pip install -r requirements.txt`, reload **Settings → MCP**. With the queue on `:8000`, Cursor can call `run_research`, `list_proposals`, `decide_proposal`, bounties, policy/verifier, and simulated sellers. See [`mcp_server/README.md`](mcp_server/README.md).

## Person A — Money layer

See [MONEY.md](MONEY.md) for True Markets setup, approval-gated execution, treasury modes, and safety tests; [ACCESS.md](ACCESS.md) records live access findings. Person C's real queue is in `product/queue_service/`. Start it with `STUB_EXECUTOR=0` for money-layer integration.
