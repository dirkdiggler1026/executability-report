# A numerator with no denominator

**What §II.F of the tokenised-stock exemption caps is a ratio. This is the top half of it, for
nine symbols over September 2026, and nothing else.** The bottom half — consolidated ADV of the
NMS stock from an effective transaction reporting plan — we could not obtain from a free
authoritative source, so **no statement about any cap, threshold or breach appears here or can
be derived from here.**

Registered in `PREREG-tsv-volume-cap-2026-09-28.md` and its five addenda, all committed before
the run. Run 2026-09-29.

---

## 1. Result — 28 complete days

```
2026-09-01 .. 2026-09-28   ·   9,786,117 swaps   ·   501 cells   ·   0 failures

                  reading A: all 66 pools          reading B: the 47 USDG-quoted
asset          28-day shares      per day          28-day shares      per day
AMC             62,400,175.7    2,228,577.7         61,000,286.4    2,178,581.7
GME             11,711,851.8      418,280.4         10,291,689.4      367,560.3
NVDA             4,293,861.2      153,352.2          3,487,350.1      124,548.2
SPY                818,136.6       29,219.2            346,051.1       12,359.0
AAPL               586,517.8       20,947.1            421,649.9       15,058.9
GOOGL              499,910.8       17,854.0            479,366.9       17,120.2
RDDT               291,549.4       10,412.5            163,577.2        5,842.0
TSLA               210,782.5        7,527.9            166,781.9        5,956.5
QQQ                133,975.8        4,784.8            124,871.5        4,459.7
```

17 or 18 cells every day, every day present, no cell failed. Daily swap counts run from
1,073,143 (09-04) down to 58,022 (09-26).

🔴 **This is not a bound.** Which venue a pool belongs to is not observable on chain, and
§II.F's numerator is per-venue and must be aggregated across affiliates. The figures above are
an estimate over a stated pool set. They cannot be used to say a threshold was not exceeded.

## 2. The registered window is a calendar month and the run was made inside it

```
registered   2026-09-01 .. 2026-09-30
complete     2026-09-01 .. 2026-09-28        28 days, the table above
partial      2026-09-29                      the run day, blocks to 11:26 UTC only
absent       2026-09-30                      had not happened
```

Not a gap in the data — two of the thirty days could not exist yet. A month figure must be
recomputed on or after 2026-10-01. The 28-day figures do not change when it is; they are
complete days and the method does not look outside a day.

## 3. A figure of ours that this replaces

An earlier note of ours said QQQ trades about **9.76 tokens a day**, and reasoned from it that
the caps were not close. **That number was wrong by a factor of about 490** and the reasoning
built on it is withdrawn.

The cause was a silent one. `eth_getLogs` over a whole day refuses two ways — `exceeds limit`
and `timed out` — and both mean the range is too large, but the collector recorded them as
failures and moved on, leaving the day's total looking small rather than incomplete. Recursive
halving of the block range turned one test day from **81,507 swaps with 10 failures** into
**253,603 with none**: two thirds of that day's trading was in exactly the pools that had been
failing. Busy pools time out; quiet ones do not. **The failure mode was biased towards deleting
volume**, which is the worst direction for a measurement whose whole purpose is a volume count.

The correct statement is not "QQQ is far from the cap" and not "QQQ is near it". It is: **the
numerator is 4,785 shares a day and the denominator is not in hand.**

## 4. How the share count is formed

The denominator of §II.F is a share count, so the numerator must be one, and a token is not a
share. Each token carries a per-asset multiplier that differs by asset and moves in steps; it
is exposed by **`uiMultiplier()`** (selector `0xa60bf13d`, ERC-8056) and equals the ratio of
the two amounts in the log that accompanies every transfer. This run reads it from the transfer
logs, which is what a sparse historical scan can do cheaply; the getter returns the same value
(verified on all nine tokens, matching to every digit). **A change is not announced** — over
the 340 blocks containing the QQQ step the token emitted no event but transfers. The run
applies the multiplier:

```
shares(asset, day) = Σ over swaps  token_amount × ratio(asset, block)
```

```
                ratio observed in the window     stepped inside the window?
SPY     1.000000000 -> 1.001717991                     yes, once
NVDA    1.000000000 -> 1.000775159                     yes, once
QQQ     1.000000000 -> 1.000700791                     yes, once
GOOGL   1.000000000 -> 1.000193924                     yes, once
AAPL    1.000566080 throughout                         no -- already above 1 on 09-01
TSLA    1.000000000 throughout                         no
GME     1.000000000 throughout                         no
AMC     1.000000000 throughout                         no
RDDT    1.000000000 throughout                         no
```

⚠️ **Four stepped, not five.** AAPL is above 1 for the whole of September and does **not** step
in it. "Above 1" and "stepped during the window" are different statements about different
assets, and the difference is the kind that survives into a sentence someone else quotes.

The effect on the totals is small and is reported rather than hidden: index-adjusted against
raw, over the 28 days, AAPL +5.66 bp, NVDA +4.61 bp, SPY +4.00 bp, GOOGL +0.61 bp, QQQ +0.59 bp,
the rest exactly zero. It changes no order of magnitude, which is a reason to publish both
columns, not a reason to drop one.

**Carry-forward, per addendum 4.** Each cell records where its ratio came from. Across all
9,786,117 swaps the marker reads `carried` 9,786,112 times and `observed` 5. That is the honest
reading of the method and not a defect: the ratio is a step function read from a sampled step
table, so a swap's ratio is "observed" only if a step boundary was bisected at that exact block.
**No swap is ever assigned 1 by default**; where a ratio could not be established the row would
be left empty and counted, and no row was.

## 5. What the sampling cannot see

```
sampling    21-27 samples per asset across the month, gap 934,701 blocks (~27 hours),
            each sample read from the largest transfer in a 1,500-block window
            (rounding error ~1/n0, so the largest transfer is the most precise one)
bisection   each detected change narrowed to a pair of adjacent transfers
blind to    a change that reverses between two samples. Accrual is cumulative, which
            argues it cannot, but we have not measured that it cannot.
pool set    the union of the four archived enumerations (66 pools, 47 USDG), all of
            which ran after 2026-09-01. A pool that traded in early September and had
            stopped classifying by 09-26 is in none of them and is missing here.
```

## 6. Files

```
tsv-volume-2026-09-01_2026-09-30.json   519 rows, 0 failures, with the pool set, the
                                        sampling record, the carry-forward markers, and
                                        the corrections this run made to its own
                                        pre-registration
code/tsv_volume.py                      the program
```

Two metadata strings and the completeness block in the artifact were written after the run,
taken verbatim out of `code/tsv_volume.py` by parsing its source so that a regeneration
produces the same file; the artifact records that it was done and no measured value was
touched.
