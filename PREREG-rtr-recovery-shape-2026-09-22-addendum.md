# Addendum 1 to PREREG-rtr-recovery-shape-2026-09-22

**Computed 2026-09-22 UTC. This is calibration, not test.**

The classification below was computed on the calibration window, after the boundaries in the
registration were fixed. It is therefore **not a test of them** — it shows only that the
boundaries do not produce an absurd partition of the data they were written against. The
forward window in §6 of the registration is what tests them.

It is published anyway, because withholding a calibration result while citing the window it
came from would be worse. It carries no weight in §7's falsification conditions.

## Window and statistic

Single window: **from 2026-09-15**. Single statistic throughout: **median**. **One row per
ladder** — one token's four cells at one block — because a ladder is `Recovery shape`'s unit.
The `state` column classifies a ladder; it does not classify a cell, and no cell carries one.

One consequence of a single statistic, stated because an earlier draft of this table did not
have it: a table that mixes minima and medians can carry two different classifications for the
same token without anything on the page looking wrong. Every value below is a median, and the
statistic is named in the caption rather than left to be inferred.

## Classification

`Flat` and `Collapse` are decided by the level test. **No concentration is reported for them**:
it does not participate in their classification, and printing it would invite a reader to
divide a number that plays no role.

| token | $100 | $1,000 | $10,000 | $100,000 | total decline | largest step | concentration | state |
|---|---|---|---|---|---|---|---|---|
| SPY | 99.90 | 99.90 | 99.86 | 99.57 | — | — | — | Flat |
| AAPL | 99.93 | 99.88 | 99.45 | 98.32 | — | — | — | Flat |
| GOOGL | 99.30 | 99.30 | 99.24 | 98.67 | — | — | — | Flat |
| NVDA | 99.89 | 99.80 | 99.46 | 97.08 | — | — | — | Flat |
| TSLA | 99.70 | 99.67 | 99.41 | 98.30 | — | — | — | Flat |
| RDDT | 99.31 | 99.19 | 97.77 | 24.02 | 75.29 | 73.75 | 97.95% | Switch |
| AMC | 99.76 | 99.73 | 99.47 | 0.02 | 99.74 | 99.45 | 99.71% | Switch |
| GME | 97.93 | 96.12 | 43.61 | 4.40 | 93.53 | 52.51 | 56.14% | Slope |
| QQQ | 6.58 | 1.93 | 0.26 | 0.03 | — | — | — | Collapse |

**Total decline and largest step are derived from the displayed cells, not from full
precision.** `RDDT` is the reason this sentence exists: at full precision its total is `75.30`,
while the four displayed cells sum to `75.29`, and `73.75 / 75.30` prints as `97.94%` against
the stated `97.95%`. Both figures are right; the table was wrong to print a ratio beside two
columns it could not be divided from.

The columns are therefore made to divide: the totals and steps above are sums of the values as
displayed, and each concentration is that division, printed to two decimals. **Any printed
ratio in this table reproduces exactly by dividing the two printed columns to its left.** If
that ever stops being true, the table is wrong, not the reader.

## Printed precision does not decide anything

The classification is invariant to the number of decimals printed. Applying the boundary rules
to the four displayed cells and to full precision gives **0 divergences across the nine
tokens**.

This is recorded because the obvious attack on a rule whose inputs are published as rounded
numbers is that its output depends on the rounding — and because the two boundaries are
close enough to a real value in one case (`GME` at `56.14%` against `2/3`) that the question
is not idle. It was measured, not assumed, and measured after the boundaries were fixed, like
every other number in this addendum.

## Sensitivity

Classification is unchanged for any shape boundary in `(56.14%, 97.95%]` — the two adjacent
concentrations in the table, on either side of the boundary. `2/3` lies inside that interval,
10.5 points from the nearer edge.

This interval is a **consequence** of fixing the boundary, computed afterwards. It is not a
justification for it, and per §3 of the registration it belongs to this window rather than to
the boundary. A window in which the two nearest values sit 41.8 points apart cannot test where
the line between them belongs.
