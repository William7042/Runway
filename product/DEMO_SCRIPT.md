# Runway demo (about 2 minutes)

**Before you start:** `POST /demo/reset` (or Demo controls → Reset demo data). Two tabs open: the Desk (`/#desk`) and the
Ledger (`/#ledger`). Block explorer tab open for the real tx. Font size up (Ctrl +) so judges can read the cards.

| # | Time | On screen | Say |
|---|---|---|---|
| 1 | 0:00 | **Fund.** Desk, right column: Research agent wallet, mostly NVDAc, some USDC, "Endowment". | "This is an AI research agent. Its treasury isn't cash, it's tokenized Nvidia. In endowment mode it can only spend gains, so the $4 principal stays invested." |
| 2 | 0:15 | **Ask.** Show the question in the card's "Triggered by" box (or have Person B type it live). | "We ask it a question that needs three things it doesn't have: a filing, a premium data archive, and a human fact-check." |
| 3 | 0:25 | **Plan.** Three approval cards appear, one is the bounty funding. | "It plans three purchases. It can't spend a cent without asking. There's no auto-approve and no approve-all." |
| 4 | 0:40 | **Approve one, reject one.** Approve the 10-Q summary (paid in kind, no swap). Reject the archive with reason "too expensive". | "This card shows what it sells, what it pays, the cost, and the cheaper paths it rejected. I'll approve this one… and reject this one. The agent is told why." |
| 5 | 0:55 | **Pay.** Receipt appears in Live receipts with quote vs fill and the tx hash. Click to the explorer. | "That's a real on-chain transaction through True Markets. Quote versus fill, right on the receipt." |
| 6 | 1:10 | **Attack.** Person B runs the attack script (backup: Demo controls → Simulate injection attack). Red card + toast. | "Now the agent reads a web page with a hidden instruction: send everything to this address. It never reaches me. Allowlists and spend caps are plain code; the model can't talk its way past them. You can see the exact hidden text." |
| 7 | 1:30 | **Drift.** Drag the slider past 2%. Badge flips to "Selling paused". | "Tokenized stocks can drift from the real price. Past 2%, Runway refuses to sell NVDA at a bad price and pays from USDC instead." |
| 8 | 1:45 | **Receipts.** Ledger tab: paid, blocked, rejected, principal still invested. | "Every order, every decision, every fill, audited. The agent spent what it needed and the investment stayed invested." |

**If something breaks live:** stay calm, say "here's the recorded run", and play the backup video from the same step.

## 60-second pitch

> Today an AI agent can't buy anything. Paywalls and human-only services all assume a person with a credit card.
> And if you give an agent a stablecoin budget, that money just sits idle.
>
> **Runway is an economy for AI agents: they hold real assets, hire each other, and pay in anything, while a person
> approves every order and the investments stay invested.**
>
> The agent's treasury is a portfolio, like tokenized Nvidia. When it needs to buy something, our router finds the
> cheapest way to pay from what it holds, using True Markets quotes, orders, wallets and transfers. A human approves
> every single order. Policy rules in plain code block anything off the rails, including prompt-injection attacks.
> And every payment leaves a receipt: what was bought, what was sold, and how well it filled.
>
> Built in a day with Grok and Cursor. Sellers in the demo are simulated, and we say so. The money is real.

## Recording the backup video (do this by ~3:30)

1. Reset demo data. Close notifications. Browser full screen (F11), zoom 125%.
2. **Windows:** press **Win + Alt + R** (Xbox Game Bar) to start/stop recording the browser window. Videos land in
   `Videos\Captures`. (Or Win + Shift + S → Record in Snipping Tool.) Use OBS if you want your voice over it.
3. Run the whole script once, talking through it. Don't restart for small stumbles.
4. Watch it back once, then copy it to a USB stick or the team drive so two people have it.
