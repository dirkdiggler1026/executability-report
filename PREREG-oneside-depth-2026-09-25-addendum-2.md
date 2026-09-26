# Addendum 2 to `PREREG-oneside-depth-2026-09-25.md`

**Written 2026-09-26, after the forward window opened at 00:00 UTC. Three rounds had been
collected (blocks 72,639,319 / 72,674,994 / 72,710,519) when this was written.** It records
how partial fills interact with the ranking, and how the venue list is refreshed. Neither is
a change: §1, §9 and §8 of the registration stand exactly as registered.

---

## 1. Partial fills and the ranking

In the first three rounds, **81 of 492 rows** are `partial` — the pool answered and took less
than the offered shares. They are not rounding: the closest to complete is 0.9188, and no row
sits above 0.999999. They concentrate in a few small pools, and one of them declines part of
even the \$100 rung.

The ranking is `argmax(amount_out_usd)` over the rows of a cell, and every row in a cell is
offered the **same** `shares_offered_raw`. A pool that fills only part of the order therefore
sells fewer shares and returns fewer dollars, and it loses the cell. Two different causes —
a worse price, and an inability to fill — arrive at the same place in the ordering.

> **Registered reading.** Partial fills are ranked on total proceeds for the offered share
> count. **The unfilled remainder is not routed anywhere else.** The winning pool is therefore
> a **lower bound on realisable proceeds**, not the outcome of an optimal route.

This is stated because a reader recomputing the winner needs to know what happens to the
remainder. A reader who assumed the remainder was re-offered to the next pool would compute a
different winner, and would be right to call that a discrepancy.

`shares_consumed_raw` is in the preimage and in every row, so the filled fraction of both the
winner and every loser is recoverable from the published file. Nothing about this is hidden
in an aggregate.

## 2. Venue list refresh

The list is re-enumerated **once a day at 03:30 UTC**, by the §2 method, over a rolling window
of 900,000 blocks (about 25 hours of this chain). Collection runs on the hour; the two do not
overlap.

Three properties, each registered here because each is a failure this project has already had:

```
a  Every enumeration is archived as enumerations/pools-<block>.json and never overwritten.
   A round records enumerated_at_block, and that number has to point at a file that still
   exists; a single overwritten current-list would make the number unresolvable.

b  Every round carries how old its list is and whether the last refresh succeeded:
   pools_source.age_blocks, and pools_source.refresh.{last_attempt_ok, last_success_utc,
   consecutive_failures}. A refresh failure does not stop collection -- the previous list is
   used -- but a stale list is never allowed to look freshly enumerated.

c  A pool already in the list is always re-classified, whatever its rank. It leaves the list
   only by ceasing to classify as a pool, which is a fact about the chain, and never by
   falling below a cut-off, which is a fact about us.
```

### 2.1 The cut-off, and why it is recorded rather than removed

Candidates are ranked **per asset** and the top 40 of each are classified. A first
implementation ranked all assets' counterparties together and took the top 80; the assets with
the most transfers crowded out the rest, and two assets came back with no pools at all. A
cut-off that produces an absence indistinguishable from data is the failure this project keeps
finding, and a global rank is one.

Ranking per asset does not remove the cut-off; it stops one asset's volume from consuming
another's budget. So the cut-off is **recorded**: each enumeration carries
`per_asset_candidates[asset].{two_way, taken, truncated}` and `per_asset_cap`. A reader can
see exactly how many two-way counterparties were left unclassified, per asset, in the run that
produced the list a round used.

Combined with §2.1 of the registration — the list is not claimed complete — this is what the
completeness statement looks like when it is implemented rather than asserted.

## 3. What this addendum does not do

- It does not change the statistic, the preimage, the cell set, the failure rules, or any
  falsification condition. The registration of 2026-09-25 keeps its date.
- It does not register a threshold. §7 of the registration still registers none.
- It does not claim the 40-per-asset cut-off is sufficient. It claims the cut-off is visible
  in the artifact, which is a different and weaker thing.
