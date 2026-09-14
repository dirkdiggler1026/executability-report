# Second addendum to the absolute-floor pre-registration (2026-09-14)

Refers to `PREREG-floor90-2026-09-14.md` (sha256 `0150937253e6…929e`) and its first addendum
(sha256 `149424d6ddd0…250c`). Written 2026-09-14 UTC, before the forward window opens at
2026-09-15 00:00 UTC. It pins one further instrument input and records one that is
deliberately left unpinned. It adds no degree of freedom.

## 4. The sampling rate is pinned

The trigger is evaluated only on rounds sampled at the calibration rate: **48 rounds per day,
30 minutes apart**. Per-day counts in the calibration window: 34 on the partial first day
(2026-09-04), 48 on each of the nine days after. Median spacing between consecutive rounds,
30.0 minutes.

An episode is a run of consecutive triggering rounds, and falsifier 1 counts **episodes per
month**. Sample less often and fewer excursions are observed, so the count falls and falsifier 1
becomes harder to violate — **the rule would look better for an instrument reason**. This is the
same shape as canon v3 in the first addendum, with one difference: a lower rate is visible in
the monthly denominator (cell-rounds), but falsifier 1 uses a count, not a rate, so that
denominator does not protect it.

**This collision is scheduled, not hypothetical.** The storage decision due in mid-to-late
October lists reducing the sampling frequency among its options. This line is why that option
is not free.

**A change of sampling rate ends this registration, or the reduced-rate data is reported as a
separate series.** Which of the two is not decided here.

## 5. The drop policy is pinned

A round in which any quote fails with `rpc_error` after the bounded retry is **dropped whole**
rather than written. The calibration configuration is 1 initial attempt plus 2 retries with
1.5-second linear backoff. No round was dropped anywhere in the calibration window: zero
`failures.jsonl` records exist across all ten days.

A more aggressive drop policy removes rounds, which lowers the episode count for an instrument
reason — the same shape as the sampling rate. Pinned by naming it. The observable pressure runs
the other way (toward more retries, which adds rounds), but the direction of the pressure is not
a reason to leave the input unwritten.

## 6. What is deliberately not pinned, and why

**Block selection.** Each round pins the block returned by `eth_blockNumber` at sampling time,
with no lag constant. A future change — pinning to tip minus N for reorg safety, say — would
shift which blocks are measured. It is **not pinned here** because it has no direction: at
roughly ten blocks per second, tip and tip-minus-N differ by about a second of chain time, and
that displacement does not systematically raise or lower recovery, so it cannot make a
falsifier easier or harder to violate. It is written down so the omission is a decision on the
record rather than something nobody thought of.

## Why this is still an addendum

The floor, the cell set, the episode definition and the three falsification thresholds are
unchanged. Sections 4 and 5 remove freedom; section 6 records an omission without granting any.
All of it predates the first round the rule will be evaluated on.

## Status of this file

Never edited. Its git commit timestamp is the evidence that it predates the window it applies
to.
