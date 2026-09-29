# A 24-hour oracle cannot be the reference for a 30-minute comparison

**A negative result, published because the design fault is the useful part.** Registered in
`PREREG-tsv-volume-cap-2026-09-28-addendum-2.md` §4 and amended by
`-addendum-3.md` §3, both written before the data was read. Run 2026-09-29.

**The test failed. Its own falsifier caught it.** What follows is what was asked, what was
measured, why it cannot answer the question, and what would be needed to answer it.

---

## 1. The question, and why it was worth asking

Each tokenised stock on Robinhood Chain carries a per-asset index that steps: every dividend
payer is above 1, every non-payer is exactly `1.000000000`. QQQ's index moved from
`1.000000000` to `1.000700791` inside a 37-second window on 2026-09-22
(blocks 69,216,761 → 69,217,129).

Does the market price it? If it does, every "token price against share price" comparison must
subtract it. If it does not, the index is an accounting quantity and the same comparisons must
subtract it for the opposite reason. Either answer is useful.

## 2. The design, and the control that killed it

```
R(asset, t)  =  pool mid, USD per token   ÷   the chain's own Chainlink feed for that asset

subject   QQQ    pool 0xd60a5d14db690b7afad71f76b108071d7175597d
                 feed 0x80901d846d5D7B030F26B480776EE3b29374C2ae
control   TSLA   pool 0xf4acdaeeb7022862a763c9b1b885e11191c889e3
                 feed 0x4A1166a659A55625345e9515b32adECea5547C38
                 index exactly 1.000000000 -- it CANNOT move for this reason
data      the published rhdepth-v2 pinned blocks, 12 rounds either side of the step
threshold the data's own noise: the step's change in log, against the standard deviation
          of that change between adjacent rounds in the same window
expected  +7.008 bp, if the market prices the index in full
```

The registered falsifier: *if the control steps comparably, the method is wrong and the test
is published as having failed.*

## 3. What was measured

```
                 across the step     adjacent-round noise σ     signal / noise
QQQ  pool mid       +17.283 bp              8.032 bp                +2.15
     oracle          +0.000 bp             10.543 bp                 0.00
     R              +17.283 bp             10.301 bp                +1.68

TSLA pool mid        +5.347 bp              9.661 bp                +0.55
     oracle         +50.201 bp             15.425 bp                +3.25   ← 🔴
     R              -44.854 bp             11.123 bp                -4.03   ← 🔴
```

The control's R moved **−44.85 bp, 2.6× the subject's, in the opposite direction**, at a
signal-to-noise of −4.03. TSLA's index is exactly 1 and cannot produce that. **The falsifier
fires.**

## 4. Which column moved, and why — the failure is attributable

`addendum-4.md` §2 requires naming the column, because the three fail for different reasons
and only one of them is about the market. Here it is **the oracle column**: TSLA's pool mid
barely moved (+5.35 bp, s/n 0.55) while its feed moved +50.20 bp (s/n 3.25).

The cause is in the feeds' own update cadence, not in anything about the market:

```
window 11.5 hours, 24 published rounds

QQQ  feed updatedAt takes 2 distinct values across 24 rounds
       2026-09-21 16:10:07   covering  2 rounds
       2026-09-21 19:23:11   covering 22 rounds

TSLA feed updatedAt takes 4 distinct values across 24 rounds
       2026-09-21 15:35:13   covering  1 round
       2026-09-21 18:55:34   covering  2 rounds
       2026-09-21 19:49:05   covering  9 rounds
       2026-09-22 00:07:40   covering 12 rounds

heartbeat, from the feed's own configuration: 86,400 s = 24 hours
```

On a 30-minute series the feed is a **staircase**: a dozen rounds read one number, and then
one update carries half a day of price movement in a single step. That step was +50 bp on
TSLA. A 7 bp signal underneath it is not small — it is invisible.

⚠️ **This is not a defect in the feeds.** An equity trades for six and a half hours a day and
a daily-heartbeat feed is an ordinary design for one. The statement is about *use*: **anyone
comparing an on-chain price to one of these feeds at sub-daily resolution is comparing it to a
staircase**, and differences they attribute to the market will largely be the feed's update
schedule.

## 5. The sentence this result prevented

Without the control, the subject's numbers read like a finding:

> QQQ's R moved +17.28 bp across the step at a signal-to-noise of 1.68, against an expected
> 7.01 bp.

**We would have written that the market prices the index, and partly over-prices it.** The
control's −44.85 bp is the only thing standing between that sentence and publication. This is
the first time in this project that a registered falsifier has fired on live data and stopped
a result from being written — the mechanism was built for exactly this and it worked on the
first occasion it was tested.

## 6. Status of the original question

```
MEASURED     the index, its step, its exact bracket, and the three series above
MEASURED     the feeds' update cadence within the window, from their own updatedAt
CONCLUDED    R against these feeds cannot resolve a 7 bp step at 30-minute resolution;
             the test is void, not negative-about-the-market
OPEN         whether the market prices the index
```

**Not "we do not know".** The precise state is: *this question is not answerable from this
chain's public data at this resolution.* Answering it needs one of

- an off-chain reference priced at the same cadence as the rounds, or
- a second on-chain wrapper of the same asset that does **not** accrue, so the index is the
  only difference between them.

Neither exists on this chain as far as we have looked, and "as far as we have looked" is not
a claim that neither exists.

## 7. Two rules this leaves behind

```
1  Before designing any on-chain-versus-reference comparison, check the reference's
   UPDATE CADENCE first. Here the cadence killed the test, not the market and not the
   instrument -- and cadence is cheap to check and was not checked.

2  A control that cannot move for the reason under test is not optional. The same rule
   already governs the crypto feeds in the oracle-staleness series; this is the second
   time it has been the difference between a result and a mistake.
```

## Files

```
index-priced-test-QQQ-2026-09-22.json   the three series for both assets, every round,
                                        with each feed's updatedAt, plus the statistics
code/index_priced_test.py               the program, which prints the numbers whichever
                                        reading they select, including the failing ones
```
