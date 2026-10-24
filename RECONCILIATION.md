# Real transfer — requires reconciliation

On 2026-10-24 a human approved proposal `b5d71b4e-5124-4e62-a182-329850289752` in Person C's queue after a successful dry run. The approved action was 5 PYUSD from `test` to `test2` on Solana, with a prepared fee of zero. The human explicitly raised the demo cap from $1 to $5 because the API rejected unsigned preparations of 1 and 2 PYUSD as `amount_below_minimum`; unsigned preparation of 5 succeeded.

The transaction confirmed, but actual settlement was:

| Item | Prepared / approved | Confirmed |
| --- | --- | --- |
| Sent | 5 PYUSD | 5 PYUSD |
| Fee | 0 PYUSD | 1 PYUSD |
| Net receipt | 5 PYUSD expected | 4 PYUSD |

[Solscan transaction](https://solscan.io/tx/5ypu1ajwp95Yj8QjJ5sASqVUhBTg5W6SymTmuvNyj6tSF5RD6LgoU2Cd5dcYaTMtJmaArF3XFfNtARVEuPm6ASk8)

The first receipt was posted as `executed` when chain confirmation arrived, before the initial implementation compared the net received amount. The raw receipt contains the actual fee and net receipt. **Chain execution succeeded, but the invoice was underpaid.** Person C's current contract prohibits changing a terminal receipt; the original is retained and this correction is recorded separately rather than rewriting history.

The money router now checks sent amount, net received amount and actual fee before classifying a new receipt. A short payment or unquoted fee produces a failed receipt with the real transaction hash and reconciliation evidence, and persists a hold on further live execution. A regression test covers this behavior. The hold has also been persisted for this real incident under ignored `.runway/plans/`.

No second payment, compensating transfer, swap or retry has been authorized or sent. Do not remove the hold until the vendor's transfer fee calculation is understood and the full cost/net amount can be reviewed before approval. A future UI update should display this reconciliation on the existing receipt.

This proves human approval → local signature → confirmed transfer → receipt. It does **not** prove the separate quote → order → swap execution path, nor successful full invoice payment. The original $1 acceptance criterion was impossible on the tested PYUSD transfer sizes and remains unmet as written.

## Independent Solana RPC audit

`getTransaction` confirmed no chain error, network fee 10,000 lamports (0.00001 SOL), and these PYUSD owner deltas:

- test (`GE8k4xhSUDpHWf2Df1XgXhF766ZQzLC8hJRjkiZsKsxe`): -5
- test2 (`28ecgfvBFGbd9Ah7pvfpawV4tCJn5ifEHvtWmaTAippp`): +4
- separate wallet (`DmVApZ3sSbAdm9mqoMnGxH5RpBHRtEDAZLvKSt9k5MhW`): +1

The transaction contains separate SPL token transfer instructions for 1 and 4 PYUSD. This confirms an application-level fee transfer; ownership of the fee wallet was not independently established. The missing pre-sign guard was decoding and checking these instructions rather than trusting the preparation response's zero fee. Keep execution held until that guard exists and vendor fee behavior is clarified.
