# Addendum 3 to PREREG-rtr-recovery-shape-2026-09-22

**Correction to the QQQ example in §10, and the method limit it exposed. Computed 2026-09-23.**

This addendum exists because §10 uses QQQ's small sizes as its one measured example, and the
recovery figure in it is wrong. §10 cites `$100 → 6.58%` with fee tiers of 70% and 88%. **The
fee tiers are right. The recovery figure is not** — and the reason is a property of the
measurement method that §10 does not state.

## What was wrong

The pool table is built by probing every candidate pool with a `$10,000` buy and dropping the
ones that cannot fill it (`build_pool_table.py`, step 2). A pool that fills `$300` and not
`$10,000` is therefore never a candidate — and `$100` and `$1,000` are exactly the sizes at
which such a pool wins. **The exclusion is by construction, not by oversight**, and it is not
fixed by rebuilding the table: the probe would still be there.

QQQ is the one token on this chain where that exclusion changes the published answer. Measured
across all nine tokens, 34 of the 36 cells (9 tokens × 4 sizes) survive a direct quote against
every pool at the same block.

## What the chain says

Quoted against **every initialized QQQ/USDG pool**, rather than against the stored table, at
three pinned blocks:

| block | $100 | $1,000 | $10,000 | $100,000 |
|---|---|---|---|---|
| 54,088,399 (2026-09-04) | 99.67% | 98.62% | 0.26% | 0.03% |
| 61,129,566 (2026-09-12) | 99.29% | 99.21% | 91.11% | 0.03% |
| 70,427,772 (2026-09-23) | 97.34% | 2.19% | 0.35% | 0.04% |

The `$100,000` rung is 0.03% at all three. The cheap route is one contract, fee 0.30%. **What
moves across those blocks is not its fee but its capacity** — the largest notional it will
quote — which was **$9,841 → $10,506 → $287**.

## What this does to §10's argument

§10's conclusion is unchanged, and this correction strengthens the second half of it.

§10 says the fee is the part no execution technique can lift. **That remains true of a given
pool:** a round trip pays the fee twice, so the ceiling through the 70% pool is
`(1 − 0.70)² = 9.00%` and through the 88% pool `(1 − 0.88)² = 1.44%`, and no ordering
technique changes either number.

What §10 gets wrong is the example, and what replaces it is a better one. The quantity that
moves is **capacity**. It moved across two orders of magnitude in seven weeks — up once, then
down — and it is visible in none of the fields Condition G requires:

- **End-of-day pool size** is one scalar per asset pair per day. It is not a capacity, and it
  is not per pool.
- **Executed transactions** show only the trades small enough to have happened.

Neither can see the boundary, and neither can see it move.

## Status

This addendum corrects an example. It does not change RTR's definition, the boundary `Λ`, the
boundary `2/3`, the four state names, or any falsification condition in §7. **The registration
is not edited.**

## How to check it, and one thing still missing

The measurement is a full-chain scan of `Initialize` on the PoolManager, filtered to the two
currencies, then a direct quote of each surviving pool at the pinned block:

    python resolve_qqq_pools_at_54088399.py --block 54088399 --sym QQQ
    python measure_cheap_pool_capacity.py

⚠️ **Those two scripts are not yet in this repository.** Until they are, this addendum is
checkable in principle and not in practice by a reader of this repository alone — which is the
one property every other claim here has. Adding them to `code/` is part of the method fix.

One qualification, so that the limitation is not stated more broadly than it is: **the third
row was taken close to the chain head, and a reader could have reproduced it against the public
endpoint at the time, without an archive endpoint — as anyone can produce a current row the
same way.** Only the two earlier rows require an archive endpoint. The chain's public endpoint
keeps about ten minutes of state, so any block older than a few minutes is out of its reach —
which is why the historical rows are not reproducible by that route and the current one is.
