# Addendum 4 to `PREREG-tsv-volume-cap-2026-09-28.md`

**Written 2026-09-28, before the run.** Two rules, both of which change what the run does, so
both have to be here rather than in the write-up. Short on purpose.

## On there being four of these in one day

The registration and its four addenda were all written on 2026-09-28, before any figure
existed. Each came from someone reading the previous one and finding a hole: a bound that was
not a bound, a constant that was not a constant, a test that could return a confident wrong
answer, and now two rules the run would otherwise have decided silently. **That is the process
working, not a drafting failure** — but a reader is entitled to see it said, so it is said
here rather than left as an odd-looking file count.

---

## 1. The index is only visible where a transfer happened

The index can be read only from the ratio inside a transfer event. A block with no transfer of
that token carries no reading. The run therefore needs a rule, and picking one while looking
at the data is exactly what these files exist to prevent.

> **Registered rule.** For a block with no observation, use the most recent earlier observed
> value, and mark the row as carried. The index is constant between steps — zero spread across
> every event at a given moment, measured on five tokens — so carrying forward is safe; but
> "safe" is not "observed", and the two must be distinguishable in the output.
>
> ```
> index_source = "observed"  the block has an event of its own
>              = "carried"   nearest earlier observation, with its block recorded
>              = "none"      no earlier observation exists in the window; the row is
>                            empty and counted, never back-filled with 1
> ```

🔴 The failure this prevents is specific: a silent carry-forward across a step would apply the
old index after the index changed, and nothing in the output would show it. With the marker,
a reader can find every row whose index came from somewhere else and how far away.

## 2. If the falsifier fires, the failure must be attributable

Addendum 3 §3.4 says that if TSLA — index exactly `1.000000000` — steps at the same block, the
method is wrong and the test is published as having failed. That is right and it is not
enough: "the method is wrong" is not a finding anyone can act on.

> **Registered rule.** When the falsifier fires, report which of the three series moved,
> because they fail for different reasons and only one of them is about the market:
>
> ```
> the oracle column moved       the denominator is at fault -- the feed carries an index of
>                               its own, or the answer read was stale. A property of the
>                               instrument, not of the market.
> the pool column moved         ordinary price movement large enough to swamp the test at
>                               this asset. The test lacked power; say so with the numbers.
> both moved                    the quote asset or the conversion moved. Neither column is
>                               usable and the window is reported as unusable.
> ```
>
> The published sentence names the column. "The test failed" without it is the same shape as
> a refusal record that keeps no reason — a rule that voids a result is only auditable when
> the reason survives, and that one has already cost this project a round.

## 3. What this addendum does not do

- It does not change the numerator formula, the symbol set, the pool readings, the window, the
  attribution limit, or any of the five readings in addendum 3.
- It does not state an expected outcome for the falsifier. It states how to describe each way
  it can fire.
