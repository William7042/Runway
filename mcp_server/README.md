# Runway MCP

Cursor MCP server exposing the approval queue, agent helpers, registry, bounty board, and simulated sellers.

## Setup

```bash
# from repo root
source .venv/bin/activate
pip install -r requirements.txt

# queue must be up for most tools
cd product/queue_service && source .venv/bin/activate
uvicorn app:app --port 8000
```

Project config: [`.cursor/mcp.json`](../.cursor/mcp.json). Reload MCP in Cursor (Settings → MCP → refresh) after pull.

## Tools

| Area | Tools |
| --- | --- |
| Queue | `health`, `list_proposals`, `get_proposal`, `create_proposal`, `decide_proposal`, `attach_receipt`, `list_receipts` |
| Config / wallets | `get_config`, `set_config`, `get_balances`, `set_balance` |
| Bounties | `list_bounties`, `post_bounty`, `claim_bounty`, `submit_bounty`, `verify_bounty` |
| Demo | `demo_attack`, `demo_reset` |
| Agent | `run_research`, `propose_payment`, `check_policy`, `verify_transaction` |
| Registry | `list_specialists`, `search_specialists`, `get_reputation` |
| Sellers | `fetch_seller_filing`, `fetch_seller_archive`, `fetch_seller_specialist` |

Resources: `runway://proposals/pending`, `runway://config`, `runway://specialists`, `runway://balances`.

Prompts: `research_desk`, `review_pending`.

**Safety:** no True Markets calls; no auto-approve; agents propose only. `DRY_RUN=1` by default.
