# Event logs of two Pendle PT markets on Robinhood Chain

Raw material, captured on 2026-10-10 by `code/read_market_logs.py`, archived in the shape
`code/verify_reads.py` checks. **No depth figure is published here and none is implied.**

| market | expiry | logs | blocks with logs | sweep | logs served from |
|---|---|---|---|---|---|
| `0x752057e7a63d0a7f15b740d41ef484fdec459ead` | 2026-10-08 00:00 UTC, expired | 82 | 30 | 0 … 85,130,760 | block 71,414,107 |
| `0x25ee3232421a08f390ef25a34b1d2ccc8394bd05` | 2026-10-22 00:00 UTC, live | 24 | 7 | 0 … 85,130,791 | block 78,144,608 |

Every figure above is read from the two records in this directory. Each record names its own
read list and response archive and carries the digests of both.

## Why these were captured before they were needed

The exit cost on a PT market is a function of the market's state, and on this chain the public
endpoint keeps state for minutes. So a quote for a past moment can only ever be computed from
an archive, and a quote computed that way cannot be checked against what anyone actually paid
unless the trades are also held. These logs are the only surviving record of those trades.
Capturing them is cheap; the alternative is not available later.

They are raw on purpose. Topics and data are archived as the node returned them. Decoding a
log into an amount needs an ABI and a decimals convention, and both are choices that belong in
an analysis where they can be argued with — not in an archive, where they would be
indistinguishable from what the chain said.

## What this establishes, and what it does not

**It establishes that the node still serves logs at the depths in the last column.** Logs came
back from those blocks, so the log index reaches at least that far for these addresses:
13,716,653 blocks back for the expired market, 6,986,183 for the live one.

**It establishes nothing about the ranges that came back empty.** An empty range is equally
consistent with the market not existing yet, with no events in it, and with a node that has
dropped its log index that far back and answers empty rather than erroring. This sweep cannot
tell those apart, and the records say so in their own `coverage_note` rather than leaving the
reader to infer it.

**Depths are in blocks, deliberately.** This chain's block time was measured at about 0.1027
seconds across three independent spans (1,000 / 100,000 / 1,000,000 blocks, agreeing to three
digits). An earlier working note in this project converted depths on this chain at two seconds
per block and was wrong by roughly twenty times. A reader who wants days should divide by a
block time that carries its own measurement, which is why no day figure appears here.

**The sweep is not pinned the way the state captures are.** `eth_getLogs` takes a block range
and cannot be pinned by block hash, so the top of the range is not reorg-proof. Each record
carries the top block's number, hash and timestamp, and `--to-block` reproduces exactly the
same range.

**The per-query block span was measured, not assumed.** The first read in each archive is a
deliberately over-wide query; the node refuses it and names its own limit, and that refusal is
archived as the evidence. If the limit could not be parsed the collector exits 3 rather than
guessing one, because a guessed span silently shortens the sweep and the missing chunk looks
like an absence of events.

## The thing a reader should know before using these for validation

Both markets are nearly inactive. The live market's last event is at block 83,458,608; the
expired market's is at 84,287,536. Neither has a dense trade history, so these logs can
support a check of a quote at a handful of moments and cannot support a distribution. And the
state as it stood at those blocks is already gone from the public endpoint, so validating a
quote against one of these trades means reconstructing the state from events first. That is a
separate piece of work and it has not been done; nothing in this directory should be read as a
validated quote.
