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
| Queue | `health`, `list_proposals`, `get_proposal`, `create_proposal`, `list_receipts` |
| Config / wallets | `get_config`, `set_config`, `get_balances`, `set_balance` |
| Bounties | `list_bounties`, `post_bounty`, `claim_bounty`, `submit_bounty` |
| Demo | `demo_attack`, `demo_reset` |
| Agent | `run_research`, `propose_payment`, `check_policy`, `verify_transaction` |
| Registry | `list_specialists`, `search_specialists`, `get_reputation` |
| Legacy simulated sellers | `fetch_seller_filing`, `fetch_seller_archive`, `fetch_seller_specialist` |
| Marketplace | `register_specialist`, `update_specialist`, `request_specialist_job`, `get_specialist_job`, `execute_specialist_payment`, `list_specialist_jobs`, `submit_specialist_result` |

Resources: `runway://proposals/pending`, `runway://config`, `runway://specialists`, `runway://balances`.

Prompts: `research_desk`, `review_pending`.

**Safety:** human decisions happen in the dashboard. Agent tools cannot approve payments, forge receipts, or approve bounty work. Only `execute_specialist_payment` can execute its job’s already approved router plan; `DRY_RUN=1` prevents signing and sending.

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

## Sell your own specialist through MCP

1. `register_specialist(name, capability, price_usd, payout_user, accepted_assets_csv, endpoint="", simulated=False)`. `payout_user` is a True Markets external user ID, such as `test2`. Keep the returned **owner_token** private: only its hash is persisted. Listings are also visible in the dashboard's Specialists tab, which includes a registration form.
2. Your vendor worker polls `list_specialist_jobs(specialist_id, owner_token)`. Only fully paid jobs appear; approval alone does not unlock work. Run the model/tooling yourself. Runway never calls the stored endpoint automatically.
3. Deliver with `submit_specialist_result(job_id, owner_token, result)`. Retrying the same result is safe; overwriting a completed result is refused.
4. Change pricing/description or pause sales using `update_specialist`. Existing jobs keep the original price and accepted assets.

Buyer flow: `search_specialists` → `request_specialist_job(specialist_id, buyer, request, idempotency_key)` → human approves the pending proposal in the dashboard → `execute_specialist_payment(job_id)` → poll `get_specialist_job(job_id)` for delivery. Reuse the idempotency key on retries. Payment proposals are bound to exactly one job, buyer, seller, invoice, and source. A transport retry recovers an existing proposal instead of paying again.

For live jobs, launch MCP with `RUNWAY_MODE=live`, and configure the seller's payout user and accepted API asset IDs in the existing ignored money-layer accounts file. Listing registration deliberately does not grant spending/signing permissions. Missing routes return a payment setup error and move no money. `DRY_RUN=1` returns previews only; results stay locked. Simulated listings and simulated receipts are permitted together for demonstrations, but cannot unlock live jobs. Shared proposal and approval contracts are unchanged.

## Bounty workers

Use `list_bounties(status="open")` → `claim_bounty(bounty_id, claimant)` → `submit_bounty(bounty_id, submission)`. A claim reserves the task; check `escrow_funded` before beginning paid work. Unfunded claims return an explicit warning. The human reviews work in the dashboard; payout/refund proposals still require a separate financial approval. App-managed bounty escrow retains the existing demo limitations; this does not add on-chain escrow contracts or automatic payout execution.

These are local demo tools, not a public multi-tenant identity system. Seller owner tokens protect listing updates and result delivery; existing buyer/bounty identities rely on the trusted local client. Do not publish the queue server as an authenticated public marketplace. There is no API-key requirement for Runway model calls in this MCP workflow; vendors pay for and run their own agent infrastructure.

Run the isolated protocol smoke test with `.venv/bin/python -m demo.mcp_marketplace_smoke`. It uses a temporary queue, fake payment evidence, and no live wallet funds.
