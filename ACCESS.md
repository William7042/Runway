# True Markets access — Person A

Checked 2026-10-24 against production using the supplied organization API key and existing `test` signer. Keys and account snapshots are ignored, permission 0600, and never printed.

## Immediate team handoff

- **Commerce allowlist: USDC, PYUSD, SOL, BTC, and ETH.** Exact IDs and networks come from the live catalog. Off-chain BTC/ETH entries are not verified on-chain payment routes.
- 209 catalog entries are marked tradeable. Catalog visibility is not proof that this user can trade a pair. The complete public catalog is saved locally under ignored `.runway/gateway_access.json`.
- Existing `test` user resolves successfully and has Solana + EVM wallets. Gateway balances show **50 PYUSD on Solana**. Runway defaults to a **$1 cap** and **DRY_RUN=1**.
- Python SDK `truemarkets==0.3.0` installs, but organization auth returns no refresh token and the generated parser raises `KeyError`. `RunwayClient` handles organization authentication without a refresh token and uses the SDK authenticated HTTP transport for current endpoints.
- Organization calls require `TM-On-Behalf-Of: user_id`; the signer key is separate from the organization authentication key.
- Gateway `/v1/gateway/assets` and `/balances` work. Legacy SDK `defi.get_assets` and watchlist routes return 404. Profile/history work with the user header. Do not infer unavailable watchlists are empty.
- `gateway.compute_quote` is CeFi-only in current docs. DeFi requires an unsigned quote/preparation operation. No signed execution has been performed yet.

## Integration (shared contract unchanged)

```python
from runway_money import propose_payment, execute
p = propose_payment('buyer-id', 'seller-id', 1, 'Purchase research', 'user message')
# Person C records a real human approve/reject decision in the queue.
r = execute(p['id'])
```

`RUNWAY_MODE=stub` (default) returns canned ETH proposals and labeled simulated fills; `tx_hash` is null. The stub still requires approval. Queue URL defaults to http://localhost:8000. No money-layer code approves proposals.

## Sources

- https://docs.truemarkets.co/gateway/requests-and-signing/
- https://docs.truemarkets.co/gateway/create-a-user/
- https://docs.truemarkets.co/api/gateway/compute-quote/

This is a technical demo, not financial advice. Live $1 acceptance remains pending a successful quote, human approval of a concrete proposal, and confirmed execution with a real transaction hash.

## Quote and recipient update

The unsigned $1 SOL buy quote succeeded: `qty_out=0.01007997`, fee `0.002` USDC, no issues. The API returned USDC as settlement even when PYUSD was requested, plus an inventory bridge payload. **SOL/USDC is quoteable; PYUSD/SOL must not be presented as a direct verified pair.** No fill or executable pair has been confirmed by a signed run.

Existing `test2` resolves to its own Solana and EVM wallets. The pending $1 payment preview uses pay-in-kind PYUSD to test2. The queue at localhost:8000 refused connections on both checks, so no proposal has been approved and no live receipt exists.

## Catalog snapshot

These are catalog entries marked tradeable, grouped by chain/venue. They are **not a claim of this user's execution eligibility**. Stablecoins used for transfers can be catalogued as non-tradeable.

- **base / defi (73)**: AAVE, AEON, AERO, AIXBT, AVNT, AXL, B3, BNKR, BRETT, CAKE, CBBTC, CBETH, CBHYPE, CBZEC, CHECK, CHIP, CLANKER, COMP, COOKIE, COW, CTR, DEGEN, DEUS, DIEM, DINO, DRV, EDGE, ELSA, ETH, FLUID, FUN, GITLAWB, HOME, HYPER, ICNT, ICP, KAITO, KAT, KTA, LMTS, MOG, MORPHO, NOCK, OPG, PENDLE, PLAY, POD, PRIME, RAVE, RECALL, REI, REPPO, RIVER, RSC, RSR, SAND, SAPIEN, SIGN, SNX, SUPER, SUSHI, TEL, TIBBIR, TIG, TOSHI, TOWNS, UP, VVV, WCT, WMTX, ZEN, ZORA, ZRO.
- **hypercore-spot / defi (3)**: KNTQ, ONEAR, PURR.
- **off-chain / cefi (2)**: BTC, ETH.
- **robinhood / defi (19)**: AI, ANSEMCAT, ARROW, CASHCAT, GTR, IF, INDEX, JUGGERNAUT, KARMA, KITSU, PIPEDOG, PONS, STONKBROKER, SWOGE, TENDIES, VEX, WISHBONE, WOOD, YOLO.
- **solana / defi (112)**: 2Z, A47, AI16Z, ALCH, ALON, ANON, ANSEM, ARC, ASTEROID, AURA, AVA, BABYDOGE, BAN, BERT, BIRB, BOME, BONK, BORG, BP, CARDS, CHILLGUY, CHILLHOUSE, COLLAT, CORAL, CPOOL, CUDIS, DADDY, DEGENAI, DOOD, DRIFT, DUPE, FARTCOIN, FO, FWOG, GIGA, GMT, GOAT, GOHOME, GP, GRASS, GRIFFAIN, HNT, HOUSE, HUMA, HYPE, IKUN, IO, JELLYJELLY, JLP, JTO, JUP, KMNO, KOKOK, KORI, LAYER, LOL, ME, MELANIA, MEOW, MET, MEW, MICHI, MON, MOODENG, MORI, MUMU, NOBODY, NOS, ORCA, PENGU, PENGUIN, PIPPIN, PNUT, POLIS, PONKE, POPCAT, PUMP, PYTH, PYTHIA, RAY, REKT, RENDER, RETARDIO, RETIRE, SHDW, SIGMA, SKR, SLERF, SOL, SPX, STARTUP, SWARMS, TAI, TITCOIN, TNSR, TROLL, TRUMP, UFD, URANUS, USA, USDUC, USELESS, VERSE, VINE, VIRTUAL, W, WEN, WIF, WLFI, WOULD, ZBCN, ZEREBRO.

## Confirmed live result and execution hold

The agent/product work was fetched from origin/main at c290847. Person C's real queue was started with STUB_EXECUTOR=0. After the human authorized a $5 cap and approved the concrete proposal in the dashboard, dry-run succeeded and a real 5 PYUSD transfer confirmed. Actual balances are test=45 PYUSD, test2=4 PYUSD. RPC audit shows 1 PYUSD went to a separate wallet; the network fee was 0.00001 SOL. Preparation had incorrectly reported zero fee. See RECONCILIATION.md. Further execution is held. No swap/order has been executed.

## Real swap/order access verified

- PYUSD/USDC: the legacy DeFi quote/trade endpoint accepts a 2 PYUSD sell as one unsigned transaction, despite PYUSD not being an orderable Gateway asset. A $1 quote was below minimum. Approved execution spent 2 PYUSD and returned 1.996651 USDC (chain-audited).
- SOL/USDC: funded USDC removes the bridge. Gateway created a single-payload SOL order; human-approved execution spent 1 USDC and returned 0.00945721 SOL (chain-audited). The receipt is executed with hash 5QFRqXWGZ1EXLngMqreRifvpBxpT14BgcUKMPdRTJrXCHaf5fgWBRVzXS9AaVonfu8Wb5GVoca4zqLHCh3B8pRck.
- Raw quotes overstated net SOL receipts; unsigned simulation exposed the difference. The human authorized a one-off cost allowance up to $0.07 before approving this order. Normal limits stay unchanged. Other payment routes still require verification.

## Transfer-fee investigation

Unsigned PYUSD/Solana probes at gross 5, 6, and 10 all encode a 1 PYUSD fee (seller receives 4, 5, and 9). API create/GET fee and received remain zero while awaiting signature. Preview pricing now uses simulated wallet changes and flags invoice underpayment before enqueue. See TRANSFER_FEES.md; no funds moved during this investigation. Transfer hold and normal fee/spend limits remain unchanged.
