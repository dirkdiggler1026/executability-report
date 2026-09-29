# Addendum 3 to `PREREG-tsv-volume-cap-2026-09-28.md`

**Written 2026-09-28, before the run and before the test data is read.** It tightens the test
registered in addendum 2 §4 — which, as written, could have produced a confident wrong answer —
and records two further measurements of the index itself.

`data/2026-09-21` and `data/2026-09-22` have still not been read for this test.

---

## 1. The step, located exactly

Bisecting the transfer-event ratio on the QQQ token:

```
last block observed with ratio 1.000000000    69,216,761   2026-09-22 00:10:28 UTC
first block observed with ratio 1.000700791   69,217,129   2026-09-22 00:11:05 UTC
                                              368 blocks, 37 seconds
```

A 37-second bracket, rather than the 2 h 14 min of addendum 2, is what makes a
thirty-minute-cadence before/after comparison clean: every published round falls
unambiguously on one side.

## 2. The index changes without announcing itself

Across those 368 blocks the QQQ token emitted **12 logs: six `Transfer` and six of the ratio
event. No administrative event of any kind.** No `index()`, `getIndex()`, `sharePrice()`,
`pricePerShare()`, `multiplier()`, `scalingFactor()`, `convertToShares()` or similar getter
exists on the contract, and **none of storage slots 0–11 changed between those two blocks**.

```
MEASURED     twelve logs, none administrative; the getters named above are absent;
             slots 0-11 identical either side.
INTERPRETED  the value is derived from state outside this contract.
OPEN         where. Not pursued -- it is not needed for either the numerator or the test.
```

🔴 **Consequence for anyone consuming these tokens:** subscribing to the token's events does
not tell you the index changed. It has to be polled, or derived from the ratio inside an
ordinary transfer event — which is to say, from a number most integrations would never read.
A quantity that moves without emitting anything is the same shape as a fee that changes
without a `fee()` setter, and this project has already been caught by that one.

## 3. Four changes to the test in addendum 2 §4

### 3.1 SPY is the subject; QQQ becomes the second case

SPY's index is `1.001717991` (+17.18 bp), 2.45× QQQ's. The signal being tested scales with the
index while the noise does not, so the asset with the largest index has the best chance of
returning an answer. QQQ is run as a second, weaker case, and **both are reported whatever they
show** — running two and reporting the one that worked is the failure this file exists against.

### 3.2 🔴 A third series, and five readings rather than four

Addendum 2 compared the pool price to the oracle and read "R did not step" as "the market does
not price the index". **That reading is unsafe**: if the oracle itself carries the index, R is
constant by construction and says nothing.

So the oracle answer is reported as its own series, and the reading table becomes:

```
pool mid steps  ·  oracle does not  ⇒ the market prices the index
pool mid flat   ·  oracle flat      ⇒ neither prices it; "token price vs share price"
                                       comparisons must subtract it
pool mid steps  ·  oracle steps     ⇒ 🔴 the oracle carries the index too. R is constant by
                                       construction and the test is void for this asset --
                                       NOT evidence that the market ignores it
pool mid flat   ·  oracle steps     ⇒ inconclusive and strange; report as observed, no reading
either moves by materially more or less than the index
                                    ⇒ inconclusive; a coincident move is not the index
```

The middle row is the one addendum 2 would have got wrong.

### 3.3 The threshold is the data's own noise, not a number we pick

```
signal  Δ log R across the step block
scale   stdev of Δ log R between adjacent rounds, in the same window, excluding the step
report  signal / scale, and the count of rounds either side
```

No external assumption, and no threshold invented by us. If the ratio of signal to scale is
small, the honest output is "this data cannot see a 17 bp step", which is a result.

### 3.4 Falsifier, so the whole test is refusable

If the control asset TSLA — whose index is exactly `1.000000000` and cannot step for this
reason — shows a step of comparable size at the same block, **the method is wrong and no
reading from it is reported.** Not "TSLA moved a bit too"; the test fails and is published as
having failed.

## 4. Where the result goes, decided before it exists

```
either outcome changes no published figure of ours. The depth statistics are ratios in
which the unit cancels (addendum 2 §5).

it does NOT go into the third comment to the SEC. That letter's subject is the volume-cap
computation and one real number. Adding a structural finding to it would dilute the one
thing it is for, and the record already carries two letters five days old.

it goes into this repository as a dated page, at the three-layer labels, with the raw
series attached.
```

## 5. What this addendum does not do

- It does not change the numerator definition, the symbol set, the pool readings, the window,
  or the attribution limit.
- It does not claim to know where the index is stored, nor that the design is unusual.
- It does not register an expected outcome. Five readings are written out precisely so that
  whichever occurs, the sentence describing it already exists.
