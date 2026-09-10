# Executability — data and verification

Independent measurement of executable depth across on-chain aggregators,
tokenized stocks on Robinhood Chain, and prediction markets.

**Report:** https://dirkdiggler1026.github.io/executability-report/

## Contact

Independent, pseudonymous operator. Questions, corrections, citations, or a
commissioned measurement:

```
dirkdiggler871026@gmail.com
```

Corrections are welcome and are published — the quarantine section below is the
point, not an embarrassment. If you think a figure here is wrong, say so.

## Commissioned measurement

Available from October 2026. Two shapes, both measured exactly like the public
series, both delivered with replayable evidence (block height, raw Quoter
returns, round hash):

1. **Verification report** — a named pool, token or venue, at sizes you choose:
   what is actually executable at a pinned block, against a stated source of
   truth (a claim, a diligence question, a dispute).
2. **Collateral / liquidation-depth review** — for a protocol about to accept
   tokenized stocks (or any token) as collateral: what that collateral can
   actually be sold for, and at what size, measured before you set parameters.

Conclusions are produced by the data, not by the payer. Coverage and scheduling
are for sale; conclusions are not, and the paying party cannot change what the
measurement finds.

## License

- `code/` — Apache License 2.0 (see `LICENSE`)
- `data/` — Creative Commons Attribution 4.0 (see `data/LICENSE`)

Attribution is the only condition on the data, and being the citable source is
the point.

## Contents

```
index.html              the report (English, canonical)
index.zh.html           Chinese snapshot, may lag
data/                   raw measurements
  <date>/
    quotes.jsonl.gz       one row per measurement
    rounds.jsonl          canonical hash per round
    MANIFEST.sha256       checksums
  snapshot-v18-12r/        frozen 12-round snapshot referenced by the report
  <date>.rhdepth-v1-defective/   quarantined, see below
code/
  collect.py            the collector
  build_pool_table.py   reproduces the pool selection
  verify.py             independent verification
  rhchain.py evm.py     chain access, zero dependencies
  stock_pools.json      the pool table in use
```

## What is measured

For each tokenized stock, at four notional sizes, at a single pinned
block height: **buy in one pool with USDG, then sell the entire position
back through that same pool.** The figure reported is how much of the
notional comes back.

The round trip is deliberately closed inside one pool. An earlier version
took the best buy pool and the best sell pool separately and derived a
rate between them; that rate belongs to no actual pool and produced
recovery figures above 100%, which cannot persist. A same-pool round trip
needs no rate assumption and carries its own sanity check: it must be
≤ 100%, and the shortfall is fees plus price impact.

## Which pools

Pool selection is part of the conclusion, so it is reproducible:

```bash
python3 code/build_pool_table.py --top 8 --probe 10000 > stock_pools.json
```

1. Full-chain scan of Uniswap V4 `Initialize` events, keeping pools that
   pair a stock token with USDG and were actually initialised. **Any
   failed block range aborts the run** — a partial pool table silently
   produces "this token cannot be sold" for tokens whose real pools were
   never scanned.
2. Probe every candidate with a $10,000 buy; drop what cannot fill it.
   Keep the N that return the most.

Ranking is by realised output, not by fee tier, pool count or TVL. Pool
count is actively misleading here: AMC has the most pools of any token
and among the fewest usable ones.

## Verify it yourself

Requires an archive node for Robinhood Chain (historical `eth_call`;
public endpoints usually retain only ~128 blocks of state):

```bash
export RHCHAIN_RPC="https://<your archive endpoint>"
python3 code/verify.py <block>
python3 code/verify.py --latest
```

The script replays every round-trip at that block height, recomputes the
hash, and compares it against ounds.jsonl.

Run it from the repository root: it looks for data/ next to the script
(or honours RHDEPTH_DATA). Quarantined v1 rounds are excluded by their
canon field and reported as defunct (exit code 2), never as mismatches.

## Canonical preimage `rhdepth-v2`

Only fields a third party can reproduce exactly at the same block:

```
per line: block|sell_sym|side|size_usd|route
          |amount_in_raw|mid_amount_raw|amount_out_raw|status
integers as decimal strings (uint256 exceeds JS safe-integer range)
lines sorted lexicographically, joined with \n,
prefixed with "rhdepth-v2" on its own line, then keccak256
```

`side` is always `roundtrip`. `mid_amount_raw` is the token amount
received at the midpoint; without it a third party could check inputs and
outputs but not which pool the middle leg went through.

Timestamps, network latency and all derived floats are excluded. They
cannot be reproduced across runs or languages, and including them would
silently break the claim that anyone can recompute and check.

Integrity check:

```bash
cd data/<date> && sha256sum -c MANIFEST.sha256
```

## Quarantined data

Three directories are kept but excluded from every conclusion. They are
not deleted: removing a superseded version would make every other claim
harder to check, not easier.

| directory | rounds | size | defect |
|---|---|---|---|
| `2026-09-03.pre-pinned-block` | 2 | 44K | not block-pinned, and v1 (broken pool table) |
| `2026-09-03.rhdepth-v1-defective` | 14 | 64K | v1: incomplete pool table + cross-pool rate |
| `2026-09-04.rhdepth-v1-defective` | 15 | 68K | v1: incomplete pool table + cross-pool rate |

The `.pre-pinned-block` set has both defects: calls in a round were not
pinned to one block height, and it was also collected on the broken pool
table (canon `rhdepth-v1`), so neither the recorded block nor the pools
hold. The `rhdepth-v1-defective` sets were collected against an
incomplete pool table (55 pools where the chain has 25,122) with the
cross-pool rate derivation described above. **They produced published
conclusions that were wrong**; those are corrected in the current report.

These three directories are shipped once, by hand, and never touched by
the daily sync (which only pushes strict `YYYY-MM-DD` directories).
`verify.py` excludes them by the `canon` field in each record, not by
directory name.

## Limits

- Quotes come from simulated Quoter calls, not executed trades. Real
  execution is affected by MEV, slippage protection and gas, and is
  generally worse.
- USDG-quoted pools only. ETH/WETH pools are not included; TSLA is known
  to have additional depth in an ETH pool, and other tokens may too.
- The pool table is internally consistent (fail-loud scan, zero failed
  ranges) but has **no external cross-check**. DexScreener counts
  uninitialised pools in its liquidity figures and is not used as a
  reference; the block explorer's API is behind anti-bot protection.
- The baseline spans hours, not weeks. It does not extrapolate across
  weekends or earnings windows.
- No dependencies: `code/evm.py` implements keccak-f[1600], static ABI
  encoding and eth_call using only Python 3 and curl.
