# Transfer-fee investigation — 2026-10-24

No funds were signed, submitted, or moved during this investigation. Three unsigned preparations and independent Solana simulations tested the existing `test` → `test2` PYUSD/Solana route.

| Requested gross debit | Simulated seller credit | Simulated fee | API create fee | API GET fee |
| --- | --- | --- | --- | --- |
| 5 PYUSD | 4 PYUSD | 1 PYUSD | 0 | 0 |
| 6 PYUSD | 5 PYUSD | 1 PYUSD | 0 | 0 |
| 10 PYUSD | 9 PYUSD | 1 PYUSD | 0 | 0 |

All API responses remained `awaiting_signature` with `sent=0` and `received=0`. The unsigned transaction already contains a separate 1 PYUSD credit to wallet `DmVApZ3sSbAdm9mqoMnGxH5RpBHRtEDAZLvKSt9k5MhW`. This matches the earlier confirmed transaction. Wallet ownership has not been independently established. These observations establish a fixed fee for these tested sizes on this route, not a universal fee schedule for all assets/accounts.

The simulated network charge was 10,000 lamports (0.00001 SOL), paid outside the buyer wallet; the buyer's native SOL delta was zero. The 1 PYUSD is an application-level token transfer, separate from the Solana network fee.

## Root cause and correction

The money layer incorrectly treated the preparation response's zero `fee` as a binding fee quote. The documentation describes a transfer record and its status, not a reliable pre-execution fee estimate. We cannot determine from public documentation whether the zero values are intentional pending-record placeholders or a server defect. Both create and GET demonstrably fail to expose the actual fee before signing on this route.

`TrueMarketsBackend.preview_transfer` now uses simulated sender/recipient balance changes to populate `sent`, `received`, and `fee`. It retains the API values separately as `api_reported_fee` and `api_reported_received`, labels `fee_source=unsigned_solana_simulation`, and excludes signing payloads. The router rejects a path that underpays the invoice and explains the required fee/gross-up instead of presenting it as free. Regression coverage checks API fee=0 against an actual simulated fee=1.

A seller needing 5 PYUSD would require a 6 PYUSD gross transfer under the tested behavior. That exceeds the present $5 demo cap and $0.01 normal cost budget. Raising those limits, paying the fee, or sending a compensating transfer has **not** been authorized. The existing transfer hold remains. No automatic workaround or compensation is attempted.

The signing path also checks exact sender debits and recipient credits on a fresh simulation. A future fee-aware gross-up proposal can disclose gross debit, seller net, and fee together for human approval, but must respect an explicitly authorized total-spend cap and fee budget.

## Reproduce without moving funds

```sh
PYTHONPATH=. .venv/bin/python scripts/investigate_transfer_fees.py
```

This script contains no signing or execute calls. Detailed unsigned probe results remain private under ignored `.runway/transfer-fee-investigation.json`.

References: [Gateway send-funds guide](https://docs.truemarkets.co/gateway/send-funds/), [transfer-record schema](https://docs.truemarkets.co/api/gateway/get-transfer/), [Solana simulation API](https://solana.com/docs/rpc/http/simulatetransaction).
