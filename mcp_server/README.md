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

## x402 v2 offers

`inspect_x402_offer(payment_required_header, resource_url)` parses a seller's
base64 `PAYMENT-REQUIRED` response header without fetching URLs or signing.
It preserves atomic amounts, CAIP-2 networks, seller metadata, and extensions.

`propose_x402_payment(buyer, seller, purpose, payment_required_header,
resource_url, option_index=0)` maps a Solana mainnet `exact` stablecoin offer
to a registered seller and the live API asset catalog (`RUNWAY_MODE=live`).
The proposal uses the existing shared queue contract, with the full offer
bound to the private router plan and its digest shown in the source.
The vendor's recipient must match the registered wallet. Seller-supplied
prices, decimals, or arbitrary recipient changes are never trusted.

**Current scope: offer validation and review only, not x402 settlement.**
Every x402 review carries a `POLICY_BLOCK` warning and the money router refuses
execution even if someone approves it. No `PAYMENT-SIGNATURE` is fabricated;
a queue approval or an ordinary transfer receipt is not an x402 authorization.
`DRY_RUN` never signs or sends. Other chains/schemes are inspectable, but cannot
be mapped to payment review by this adapter yet.

To enable actual x402 settlement, implement a True Markets-compatible Solana
partially signed transaction builder/signer, validate the merchant and sponsor
outcomes, recheck human approval before signing, and integrate a facilitator
that supports the selected scheme/network. Build the recent-blockhash
transaction after the human decision. Then send the standard
`PAYMENT-SIGNATURE` paid retry and validate its `PAYMENT-RESPONSE`. Do not use
the normal True Markets transfer submission path as a substitute for this flow.

References: [x402 v2](https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md),
[Solana exact](https://github.com/x402-foundation/x402/blob/main/specs/schemes/exact/scheme_exact_svm.md).

## Commerce token allowlist

Runway allows **USDC, PYUSD, SOL, BTC, and ETH**. `list_supported_assets`
returns those symbols and, in live mode, matching active entries from the
True Markets API. Token IDs, chains, and addresses are resolved from the API;
wrapped BTC (cbBTC/WBTC), WETH, tokenized stocks, and other symbols are excluded.
The money router filters payment candidates, standalone swaps, and top-ups,
and checks stored plans against the current policy before execution.

This selects permitted assets, not guaranteed execution routes. BTC and ETH
off-chain trading entries do not automatically provide an on-chain seller
payment route. Existing quote, chain, simulation, and human approval checks
still apply. Historical seeded demo proposals may show older assets; they are
not new executable money-layer plans.
