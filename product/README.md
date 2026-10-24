# Runway · product layer (Person C)

Everything in `product/` belongs to the product layer: the **approval queue service** and the **web UI**.
Nothing here signs or sends money. Money only moves in Person A's `execute()`.

```
product/
  queue_service/   FastAPI approval queue, JSON-file store (port 8000)
  frontend/        Vite + React UI (port 5173)
  DEMO_SCRIPT.md   2-minute demo, 60-second pitch, backup-video steps
```

## Run it (Windows)

**1. Approval queue** (terminal 1)

```powershell
cd product\queue_service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Check it: open http://localhost:8000/docs (interactive API docs) or http://localhost:8000/proposals.
On first run it creates `queue_service/data/store.json` with 3 seeded proposals, 1 bounty and 2 wallets.

**2. UI** (terminal 2; needs Node 18+, check with `node -v`, install from nodejs.org if missing)

```powershell
cd product\frontend
npm install
npm run dev
```

Open http://localhost:5173.

**Teammates on the same Wi-Fi** use `http://<your-laptop-IP>:8000` (find it with `ipconfig`, the IPv4 address).
To point the UI at someone else's queue, create `frontend/.env.local` with `VITE_API_URL=http://<ip>:8000`.

## Stub router

Until Person A's router is live, the queue runs a **stub executor**: about 2 seconds after you approve a proposal it
writes a fake receipt (tx hash starts with `STUB-`, shown with a "stub" badge). This is what lets the UI demo work end to end
with canned data.

**When Person A's `execute()` is ready, start the queue with the stub off:**

```powershell
$env:STUB_EXECUTOR="0"; uvicorn app:app --host 0.0.0.0 --port 8000
```

## Contract (shared with A and B, unchanged)

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/proposals` | Proposal JSON | Always created as `pending`. Generates `id` if missing. |
| GET | `/proposals?status=` | | Newest first. `status` optional. |
| POST | `/proposals/{id}/decision` | `{"decision": "approve"\|"reject", "reason": str}` | Only from `pending`. 409 otherwise. |
| POST | `/proposals/{id}/receipt` | `{quote, fill, tx_hash, status}` | **409 unless status is `approved`.** `status` is `executed` or `failed`. |

Path steps: `{"type": "swap", "asset": <what is SOLD>, "amount": n}` and `{"type": "transfer", "asset": <what is PAID>, "amount": n}`.
The UI reads "Sells" from swap steps and "Pays" from transfer steps. Extra fields (e.g. `to_asset` on a swap) are allowed and displayed.

### Conventions the UI understands (please follow these, A and B)

- **flags** are strings with a prefix. The UI colours them by prefix:
  - `POLICY_BLOCK: ...` → **the queue rejects the proposal on arrival** (status `rejected`, `blocked: true`, decision by `policy`).
    It can never be approved, and the UI shows it as a big red "Blocked by policy" card. This is how the attack demo works.
  - `INJECTION: ...` → red. `VERIFIER: ...` → amber warning on the approval card (does not block). Anything else → amber.
- **drift**: `{"onchain_price": n, "reference_price": n, "gap_pct": n}` (or just a number = gap %), `null` when no tokenized stock.
- **expected_cost**: `{"price_impact_usd": n, "fees_usd": n, "total_usd": n}` or a plain number (USD).
- **source**: `{"kind": "user_message"|"agent_plan"|"fetched_page"|"seller_response", "text": str, "url"?: str, "injected_excerpt"?: str}`.
  For the attack, put the hidden instruction in `injected_excerpt` and the UI highlights it inside `text`.
- **receipt quote / fill**: objects with `cost_usd` (and `amount_usd`) so the UI can show quote vs fill. A plain number also works.

## Product-layer extensions (additive)

| Method | Path | Who uses it |
|---|---|---|
| GET | `/config` → `{drift_pct, drift_threshold_pct, dry_run}` | **Person A reads `drift_pct` here** for the simulated drift. The UI slider writes it. |
| PUT | `/config` | UI slider |
| GET | `/balances` | UI wallets panel |
| PUT | `/balances/{agent}` `{label, treasury_mode, cost_basis_usd, assets:[{asset, amount, usd_value}]}` | **Person A pushes real balances** after each fill |
| GET/POST | `/bounties` | Bounty board |
| POST | `/bounties/{id}/claim` `{claimant}` · `/submit` `{submission}` · `/verify` `{decision, reason}` | Bounty board; Person B's worker agents can call these too |
| GET | `/receipts` | Receipts feed / ledger |
| POST | `/demo/attack` | Injects the canned injection proposal (B's attack script can POST its own instead) |
| POST | `/demo/reset` | Back to seeded data before each run |

**Bounties never pay on their own.** Posting a bounty creates a funding proposal. Approving submitted work creates a payout
proposal; rejecting it creates a refund proposal. Each goes through the same approval desk, and the bounty moves to
`paid` / `refunded` only when that proposal's receipt comes back `executed`. These proposals carry `bounty_id` and
`bounty_role` (`funding` | `payout` | `refund`); Person A should route them like any other transfer from the escrow wallet.

## Safety notes

- No auto-approve, no "approve all". The decision endpoint takes one proposal at a time.
- Blocked proposals are rejected server-side, so even a buggy UI can't approve them.
- `store.json` is demo data and is git-ignored. No keys live in this folder.
- Technical demo, not financial advice.
