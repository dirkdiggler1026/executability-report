# How long the equity feeds on Robinhood Chain went without publishing

Produced by [`code/verify_feed_staleness.py`](../../code/verify_feed_staleness.py) from
`AnswerUpdated` logs on the public endpoint `rpc.mainnet.chain.robinhood.com` — no
account, no key. Re-run it and it recomputes these numbers from the chain.

Measured 2026-10-28, at between forty-five and forty-six million blocks after the fact:

| feed | longest gap | × documented heartbeat | last update (UTC) | resumed (UTC) |
|---|---|---|---|---|
| QQQ | 91.48 h | 3.81 | 2026-09-04 04:31:52 | 2026-09-08 00:00:31 |
| GOOGL | 81.55 h | 3.40 | 2026-09-04 14:27:21 | 2026-09-08 00:00:37 |
| SPY | 80.80 h | 3.37 | 2026-09-04 15:12:39 | 2026-09-08 00:00:51 |
| NVDA | 78.24 h | 3.26 | 2026-09-04 17:46:24 | 2026-09-08 00:00:54 |
| TSLA | 77.77 h | 3.24 | 2026-09-04 18:14:36 | 2026-09-08 00:00:49 |
| GME | 76.82 h | 3.20 | 2026-09-04 19:11:08 | 2026-09-08 00:00:31 |
| AAPL | 76.16 h | 3.17 | 2026-09-04 19:51:26 | 2026-09-08 00:00:54 |

The documented heartbeat is 86,400 s for every one of them. AMC and RDDT have no feed on
this chain at all, which is recorded in [`absent-feeds.json`](absent-feeds.json) rather
than left as a missing file — a measured absence and a forgotten measurement look the same
in a directory listing.

The stops are staggered across fifteen hours. The resumes land within twenty-three seconds
of each other. Nothing reverted: through the gap every call returned a price with a
timestamp that looked valid, and AAPL's held value was 320.51633525 for seventy-six hours.

## Reproduce

```
python3 code/verify_feed_staleness.py --symbol AAPL \
    --from-utc 2026-09-04T12:00:00Z --to-utc 2026-09-08T12:00:00Z
```

Exit 0 measured, 1 a check failed, 3 not exercised. AMC and RDDT exit 3.

## What this does not establish

Each artifact carries the same list under `what_this_does_not_establish`:

- It does not establish that any position was unliquidatable, or that anything was
  liquidated. A feed that has not moved is an input to a decision, not the decision.
- It does not establish that the published answer was wrong. Only that it did not change.
- It says nothing about a feed the run did not query.

## Why events rather than state

The public endpoint on this chain prunes state within roughly ten to fourteen minutes
(measured in [`../rh-retention/`](../rh-retention/)), so `latestRoundData()` cannot answer
a question about September. Logs are a different retention class on the same endpoint and
are served tens of millions of blocks back, measured by rows actually returned.

That asymmetry is the reason this directory exists at all. On this chain a figure can be
computable at the head and still not be verifiable afterwards, and the depth figures this
project publishes are the second kind — they had to be captured at the time or they are
gone. The feed gaps are the first kind. Anyone can still check them, including after this
archive stops being added to.

## Three controls, and the one that was added after being needed

**Contiguous roundIds.** A log query can return fewer rows than exist; this endpoint caps
a response at ten thousand matched rows and a span at ten million blocks. An interval
measured across a hole in the data is a fabrication, so the recovered roundIds must form
an unbroken run or the script exits 3.

**The window edge.** A statistic taken *between* returned rows cannot see a gap that
straddles the start of the window. The first version of this script took the worst gap
between returned rows. For QQQ the first returned row was the instant every feed resumed,
so the days of silence before it sat outside the row set entirely, and QQQ — the worst
feed of the seven — printed as 3.48 h instead of 91.48 h. The window is now extended
backwards until an update precedes it, the straddling gap is flagged in the artifact as
`spans_requested_window_start`, and the script refuses rather than reporting the largest
gap it happens to see.

It was caught by a disagreement, not by a test: six feeds agreed with an earlier bisection
of AAPL's gap and one did not, and the one that did not was the one whose gap began before
the window. Same family as most of the entries in this project's error archive — a
statistic pointed at a set that did not contain the thing being measured.

**The sequencer.** A halt produces an identical-looking gap, so the block rate across the
gap is measured and reported. Every artifact here records
`the chain produced blocks throughout`; had it not, the verdict would say so rather than
the number standing alone.
