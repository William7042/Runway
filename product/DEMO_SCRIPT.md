# Real-money Runway demo

## Prepared setup

Run the demo from this repository in two Codex chats: Buyer (`test`) and Seller (`test2`). Both use Runway MCP. Servers: frontend http://127.0.0.1:5173, queue http://127.0.0.1:8000, optional built-in agent http://127.0.0.1:8200.

Private, gitignored preparation files:
- `.runway/demo-seller.json`: current specialist ID and seller owner token. Never display its contents on the projector.
- `.runway/demo-prep.json`: buyer request, specialist ID, bounty payload, and expected budget. This file contains no owner token.

The prepared specialist is `Runway Treasure Analyst`, paid to `test2`, charging 4 PYUSD. Each demonstrated payment currently expects 4 PYUSD net to the seller plus a 1 PYUSD transfer fee. Two payments therefore expect 10 PYUSD plus any additional network fees. Read the fresh quote before approving. Nothing in preparation signs or sends a payment.

Do not reset demo data: it includes real receipts. Do not present seeded wallets or simulated services as real money. Do not claim every listed asset has a tested route. The voice desk is optional; its live voice service has not been verified in this preparation.

## 1. Show the real wallets (30 seconds)

Open `/#wallet`. Show `test` and `test2`, their real holdings, and existing transaction receipts. Note the starting PYUSD balances so the audience can compare after settlement.

Say: “These are two real wallets. One agent buys work; another sells it. The agent proposes the spend, and I approve each financial order.”

## 2. Request a specialist via MCP (45 seconds)

Open `/#hire` to show the prepared specialist. In Buyer Codex, send:

> Read `.runway/demo-prep.json`. Use Runway MCP `request_specialist_job` with the exact `specialist_request` object. Save the returned job ID privately in `.runway/demo-job.json` for this demo. Stop after creating the proposal; do not approve or execute it. Reuse the supplied idempotency key if retrying.

Open `/#desk`. Show the pending purchase, purpose, buyer, seller, route, seller net, fees, and warnings. Nothing has moved yet.

## 3. Approve and pay (45 seconds)

Review the exact proposal and click Approve yourself. The queue immediately schedules the approved specialist payment; no further buyer or seller call is needed to send it. In Buyer Codex:

> Read `.runway/demo-job.json`. Use Runway MCP to check the job and show its payment receipt and transaction hash. If the payment stopped, inspect the error; do not create a replacement order.

Show the real receipt, then `/#wallet`. Allow a few seconds for balance refresh. The expected change is buyer minus 5 PYUSD and seller plus 4 PYUSD, subject to the actual quoted fees. Open the transaction explorer link on the receipt.

## 4. Seller fulfills the paid job (45 seconds)

In Seller Codex:

> Privately read `.runway/demo-seller.json`. Use its specialist_id and owner_token with Runway MCP `list_specialist_jobs`. For the current paid demo job, perform the requested analysis and use `submit_specialist_result` to deliver it. Never print the owner token. Do not deliver an unpaid job.

In Buyer Codex:

> Use Runway MCP `get_specialist_job` for the job in `.runway/demo-job.json` and show its completed result.

Show `/#sell` with the completed job. Say: “Runway handles discovery, payment approval, settlement, and delivery tracking. The vendor runs the specialist.”

## 5. Post and complete a bounty (60–90 seconds)

In Buyer Codex:

> Read the `bounty` object in `.runway/demo-prep.json`. Use Runway MCP `post_bounty` with those exact fields and save the returned bounty ID in `.runway/demo-bounty.json`. Do not post a duplicate if that file already identifies this demo bounty. No payment should happen at posting.

Show `/#hire/bounties`. In Seller Codex:

> Read `.runway/demo-bounty.json`. Use Runway MCP to claim that bounty as test2, produce the requested checklist, and submit the work. Do not approve work or payments yourself.

On the bounty card, review the submission and click **Approve work**. This prepares a financial proposal; it does not pay yet. Open `/#desk`, review its fees and seller net, then approve that exact payout. The local queue executes approved direct bounty payouts. Wait for the real receipt; if the bounty remains unpaid, inspect the proposal and failure before retrying anything.

Show the paid bounty and real wallet balances. Explain: “The bounty is direct payment after accepted work. Funds are not reserved in escrow.”

## 6. Finish (20 seconds)

Show both real receipts in the wallet history and the delivered specialist result. Say: “Any MCP-capable agent can buy or sell work through this interface. Every financial order needs a human decision, and settlement leaves an auditable receipt.”

Optional: demonstrate rejecting a separate proposal without executing it. Optional: show the supported asset catalog and a historical real swap receipt; a fresh swap requires its own quote and approval. The main demo uses the verified PYUSD route.

For an intentional second paid demo, choose a new specialist idempotency key and new local job/bounty tracking files. Never change the key just to retry an uncertain payment.
