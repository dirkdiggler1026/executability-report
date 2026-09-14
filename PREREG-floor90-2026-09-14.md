# Pre-registration: absolute floor trigger for the five stable names

**Registered 2026-09-14 UTC. Forward evaluation starts 2026-09-15 00:00 UTC.**

This document fixes a detection rule before it is evaluated. Everything below was written
while looking at data through 2026-09-14; nothing after that date had been seen. The rule is
therefore **calibrated, not tested** — its behaviour on the calibration window says only that
it does not fire there, which is how it was chosen. Whether it is any good is a question the
forward window answers, and only the forward window.

## The rule

For each of the 20 cells below, at each round:

    trigger  <=>  same-pool round-trip recovery < 90.0000 %

- No persistence requirement. One round below the floor is a trigger.
- `no_liquidity` counts as a trigger (the round trip did not close).
- An **episode** is a run of consecutive triggering rounds **within one cell**. Episodes are
  per cell, never merged across cells: two cells triggering in the same round are two
  episodes. Reports also carry the number of distinct rounds with at least one trigger, so
  "how many cells" and "how long" are never read off the same number.
- Each episode is reported with first block, last block, round count, and minimum recovery.

## The cells

Five names that never went below 92.7998% in the calibration window, at all four sizes:

    SPY, AAPL, GOOGL, NVDA, TSLA  x  $100, $1,000, $10,000, $100,000

QQQ, RDDT, GME and AMC are **excluded by design**. Under the same floor they produce 3,053
triggers in the calibration window out of 7,456 cell-rounds. A rule that fires on them is not
detecting anything; their condition is the standing state, and it is reported by the
round-trip share table instead.

## Why 90%

Calibration window: blocks 54,088,399 to 62,352,664, 466 rounds, 2026-09-04 to 2026-09-13 UTC,
9,320 cell-rounds across the 20 cells.

    lowest recovery observed in any of the 20 cells   92.7998 %   (TSLA, $100,000)
    second-lowest cell minimum                        96.2503 %   (NVDA, $100,000)
    upper edge of the collapse band                 < 50      %
    floor                                             90.0000 %

The floor sits 2.80 points below everything observed. **Its own distance to the collapse band
is 40.0 points** (90 − 50), which is the gap it selects a side of; the 42.8 points between the
observed minimum and the band belong to the minimum, not to the floor.

The stronger support is that the tail is one cell thick, not that the floor has 2.8 points of
clearance. Of 9,320 cell-rounds: 24 below 96.25%, 13 below 95%, 3 below 94%, none below 92.8%,
none below 90%. Nineteen of the twenty cells never went below 96.2503%. Below 90% is not
"slightly worse than observed" for nineteen of them; it is a different order of magnitude.

**What 9.7 days cannot settle:** this window cannot distinguish "90% is outside normal
variation for these names" from "90% was not reached in 9.7 days". The floor is a reasonable
line, not a demonstrated one. **The falsification conditions below carry the weight, not the
floor.**

The floor has no other parameter. It is not tuned to a distribution.

## The gap at 2026-09-14

Calibration ends 2026-09-13; forward evaluation starts 2026-09-15. **2026-09-14 belongs to
neither window, deliberately**: it is the day this document was written, so its data had been
seen and cannot serve as a forward test, and including it in calibration after the fact would
move the window to fit the rule. Anyone counting days will find it missing; it is missing on
purpose, and this paragraph is why there is no silent hole.

## What the forward window reports

Each calendar month from 2026-09-15:

1. Episodes, in full, with blocks and minima. **Zero episodes is a result and gets reported.**
2. Cell-rounds evaluated, so the trigger rate has a denominator.
3. Distinct rounds carrying at least one trigger.
4. Any round that could not be evaluated, and why.

## What would make this rule wrong

- **It fires often.** More than one episode per month averaged over three months means 90% is
  inside normal variation for these names, not outside it, and the floor was set on too short
  a window.
- **It never fires while one of these names degrades.** Concretely: any cell whose 30-day
  rolling median falls more than 2.00 points below its calibration-window median while no
  round in that cell ever crosses 90%. That is a measurable condition, not a judgement call —
  a falsification test that needs someone to decide what "degrades" means would hand the
  choice of definition back to the moment of the result, which is what this document exists
  to prevent.
- **It fires on measurement rather than market.** Any episode traced to an endpoint or
  collector fault is a fault in the instrument, reported as one, not as a finding.

## What this rule does not do

It does not predict. It does not say a holder can or cannot exit. It reports that a same-pool
round trip that had closed above 92.8% in every one of 9,320 prior measurements closed below
90% — nothing more, and the report will say nothing more.

## Fixing this document

Changing the floor, the cell set, the episode definition, or any falsification threshold ends
this registration and starts a new one with a new date. This file is never edited. Its git
commit timestamp is the evidence that it predates the window it is evaluated on.
