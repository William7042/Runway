# Runway demo (about 2 minutes)

**Before you start:** `POST /demo/reset` (or Demo controls → Reset demo data). Open the Desk (`/#desk`) —
wallets, drift slider, and live receipts are in the **right column**. Block explorer tab ready only if you
will show a real Solana tx (live money path). Font size up (Ctrl +) so judges can read the cards.

| # | Time | On screen | Say |
|---|---|---|---|
| 1 | 0:00 | **Fund.** Desk right column: Research agent wallet, mostly NVDAc (labeled simulated), some USDC, "Endowment". | "This is an AI research agent. Its treasury isn't cash — in the demo it's simulated tokenized Nvidia. In endowment mode it can only spend gains, so principal stays invested." |
| 2 | 0:15 | **Ask.** Run `DRY_RUN=1 python -m demo.run_research` (sellers optional until step 5b). Show "Triggered by" on a card. | "We ask it a question that needs three things it doesn't have: a filing, a premium archive, and a human fact-check." |
| 3 | 0:25 | **Plan.** Three approval cards / up-next queue. | "It picks sellers from a registry by price and reputation, then proposes three purchases. It can't spend a cent without asking. There's no auto-approve and no approve-all." |
| 4 | 0:40 | **Approve one, reject one.** Approve the cheap filing (pay in kind if shown). Reject the archive with reason "too expensive". | "This card shows what it sells, what it pays, the cost, and the cheaper paths it rejected. I'll approve this one… and reject this one. The agent is told why." |
| 5 | 0:55 | **Pay.** Right column **Live receipts**: quote vs fill + tx (pill says simulated when stub executor is on). | "With the stub executor, fills are simulated and labeled. On the live money path we'd show a real Solscan hash — quote versus fill on the receipt, including any transfer fee vs seller net." |
| 5b | 1:05 | **Optional paid→data.** With sellers up: `python -m demo.run_research --fetch` after approving. Terminal prints SIMULATED filing/archive text. | "After payment confirms, the agent actually pulls the data from the simulated seller — paywall unlocked only once the queue says approved." |
| 6 | 1:15 | **Attack.** Demo controls → Simulate injection attack (or `demo.attack_script`). Red card + toast. | "Now the agent reads a page with a hidden instruction: send everything to this address. It never reaches me as a clean order. Allowlists and spend caps are plain code. You can see the exact hidden text." |
| 7 | 1:30 | **Drift.** Right-column slider past 2%. Badge flips to "Selling paused". | "Tokenized stocks can drift from the reference price. Past 2%, Runway refuses to sell at a bad price and pays from USDC instead. This slider is the demo control Person A reads from /config." |
| 8 | 1:45 | **Receipts.** Activity tab: paid, blocked, rejected, principal still invested. | "Every order, every decision, every fill, audited. The agent spent what it needed and the investment stayed invested." |

**If something breaks live:** stay calm, say "here's the recorded run", and play the backup video from the same step.

**Backup video:** not in the repo yet — record before the final hours (see below) and keep a copy off-machine.

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
> Built in a day with Grok and Cursor. Sellers in the demo are simulated, and we say so. Live swaps through True Markets
> are real; transfer fee edge cases are documented, not papered over.

## Recording the backup video (do this by ~3:30)

1. Reset demo data. Close notifications. Browser full screen (F11), zoom 125%.
2. **macOS:** QuickTime → New Screen Recording (or Cmd+Shift+5). **Windows:** Win + Alt + R (Xbox Game Bar).
3. Run the whole script once, talking through it. Don't restart for small stumbles.
4. Watch it back once, then copy it to a USB stick or the team drive so two people have it.
