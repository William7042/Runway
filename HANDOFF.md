# Person A → Persons B and C

The `runway_money` package exposes `propose_payment(buyer, seller, amount_usd, purpose, source)` and `execute(proposal_id)`. Contract fields and queue endpoints are unchanged. `runway_money.stub.StubRouter(queue=...)` accepts an injected queue for tests; otherwise it uses Person C's HTTP service.

**Access finding:** use the five-token commerce allowlist; distinguish simulated examples from verified payment routes. The test user is funded in Solana PYUSD, not USDC. See ACCESS.md.

A proposal is created pending. Only Person C's human decision flow may approve it. Simulation has no real transaction hash. A dry run must never consume approval or mark the real payment executed. Live execution will bind the approved proposal to a locally saved immutable plan and refuse retries after uncertain submission.

No other team chats have been identified or messaged. This file is the immediate on-disk handoff.

## Integration update

Fetched Persons B/C at origin/main c290847. Person C's queue coerces numeric amounts and adds metadata; the money client now compares canonical shared fields while retaining all original warnings and allowing additional verifier warnings. Terminal receipt retries are idempotent. Tests run against the actual product queue with fake money.

The local demo cap is $5 by human authorization; templates remain conservative at $1. Current queue: http://localhost:8000 with STUB_EXECUTOR=0; dashboard: http://127.0.0.1:5173. Real test/test2 balances were pushed using the product balance extension.

**Critical: live execution is held after the API returned fee=0 during preparation but charged 1 PYUSD from the 5 PYUSD transfer. test2 received 4.** The existing terminal receipt remains executed for chain completion, with raw fee/net values; product should display the reconciliation in RECONCILIATION.md. Future receipts compare net settlement and classify underpayments as failed. A pre-sign decoder is still needed before the hold can safely be lifted.

Person B still imports its original `stubs.router_stub`; that agent path remains simulated. Wiring the live router requires a draft-before-enqueue adapter so policy/verifier warnings are complete before queue creation, actual-path policy checks (including PYUSD), and receipt model support for null transaction hashes during dry-run. The money CLI and Person C queue integration are verified; the agent loop has not been silently switched to live funds. Shared endpoints and fields were not changed.

## Live connection and order proof completed

Person B's live mode now calls `runway_money.agent_adapter.draft_payment`, then checks actual path assets/fees and verifier warnings before enqueueing exactly once. The stub remains the default. The five shared payment arguments and queue endpoints are unchanged. `record_velocity=False` is an additive policy option for the preliminary check so a live request is counted once. Policy allowlists and registered buyer/seller IDs still apply.

A human-approved 2 PYUSD conversion settled 1.996651 USDC; a separate Gateway order spent 1 USDC and received 0.00945721 SOL. SOL proposal 382463f4-1467-490a-9987-8a2cf0544410 has a successful audited receipt. The user explicitly approved its one-off cost allowance (up to $0.07); normal policy defaults remain unchanged. Unsigned preflight and independent chain auditing now guard standalone swaps. Multi-payload bridges are refused. Transfer hold remains. The first conversion's legacy receipt requires a product reconciliation display because the old confirmation lookup used the wrong order namespace; local on-chain reconciliation proves success, and the confirmation path is fixed for future trades. All work is on main.

## Transfer-fee investigation

Unsigned PYUSD/Solana probes at gross 5, 6, and 10 all encode a 1 PYUSD fee (seller receives 4, 5, and 9). API create/GET fee and received remain zero while awaiting signature. Preview pricing now uses simulated wallet changes and flags invoice underpayment before enqueue. See TRANSFER_FEES.md; no funds moved during this investigation. Transfer hold and normal fee/spend limits remain unchanged.

## Current policy — $1 transfer fee authorized

The human authorized a $1 transfer-fee budget and removal of the old blanket hold. A fresh unsigned live draft verified **6 PYUSD gross debit → 5 PYUSD seller net + 1 PYUSD fee**. No funds were moved. The prior hold evidence is retained with its explicit resolution; any new settlement mismatch can establish a new hold.

Payment proposals treat `amount_usd` as the seller invoice and show the gross transfer amount in `path`, the fee in `expected_cost`, and seller net/fee/total debit in approval flags. Gross-up is derived from simulation, not a hardcoded deduction. Lower fees reduce the gross debit; fees above $1 or changed recipient net require a fresh plan. Approval still precedes every signature. Invoice caps remain separate from the authorized fee allowance. Existing swap slippage/fee checks remain active.

`RUNWAY_PAYMENT_FEE_USD=1` controls the disclosed transfer allowance. The live agent checks that allowance separately from swap price impact, using the deterministic router plan rather than language-model text. The shared proposal fields and original payment interface are unchanged.

## Seller marketplace and bounty MCP workflow

Latest origin pulled to `21783bf`; local token/wallet cleanup preserved. Product
extensions are additive: persisted `POST /specialists`, listing updates, and
`/specialist-jobs` request/payment/result routes. Existing proposal/router
contracts are unchanged. MCP registration/search/resources use the same product
registry shown by the dashboard. New listings use owner tokens (hash stored),
fixed job invoices, idempotency keys, and confirmed-payment delivery gates.
Money-layer recipient/asset configuration remains required for live purchases.
Agent tools no longer expose financial decisions, receipt attachment, or bounty
work approval; those remain in the human dashboard. Bounty claim/submit remains
a local trusted-client demo; app-managed escrow limitations are unchanged.
