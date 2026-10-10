# Pre-expiry exit curve of a Pendle PT market, captured hourly until it expires

The market is `0x25ee3232421a08f390ef25a34b1d2ccc8394bd05` on Robinhood Chain and it expires
**2026-10-22 00:00:00 UTC**. Before that an exit is a trade against the market's curve; after
it, PT redeems and the question becomes the redemption path. Those are two quantities and they
do not go under one label — this directory holds only the first.

`orbio-<block>.json` are state captures written by `code/read_orbio_state.py`, one per hour,
each with its read list and response archive and the digests of both (`code/verify_reads.py`
checks them). `curve-<block>.json` are the exit curves `code/pendle_pt_exit_curve.py` computes
from them. **Figures below are read from those files; if one ever disagrees with its artifact,
the artifact is right and this file is wrong.**

## The quantity, and the one it is not

`recovery_pct` is the proceeds of selling N PT divided by N times **the market's own pre-trade
marginal quote** at the same block. Nothing outside the market enters either side — the same
shape as the Base work, so the two are comparable.

`proceeds_vs_face_value_pct` is the same proceeds against PT's face value of one unit per PT.
It is reported and it is **not** the claim: it climbs towards 100% as expiry approaches no
matter what happens to the book, because the discount PT trades at shrinks with the remaining
time.

## Why there is a third column, and what it caught

The claim is not clock-free either, which is the correction this directory exists to carry.
`rateScalar` is `scalarRoot × 365d / timeToExpiry`, so the curve flattens as expiry nears:
holding this market's reserves fixed and moving only the clock, selling 200,000 PT recovers
**91.914280%** a year out and **99.986714%** half a day out. Those two are the only figures on
this page that are not columns of a committed artifact, so here is how to get them back:

```
python3 code/pendle_pt_exit_curve.py --capture measurements/orbio-pendle/orbio-85122008.json \
        --sizes 200000 --reference-days 365     # and again with --reference-days 0.5
```

A single capture's `recovery_pct` is a fact about that block. A *series* of them is not a depth
series.

So every row also carries `recovery_pct_at_reference_clock`: the same reserves recomputed at
one declared time to expiry (`reference_seconds_to_expiry`, 30 days). The clock is pinned, so
what is left to move is the book.

The first three captures show why that column is the one to put in a series. Over 1 h 48 min
in which this market emitted no events at all, measured recovery at 200,000 PT rose from
**99.698638%** to **99.700612%** — while the 30-day reference column stayed **identical to all
six decimals** across every capture. The measured column would have been read as a market
getting deeper. Nothing happened to the book.

## Coverage limits, all of them

**Standing of every figure here: the published formula evaluated on an archived state, not
validated against any executed trade.** The market's swap entry point reverts under `eth_call`
because it requires PT to be transferred in first, so there is no on-chain quote to compare
against. And this market is nearly dormant — its last event is at block 83,458,608 — so there
is no recent trade to replay against either. The logs that do exist are archived in
`../pendle-market-logs/`; reconstructing the state they occurred at is a separate piece of
work and it has not been done.

**The series starts at the first capture that carries the PY index, judged by field presence.**
Pendle's market maths takes a PY index and `readState` does not return it, so a capture without
it cannot price anything; `code/pendle_pt_exit_curve.py` exits 3 on those rather than returning
a number. Two captures predate that read and cannot be repaired — the state they would have
read is already gone. The index currently reads exactly 1.0, which is the trap: a quantity that
equals one looks like a quantity that can be dropped.

**A size above the market's 0.96 PT-proportion cap is a refusal, not a low recovery.** The
market would revert; "will not quote this" and "quotes this badly" are different findings and
the ladder prints them differently.

**Arithmetic is 60-digit decimal, the contract's is 1e18 fixed point with Balancer's
LogExpMath.** Figures can differ in the last places and that difference is not modelled.

**The four self-checks on every curve are internal.** They catch a fee applied twice, a rate
anchor inconsistent with the rate function, a curve that does not respond to size, and a
reference column that is not actually controlling for the clock. None of them establishes that
this implementation matches Pendle's deployed contract: a formula wrong in the same way
everywhere satisfies all four. Each check carries that boundary next to it in the artifact.
