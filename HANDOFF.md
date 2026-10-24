# Person A → Persons B and C

The `runway_money` package exposes `propose_payment(buyer, seller, amount_usd, purpose, source)` and `execute(proposal_id)`. Contract fields and queue endpoints are unchanged. `runway_money.stub.StubRouter(queue=...)` accepts an injected queue for tests; otherwise it uses Person C's HTTP service.

**Access finding:** no NVDAc in the live catalog; use the clearly labeled stub for the stock demo. The test user is funded in Solana PYUSD, not USDC. See ACCESS.md.

A proposal is created pending. Only Person C's human decision flow may approve it. Simulation has no real transaction hash. A dry run must never consume approval or mark the real payment executed. Live execution will bind the approved proposal to a locally saved immutable plan and refuse retries after uncertain submission.

No other team chats have been identified or messaged. This file is the immediate on-disk handoff.

## Integration update

Fetched Persons B/C at origin/main c290847. Person C's queue coerces numeric amounts and adds metadata; the money client now compares canonical shared fields while retaining all original warnings and allowing additional verifier warnings. Terminal receipt retries are idempotent. Tests run against the actual product queue with fake money.

The local demo cap is $5 by human authorization; templates remain conservative at $1. Current queue: http://localhost:8000 with STUB_EXECUTOR=0; dashboard: http://127.0.0.1:5173. Real test/test2 balances were pushed using the product balance extension.

**Critical: live execution is held after the API returned fee=0 during preparation but charged 1 PYUSD from the 5 PYUSD transfer. test2 received 4.** The existing terminal receipt remains executed for chain completion, with raw fee/net values; product should display the reconciliation in RECONCILIATION.md. Future receipts compare net settlement and classify underpayments as failed. A pre-sign decoder is still needed before the hold can safely be lifted.

Person B still imports its original `stubs.router_stub`; that agent path remains simulated. Wiring the live router requires a draft-before-enqueue adapter so policy/verifier warnings are complete before queue creation, actual-path policy checks (including PYUSD), and receipt model support for null transaction hashes during dry-run. The money CLI and Person C queue integration are verified; the agent loop has not been silently switched to live funds. Shared endpoints and fields were not changed.
