# Executability — data and verification

Independent measurement of executable depth across on-chain aggregators,
tokenized stocks on Robinhood Chain, and prediction markets.

**Report:** https://dirkdiggler1026.github.io/executability-report/

## Contents

```
index.html              the report (English, canonical)
index.zh.html           Chinese snapshot, may lag
data/                   raw measurements
  <date>/
    quotes.jsonl.gz       one row per measurement
    rounds.jsonl          canonical hash per round
    MANIFEST.sha256       checksums
  <date>.rhdepth-v2-defective/   quarantined, see below
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
hash, and compares it against `rounds.jsonl`.

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

Directories suffixed `.rhdepth-v2-defective` and `.pre-pinned-block` are
kept but excluded from every conclusion:

- `.pre-pinned-block` — quote calls in a round were not pinned to one
  block height, so the recorded block does not match the state the data
  came from.
- `.rhdepth-v2-defective` — collected against an incomplete pool table
  (55 pools where the chain has 25,122) and with the cross-pool rate
  derivation described above. **This produced published conclusions that
  were wrong**; they are corrected in the current report.

They are not deleted. Removing a superseded version would make every
other claim harder to check, not easier.

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
