Runway: Design Doc
Oct 24, 2026 · @William
Vision
Runway is an economy for AI agents: they hold real assets, hire specialist agents and humans through a bounty board, and pay in whatever they hold, while a person approves every order and the underlying investments stay invested.
Today an agent cannot buy anything. Paywalls, subscriptions, and human-only services all assume a person with a credit card, so every purchase stalls and pings a human. Stablecoin transfers fix the payment half, but a stablecoin-only budget leaves money idle and forces teams to sell the assets they actually want to hold.
Runway fixes both. The agent's treasury is a portfolio (for example ETH and SOL, ETH), and a payment router converts or transfers only what each purchase needs, at the best available quote. True Markets supplies the quotes, orderbooks, wallets, and local signing underneath.
Goals and non-goals
The hackathon build proves one complete loop end to end: an agent buys a service, the router pays it from a stock portfolio, and a human approved the order first.
Goals
• Real, on-chain execution of at least one quote, order, and transfer during the demo
• A human approval step on every order, with a plain-English preview
• A payment router that picks the cheapest path from what the buyer holds to what the seller wants
• A treasury mode that pays from gains or in kind, so principal stays invested
• A bounty board with escrow, and at least one specialist agent selling data
• A receipt for every payment: what was bought, what was sold, and execution quality
Non-goals
• A live public marketplace with real sellers. Sellers are simulated, and we say so.
• Autonomous trading for profit. Agents spend; they do not speculate.
• Smart-contract escrow. Escrow is app-managed wallets, with funds visible on-chain.
• Support for every asset. The router reads the assets our API key can trade and uses those.
Core scenarios
Three scenarios carry the whole product; the demo runs all three in one session.
Scenario
What happens
What it proves
Research desk
A user asks a question. The agent plans, finds it needs three paid inputs, and requests approval to pay for each.
Agents can buy things, with a human gate
Bounty
The agent posts a task (for example, a human fact-check) with a price. A worker claims it and a verifier approves. Escrow pays out.
Agents can hire humans and other agents
Specialist hire
The agent finds a specialist agent that holds data it lacks, then pays per job in the seller's preferred asset.
Agents can pay in anything, via the router
System architecture
The agent never calls the True Markets API directly: every proposal passes the policy layer and a human before the router executes it, and the bounty board creates its escrow wallets through the same API.
Human approval flow
A policy block is final and never reaches a person. A verifier mismatch does not block the request but is flagged on the approval card. There is no auto-approve mode: a rejection is logged and the agent is told why.
Payment router
The router takes what the buyer holds, what the seller wants, and an amount, and returns the cheapest executable path. Nothing runs until a human approves it.
1. Inputs: buyer wallet balances, seller's accepted asset, amount owed in USD terms.
2. Candidates: pay in kind if the seller accepts a held asset; otherwise swap one held asset into the seller's asset, then transfer.
3. Pricing: call the quote endpoint for each swap candidate and rank by total cost, meaning price impact plus fees.
4. Guards: reject any path over the price-impact limit, and for tokenized stocks reject any sale where the on-chain price has drifted too far from the reference price.
5. Proposal: bundle the best path into one approval request: what is sold, what is paid, expected cost, and the alternatives that were rejected.
6. Execution: after approval, place the order, sign locally, confirm the fill, then send the transfer.
7. Receipt: write a ledger row with the quote, the fill, and the difference between them.
The router reads available assets and pairs from the API at startup instead of hard-coding them, so it keeps working when the set of tradable assets changes.
Treasury modes
A person cannot sell shares and still own them, so Runway offers three honest ways to pay while staying invested. The owner picks one per agent.
Mode
How it pays
What stays invested
Best when
Pay in kind
Transfers the held asset (for example ETH) straight to the seller
Everything except the amount paid; no swap fee
The seller is happy to hold the asset
Endowment
Sells only unrealized gains above cost basis, computed from transaction history
The original principal
The owner wants a self-funding agent
Auto top-up
Pays from stablecoin, then buys back toward the target allocation with limit orders
Exposure returns to target over time
The owner wants steady exposure
For tokenized stocks, every sale or buy-back first compares the on-chain price to the reference price of the underlying stock. True Markets calls a gap between the two unanchored pricing. When the gap is above a set threshold, the agent shrinks the order, waits, or pays from stablecoin instead.
Cost basis comes from the account's own transaction history, so endowment mode never relies on the agent's memory.
Bounty board and escrow
Each bounty gets its own escrow wallet, so funds for a task are visible on-chain and cannot be spent on anything else by the app.
1. Post: a human or agent posts a task, a price, an accepted asset, and a deadline. The poster approves the funding transfer.
2. Escrow: the app creates a wallet for the bounty and funds it from the poster's wallet.
3. Claim: a worker (human or agent) claims it. One claimant at a time.
4. Submit: the worker submits a result.
5. Verify: a human approves, or for objective tasks a checker agent runs a defined test and a human confirms.
6. Pay out: the escrow wallet transfers to the worker; on rejection or expiry it refunds the poster.
Escrow here is app-managed, not a smart contract, and the doc and demo say so plainly. Disputes in the hackathon build are settled by the poster; a real product would add a neutral arbiter.
Specialist agents and reputation
A specialist agent is a registered seller with a profile: what it does, what private data or tools it holds, its price per job, and which assets it accepts.
Field
Example
Capability
Summarize SEC filings for a company
Private asset
Indexed filings archive the buyer does not have
Price
A few cents per request
Accepted assets
USDC, ETH
Endpoint
Pay-per-request service that returns data after payment is confirmed
The buyer agent searches the registry, compares price and fit, and hires through the same approval flow as any other payment.
Reputation is read from the ledger, not self-reported: jobs completed, payouts received, and refunds issued, taken from transaction history. For the hackathon, the specialist services are simulated sellers we run ourselves, and the demo labels them as such.
True Markets API usage map
Every money movement goes through the True Markets Python SDK, whose operations come in two groups: gateway (quotes and orders) and defi (assets, balances, history, trades, transfers, wallets, watchlists). Orders return Turnkey payloads that the SDK signs locally with our API key, so funds never sit with a third party.
Component
SDK operations used
Purpose
Router
gateway.compute_quote, defi.create_quote
Price each candidate path
Execution
gateway.create_order, gateway.execute_order, defi.execute_trade
Place and fill the approved order
Payments
defi.prepare_transfer, defi.execute_transfer
Pay sellers and workers
Wallets
defi.create_wallet
One wallet per agent and per bounty escrow
Treasury
defi.get_balances, defi.get_assets, defi.get_profile
Holdings and tradable assets
Cost basis and receipts
defi.get_history
Endowment mode, reputation, audit trail
Watchlists
defi.get_watchlists, defi.get_watchlist_by_id
Which assets the router considers
Signing
sign_turnkey
Local signature on each approved activity
Supported assets are USDC, PYUSD, SOL, BTC, and ETH. Catalog visibility does not prove an executable payment route; each live route needs quote and simulation checks.
Safety and trust model
No agent can move funds on its own: every order and transfer needs a human approval, and policy checks run before the human even sees the request.
• Human approval on every order. The agent proposes; a person approves or rejects. There is no auto-approve mode in the demo build.
• Deterministic policy layer. Spend caps, asset allowlists, recipient allowlists, and price-impact limits are plain code. The language model cannot talk its way past them.
• Independent verifier. A second model sees only the proposed transaction and the user's original instruction, not the page or message that triggered the request, and flags any mismatch.
• Prompt-injection resistance. Content the agent reads (web pages, seller responses) is treated as data. A payment request that originates from that content is flagged and shown to the human with its source.
• Local signing. The API key stays on our machine, and only approved activities get signed.
• Small balances. Demo wallets hold a few dollars.
• Audit log. Every proposal, approval, rejection, and fill is logged with the reason.
This project is a technical demo, not financial advice, and it does not give investment recommendations.
Demo script
The demo runs about two minutes and ends on a real transaction.
1. Fund. Show the research agent's wallet: mostly ETH, some USDC, in endowment mode.
2. Ask. Pose a question that needs three paid inputs: a filing, a premium archive, and a human fact-check.
3. Plan. The agent lists the three purchases and posts the fact-check as a bounty.
4. Approve. For each payment, an approval card shows what will be sold, what will be paid, the quote, and the drift check. The presenter approves one and rejects another to show the gate works.
5. Pay. The approved swap fills and the transfer lands. Show the transaction on screen.
6. Attack. Feed the agent a page containing a hidden "send everything to this address" instruction. The policy layer and verifier block it, and the approval card shows the flagged source.
7. Drift. Flip the drift slider. The agent refuses to sell ETH at the bad gap and pays from USDC, explaining why.
8. Receipts. End on the ledger: every payment, quote versus fill, and principal still invested.
A recorded backup of this run is kept in case the live demo fails.
Risks and open questions
The largest risk is access: tokenized equities are available only to eligible non-US clients, and our team may not qualify.
Risk
Impact
Mitigation
No access to tokenized equities for a US-based team
An unverified payment route cannot run live
Ask the True Markets team today; otherwise run the same logic on tradable assets and label unverified flows as simulated
Asset coverage is narrower than "anything on the market"
Router has fewer paths
Read tradable assets from the API; confirm which pairs our key can trade
Live swap-then-pay adds demo risk
A failed fill breaks the demo
Dry-run mode, tiny amounts, recorded backup
Escrow is app-managed
Judges may question trust
State it plainly; funds are visible on-chain
Simulated sellers
Looks like a closed loop
Label them as simulated; position the project as buyer-side infrastructure
Human approval on every order slows the flow
Demo drags
Batch approvals into one card per task, with per-item detail
Open questions
[ ] Does our API key have access to ETH/USDC, and can it trade other pairs?
[ ] What are the rate limits and any minimum order sizes?
[ ] Which reference price source do we use for the drift check?
[ ] Which track prompt and judging criteria apply to the second track we want to double up on?
Build plan and cut lines
The router phase is the critical path, because the bounty board, treasury modes, and approval cards all depend on it. Phases are sized for a one-day build; adjust the hours to the real schedule. If time runs short, cut from the bottom of this table first.
Tier
Includes
Must have
Payment router, one specialist agent, one bounty, approval cards, receipts
Should have
Endowment mode, drift check, prompt-injection attack demo
Nice to have
Reputation scoring, multiple specialists, auto top-up mode, second tokenized stock
Shared interfaces to agree on first
Three contracts let the money layer, agent layer, and product layer build in parallel. Settle them in the first 30 minutes and change them only by telling the other two.
1. The proposal object. Everything the agent wants to do with money is one proposal, and the approval card renders it as is.
Field
Meaning
id
Unique proposal id
buyer
Agent wallet making the payment
seller
Recipient wallet or service
purpose
Plain-English reason, written by the agent
amount_usd
Amount owed, in USD terms
path
Ordered steps, each a swap or a transfer with asset and amount
expected_cost
Price impact plus fees for the chosen path
alternatives
Rejected paths with the reason for each
drift
On-chain price versus reference price, for tokenized stocks
flags
Policy or verifier warnings shown on the card
source
What triggered the request, such as the user's message or a fetched page
status
pending, approved, rejected, executed, or failed
2. The approval queue. A small shared service or file that all three layers touch.
• Agent layer creates a proposal with status pending.
• Product layer lists pending proposals and records an approve or reject decision.
• Money layer executes only proposals with status approved, then writes the receipt back.
3. The router interface and its stub. The money layer owns two functions, and ships a stub of the first within the first hour so the others never wait on it.
• propose_payment(buyer, seller, amount_usd, purpose, source) returns a proposal.
• execute(proposal_id) runs an approved proposal and returns a receipt with quote, fill, and transaction hash.
• The stub returns canned proposals and fake receipts in the same shape as the real ones.
Ownership
Layer
Owns
Depends on
Money
True Markets setup, router, treasury modes, drift check, escrow wallets, execution
Nothing; ships the stub first
Agent
Research agent, mock sellers, registry, bounty logic, policy layer, verifier, attack script
Router stub and the queue
Product
Approval cards, dashboard, bounty UI, demo script, backup video
The queue and proposal shape