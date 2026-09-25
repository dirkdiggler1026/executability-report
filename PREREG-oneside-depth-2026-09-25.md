# Pre-registration: one-sided executable depth

**Registration date: the date this file first appears in the public repository. Forward
evaluation starts at 00:00 UTC on the day after that.**

A local commit timestamp is not evidence of anything: `GIT_COMMITTER_DATE` can be set to any
value, so a commit that has not been published carries no time evidence for a third party.
What cannot be backdated is the earliest moment the file was publicly observable, and that is
what the registration date means here, exactly as in
`PREREG-rtr-recovery-shape-2026-09-22.md`.

**This registration does not replace that one.** The `rhdepth-v2` series and its forward
window continue unchanged, under the canon they were registered with, including the defect
recorded in `PREREG-rtr-recovery-shape-2026-09-22-addendum-4.md`. Changing a registered series
after a defect is found in it would destroy the only thing registration buys. This is a
**second, parallel series**, with its own canon, run alongside.

---

## 0. Why a second series

For a round trip through one pool, the buy leg's price impact is returned by the sell leg that
retraces it. The result is `(1−f)²` for any pool that fills, independent of size. A round-trip
recovery figure is therefore a fee meter: **depth does not appear in it.** That is a property
of the construction, not of any particular chain, and it is set out with the algebra and the
measurements in addendum 4 to the earlier registration.

A forced seller does not round-trip. One direction is walked, and the impact is not returned.
This registration fixes the statistic for that question before it is evaluated forward.

## 0.1 Calibration disclosure — read this before §2

**The definitions below were written after looking at a measurement taken on 2026-09-25**: nine
assets × four sizes, block 72,245,711, and the venue enumeration described in §2. That
measurement is therefore **calibration, not test**. It informed what to measure and how to
compare across pools. It establishes nothing about the forward window.

No threshold, boundary, or classification is registered here at all — see §7. That is
deliberate: having already seen one day of this statistic, any cut-off chosen now would be
fitted to it. What is registered is **a measurement procedure and a serialisation contract**,
which are checkable without reference to any outcome.

---

## 1. The statistic

At a pinned block `B`, for asset `A` and notional rung `N` in US dollars:

```
1  Enumerate the candidate pools for A            (§2)
2  m_A := the median of the candidate pools' own mids at B, in USD    (§3)
3  s    := N / m_A                                 shares, fixed for all pools
4  For each pool p: quote an exact-input sale of exactly s shares of A into p
5  P    := the greatest USD proceeds returned by any pool
6  one-sided loss  L := 1 − P / N
7  filled fraction f_p := (input consumed) / s, for the pool that produced P
```

**`L` is the registered statistic.** `f_p` is registered alongside it and is not optional:
without it, a large `L` cannot be distinguished from a pool that declined most of the order.

### 1.1 What is deliberately not in it

- **No external price.** `m_A` comes from the pools themselves. No index, no oracle, no
  exchange feed.
- **No round trip.** See §0.
- **No routing across pools within one rung.** Each quote is against one pool. Splitting an
  order across pools is a strategy, not a property of the venue, and it would make the figure
  depend on an optimiser rather than on the chain.

### 1.2 The invariant that makes `m_A` harmless

`m_A` sets the rung label, not the ranking: step 4 sends the **same `s`** to every pool and
step 5 ranks by **absolute proceeds**. Therefore

> **Registered invariant.** Replacing `m_A` with any other positive number leaves the winning
> pool of every cell unchanged.

This is checkable on any published round, and a counterexample falsifies the implementation.
It is the reason a mid is not a benchmark here: it scales `N` and `s` together.

## 2. Venue enumeration — the method, the windows, the criterion

Pools are **not** enumerated from a known factory's events. That method finds only venues
matching a pattern the author already knows, and on 2026-09-25 it was found to have missed two
further factories and one further class of AMM on this chain.

```
a  For each asset, read its Transfer logs over the declared windows.
b  Keep every counterparty that both sends and receives the token.
c  Ask each one what it is, by calling its interface:
     slot0() answers            -> concentrated-liquidity pool; read token0/token1/fee/factory
     getReserves() answers      -> reserve-based pool; read what it will answer
     neither                    -> unclassified; recorded, not quoted, not counted as absent
d  Keep the pools whose pair is (A, quote currency) for a declared quote currency.
```

**Declared windows and quote currencies are published with each round**, in the round record,
not in prose. A round whose window differs from the previous round's says so in its own
record.

### 2.1 The completeness statement, registered

> **This procedure does not establish that the venue list is complete, and no figure produced
> by it is a claim about the chain.** Every figure is scoped to the venues enumerated, by the
> stated method, over the stated windows. If a venue found later wins a cell, that is an
> **update** to the series, not a correction of it — provided the published wording carried
> the scope. Wording that claims the chain rather than the enumeration is a defect in the
> wording, and is corrected as one.

This paragraph exists because the failure it describes already happened once, on 2026-09-24,
in a comment filed with the Securities and Exchange Commission, and was corrected on
2026-09-25.

## 3. Mids, and the quote-currency conversion

A pool's own mid is its marginal price at `B`, from the pool's own state, expressed in USD:

- For a pool quoted in the USD stablecoin, directly.
- For a pool quoted in the chain's wrapped ether, through **one declared conversion pool**,
  at that pool's own marginal price at the same block `B`. The conversion pool's address is
  recorded in every round that uses it.

**The conversion is an assumption and is labelled as one.** A rung whose USD label depends on
it is marked in the record. The §1.2 invariant means the assumption cannot change which pool
wins; it can shift the rung label, and therefore `L`, for wrapped-ether-quoted pools.

## 4. Cells

```
assets   the tokenised NMS stocks tracked by the rhdepth-v2 series, unchanged
sizes    $100, $1,000, $10,000, $100,000
block    one block per round, pinned; every call in a round uses it
```

Sizes are fixed here and not chosen per round. A series free to choose its ladder can choose
the rung on which it looks best.

## 5. Fee, and why it is read per block and never as a property

The winning pool's fee is recorded **at block `B`**, never as an attribute of the pool. On
2026-09-25 a pool on this chain was measured returning different values from `fee()` on
different blocks, while exposing no dynamic-fee marker and none of the conventional fee-setter
selectors that were checked for — `setFee`, `dynamicFee`, `currentFee`, `baseFee`,
`feeManager`. That is a statement about the selectors looked for, not a proof that no setter
exists. What is established is narrower and sufficient: a single read of `fee()` does not
disclose that the value moves. A series that records a fee once and reuses it is wrong on that
class of pool and cannot tell that it is.

## 6. Failure handling

```
ok             the pool answered and the input was consumed in full
partial        the pool answered and consumed part of the input; f_p < 1 records how much
no_liquidity   the pool answered and would take none of it          -> this is data
rpc_error      no answer was obtained                                -> this is not a measurement
```

**`no_liquidity` and `rpc_error` are never merged, and neither is ever written as a zero.**
A round in which any pool of any reported cell returns `rpc_error` after retries is **not
written**: the pool that failed to answer may have been the winner, and the remaining pools
would produce a figure that is low and looks ordinary.

## 7. What the forward window reports, and what it does not

The forward window reports `L` and `f_p` per cell per round, and nothing derived from them.

**No threshold, no boundary, no classification, and no trend claim is registered here.** After
this registration has produced its own window of data — not the calibration day — boundaries
may be derived and registered in a separate document with its own date. Registering them now
would be fitting them to the one day already seen.

## 8. What would make this wrong

- A published cell whose winning pool cannot be reproduced by a third party from public state
  at the recorded block.
- A counterexample to the §1.2 invariant: some choice of `m_A` that changes a winning pool.
- A cell reported as `no_liquidity` whose pool, re-quoted at the same block, answers.
- A round written despite an `rpc_error` in a reported cell.
- Published wording that claims the chain rather than the enumeration (§2.1).

## 9. Serialisation — canon `rhdepth-oneside-v1`

This series has **its own canon**. `rhdepth-v2` is untouched: no field of it changes, no
published byte of it changes, and its watermark is not affected. The two series share nothing
but the machine they run on.

Per-quote canonical line, joined with `|`, sorted, and prefixed by the canon string:

```
block | asset | quote | size_usd | pool | shares_offered_raw | shares_consumed_raw | amount_out_raw | status
```

`roundKeccak` is `keccak256("rhdepth-oneside-v1" + "\n" + "\n".join(sorted(lines)))`.

`shares_offered_raw` is the `s` of §1 step 3, identical for every pool in the cell;
`shares_consumed_raw` is what the pool took. The filled fraction of §1 step 7 is the ratio of
the two and is **not** a separate field: two fields that must agree are a place for them to
disagree.

Fields present in the record but **not** in the preimage — the enumeration windows, the
conversion pool, the per-pool mids, the fee at block, `m_A`, latency — are metadata. Adding a
metadata field does not change any hash. Moving a field into the preimage, or changing any
field above, ends this registration and starts a new one.

Every quote row carries its own `canon` field. Round records already do; on 2026-09-25 a
reviewer working from a copy of the published data read quarantined rows as current ones
because the quote file did not state its own canon and the directory name that did had been
lost in a copy. This series does not repeat that.

## 10. What this does not do

- It does not say what a position is worth. It says what one sale of a stated size returned
  against the pools enumerated, at one block.
- It does not forecast. A cell is a measurement of one block.
- It does not rank venues. The winning pool of a cell is recorded because a reader needs it to
  reproduce the figure, not as a recommendation.
- It does not measure what a router would achieve. See §1.1.
- It does not supersede `rhdepth-v2`, and it does not correct it.

## Fixing this document

Changing the statistic in §1, the enumeration method in §2, the cell set in §4, the failure
rules in §6, the preimage in §9, or any falsification condition in §8 ends this registration
and starts a new one with a new date. **This file is never edited.** The date on which it
first appears in the public repository is the evidence that it predates the window it is
evaluated on.
