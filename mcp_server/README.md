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

**Safety:** human decisions happen in the dashboard. Agent tools cannot approve payments, forge receipts, or approve bounty work. Specialist payments execute through the approval-guarded router, either by the queue worker or the idempotent `execute_specialist_payment` fallback; `DRY_RUN=1` prevents signing and sending.

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

Buyer flow: `search_specialists` → `request_specialist_job(specialist_id, buyer, request, idempotency_key)` → human approves the pending proposal in the dashboard → queue executes the approved payment (with `RUNWAY_SPECIALIST_EXECUTOR=1`) → poll `get_specialist_job(job_id)` for delivery. Reuse the idempotency key on retries. Payment proposals are bound to exactly one job, buyer, seller, invoice, and source. A transport retry recovers an existing proposal instead of paying again.

For live jobs, launch MCP with `RUNWAY_MODE=live`, and configure the seller's payout user and accepted API asset IDs in the existing ignored money-layer accounts file. Listing registration deliberately does not grant spending/signing permissions. Missing routes return a payment setup error and move no money. `DRY_RUN=1` returns previews only; results stay locked. Simulated listings and simulated receipts are permitted together for demonstrations, but cannot unlock live jobs. Shared proposal and approval contracts are unchanged.

## Bounty workers

Use `list_bounties(status="open")` → `claim_bounty(bounty_id, claimant)` → `submit_bounty(bounty_id, submission)`. A claim reserves the task, not money. New bounties leave funds in the poster wallet until the work is reviewed and the exact payment is separately approved. The human reviews work in the dashboard; a payout proposal still requires separate financial approval. Rejected direct-pay work sends no money and requires no refund. New bounties use direct payments, not escrow. The queue can execute their already approved money-layer plans; it never approves them.

These are local demo tools, not a public multi-tenant identity system. Seller owner tokens protect listing updates and result delivery; existing buyer/bounty identities rely on the trusted local client. Do not publish the queue server as an authenticated public marketplace. There is no API-key requirement for Runway model calls in this MCP workflow; vendors pay for and run their own agent infrastructure.

Run the isolated protocol smoke test with `.venv/bin/python -m demo.mcp_marketplace_smoke`. It uses a temporary queue, fake payment evidence, and no live wallet funds.

## Direct bounty payouts

For the tested real demo, post `price_usd=4`, `asset=PYUSD`, `poster=test`; claim
as `test2`. Submit work, review it in Hire → Bounties, then approve the quoted
$4 reward plus $1 transfer fee in Approvals. A queue started with
`RUNWAY_BOUNTY_EXECUTOR=1 DRY_RUN=0 STUB_EXECUTOR=0` executes only already
approved direct bounty plans and records the real receipt. Alternatively call
`execute_bounty_payment(bounty_id)` after approval. `DRY_RUN=1` only previews.
No funds are reserved at posting. Poster funds, worker registration, token
acceptance, quote limits, and transfer minimums are checked before proposing.
Historical escrow records remain legacy entries and are not converted.

### Execute specialist payments after human approval

Run the local queue with `RUNWAY_SPECIALIST_EXECUTOR=1`, `STUB_EXECUTOR=0`, and
the intended `DRY_RUN` setting. It checks live specialist invoices every half second
and sends their exact payments through the money router only after dashboard approval.
The buyer no longer needs to call `execute_specialist_payment`; that tool remains an
idempotent fallback. This setting never approves an order. Invoice binding, expiry,
price protection, local signing, and durable duplicate-submission guards still apply.
A stopped attempt records `execution_error` for inspection and is not blindly retried.

### File deliveries and buyer ratings

Specialist work can include text and multiple files (PDFs, spreadsheets, images,
code, archives, or other binary formats). Sellers upload artifacts before finalizing
with `submit_specialist_result`; an empty result is allowed for a file-only delivery.
Limits: five files, 10 MiB per file, 25 MiB per job. Uploaded files are private,
gitignored data in `.runway/artifacts`; downloading never executes a file.

A new job returns a buyer capability once. MCP saves it privately under
`.runway/buyer-jobs/` and uses it for delivery downloads and ratings. Keep these
JSON files private. To view MCP purchases in the browser, import the corresponding
buyer access file in Hire's deliveries panel; seller credentials cannot authorize
buyer ratings. Existing jobs without buyer capabilities cannot acquire one by
knowing a job ID. This local capability mechanism is not a production account
identity or wallet-ownership verification system.

Use `upload_specialist_artifact` to attach seller files, `get_specialist_job` to
inspect completed delivery, and `download_specialist_artifact` to save a buyer's
file. `rate_specialist_job(job_id, stars, review)` uses the saved buyer capability;
`list_specialist_reviews` reads public reviews. One immutable review is allowed
per completed, fully paid, non-simulated job between distinct buyers and sellers.
Identical review retries are idempotent. Reviews do not move money. All purchase
approval and execution rules remain unchanged.
