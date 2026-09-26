# Executability — data and verification

Independent measurement of executable depth across on-chain aggregators,
tokenized stocks on Robinhood Chain, and prediction markets.

**Report:** https://dirkdiggler1026.github.io/executability-report/

## Contact

Independent operator, working under a pseudonym. Questions, corrections,
citations, and commissioned work:

```
dirkdiggler871026@gmail.com
```

Corrections get published. The quarantine section below is an example of that.
If you think a figure here is wrong, say so.

**The error archive.** Ten instrument failures over six days are written up on the
report page, numbered, each with what it was and how it was caught — eight caught
before anything was published, two after. Section heading: *"Our instruments lied
to us ten times"*. Two of them (#08, #10) are about the pool table being incomplete
or out of date; see **Limits** below for the cutoff that is still open.

## Commissioned measurement

From October 2026. Two kinds of work, measured the same way as the public
series and delivered with the raw evidence (block height, Quoter returns,
round hash):

1. **Verification report.** A named pool or token, at sizes you pick. What is
   actually executable at one pinned block, checked against a stated claim, a
   diligence question, or a dispute.
2. **Collateral / liquidation-depth review.** For a protocol about to accept
   tokenized stocks (or any token) as collateral. What that collateral can be
   sold for, and at what size, before parameters are set.

Both use public on-chain state, so anyone can replay them. I do not take paid
work on third-party aggregator APIs: those free tiers are licensed for
non-commercial use, and paid work would not be. The public aggregator series in
this report stays non-commercial for the same reason.

The data decides the conclusion. Coverage and scheduling are what you pay for.

## License

- `code/` — Apache License 2.0 (`LICENSE`, which covers `code/` only)
- `data/` — Creative Commons Attribution 4.0 (`data/LICENSE`)
- `index.html`, `index.zh.html` — Creative Commons Attribution 4.0, same terms
  as the data

Attribution is the only condition, for the data and the report alike.

## Contents

```
index.html              the report (English, canonical)
index.zh.html           Chinese snapshot, may lag
now.html                current figures, regenerated daily (make_now.py)
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

**What a round trip cannot see.** Both legs are quoted against the same pinned
block, so the sell leg is priced against the book as it stood *before* the buy,
and the cost is the buy-side cost **plus** the sell-side cost. At block
54,088,399, QQQ at $100,000: 0.133% buy plus 0.131% sell = 0.264% against a
measured round-trip cost of 0.264%. A forced seller walks **one** side, so the
round trip is not that seller's number. This is why a second series measures the
sell side alone (below), and why the field this project proposed to the SEC was
corrected to one-sided depth.

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
hash, and compares it against rounds.jsonl.

That recorded hash has two anchors. The first is git history: rounds.jsonl
ships in this repository next to the data, so recomputing it shows the round
has not been revised without the change appearing in the history. The second
is the on-chain ledger described below, which since 2026-09-19 holds the
hashes of the published rounds through block 64,907,249.

Each record carries a `committed` field, and it reads `false` on every round
ever published. That is not a status: chain state is never written back into
a published file, so the field cannot become `true`. It is a constant, and
the next section says what to ask instead.

The same hashes can also be anchored on-chain, by
[ievidence-ledger](https://github.com/dirkdiggler1026/ievidence-ledger):
`IEvidenceLedger` at `0xc4f7c2ed489d9f521d65b43cc4929d3c642c6fb9` on Robinhood
Chain testnet (chainId 46630). It was deployed on 2026-09-15 and still empty on
2026-09-16 — the film's "the ledger did not exist until the fifteenth" is that
deployment. On 2026-09-19 a backfill landed: 610 rounds in ten transactions, and
`latestCommittedBlock()` has returned 64,907,249 since. Those 610 rounds are
every published round at or below that block; everything else — later rounds,
and the quarantined directories — returns canon 0 ("absent").

Records above read `committed: false` regardless, and will keep doing so.
That field is not a report of the chain — chain state is never written back
into a published data file, so the field is false by construction. To ask
whether a round is anchored, ask the ledger. `code/verify.py` deliberately
does not, and says so.

On 2026-09-23 a second ledger was deployed on Robinhood Chain **mainnet**
(chainId 4663) at `0x7f5446b920e09531f443ce951076cbaed09dfab6`, block
70,145,346, owner `0x6768cEF3…` — a key that has never held the iteration-network
ledger. 850 published rounds through block 69,196,861 were committed in fourteen
transactions. The iteration-network ledger is not superseded: its watermark only
moves forward, so what it holds it keeps holding.

The two anchors are not redundant: git history can be rewritten by whoever
holds the repository, while the ledger can only be appended to.

Run it from the repository root: it looks for data/ next to the script
(or honours RHDEPTH_DATA). Quarantined v1 rounds are excluded by their
canon field and reported as defunct (exit code 2), never as mismatches.

## The pre-registrations, and the second series

Two series run, each with its own pre-registration and its own canon:

| series | canon | cadence | published under |
|---|---|---|---|
| same-pool round trip | `rhdepth-v2` | one round every 30 minutes since 2026-09-04 | `data/` |
| sell side alone | `rhdepth-oneside-v1` | one round every hour since 2026-09-26 00:00 UTC | `data-oneside/` |

The registrations are the `PREREG-*` files in this repository, written **before** the windows they
govern: `PREREG-rtr-recovery-shape-2026-09-22.md` and `PREREG-oneside-depth-2026-09-25.md`, with
their addenda. A registration that is adjusted afterwards to describe what happened is not one, so
deviations are recorded rather than smoothed: `PREREG-oneside-depth-2026-09-25-addendum-3.md`
states that the second series' first four rounds name an enumeration that was never archived, and
that one of its per-round fields changed shape twice inside the window. The affected rounds are
neither withdrawn nor compliant, and the addendum says so.

`data-oneside/` is published by the same daily sync as `data/`, and only for complete days, so the
second series' first day appears with the 2026-09-27 06:01 UTC sync.

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
- **The pool table stops at block 53,983,886** (2026-09-04 04:33:55 UTC,
  about three hours before the first measured round). Pools created after
  that block are not in it. So every figure here means *the best route
  among the pools in this table*, never *the best route on the chain*.
  One affected cell is known and written up as error #10; which others
  are affected is what an incremental scan has yet to establish.
- The pool table is internally consistent (fail-loud scan, zero failed
  ranges) but has **no external cross-check**. DexScreener counts
  uninitialised pools in its liquidity figures and is not used as a
  reference; the block explorer's API is behind anti-bot protection.
- The baseline spans hours, not weeks. It does not extrapolate across
  weekends or earnings windows.
- No dependencies: `code/evm.py` implements keccak-f[1600], static ABI
  encoding and eth_call using only Python 3 and curl.
