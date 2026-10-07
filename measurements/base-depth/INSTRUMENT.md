# Instrument properties — Base exit-depth

This file describes the **instrument**, not the asset, and it belongs to the run pair named below.
The scope line is printed from the input rather than written here, so it cannot be dropped in a
later rewrite.

> runs Y5 and Y6 at block 52175000; does not describe the read volume of the published table, whose logs are Y1/Y2 and carry no cache_hits field

- Block `52175000` · run pair `Y5` / `Y6` · rows in R (completed and bit-identical in both): **42**
- **Non-memo row-attributed reads are the reproducible quantity: `3071` in both runs.**
  Memoisation takes it to `2458` / `2450` (20.0% / 20.2% fewer).
- On the two selectors `ranges_of` issues (0x5339c296, 0xf30dba93) the ratio is **1.26× / 1.26×**,
  and every cache hit lies on those two selectors (`613` / `621`).
- One row's issued/hit split differs between the runs: `0x7f030e5f…|100000 (AMZNc/USDC)` by 8 calls — the row
  that failed in one run completed in the other, its crossings matched, so the same memo key was
  filled by one and hit by the other. The split therefore follows cross-row cache fill order; the
  total does not move.
