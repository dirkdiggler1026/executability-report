# Third addendum to the absolute-floor pre-registration (2026-09-14)

Refers to `PREREG-floor90-2026-09-14.md` (`0150937253e6…929e`), addendum 1
(`149424d6ddd0…250c`) and addendum 2 (`707a99c5456d…d4a3`). Written 2026-09-14 UTC, before the
forward window opens. It corrects an argument in addendum 2 §6 and pins the input that section
declined to pin.

## 7. Section 6 of addendum 2 claimed more than it argued

Addendum 2 §6 left block selection unpinned, on this reasoning:

> ...that displacement does not systematically raise or lower recovery, **so it cannot make a
> falsifier easier or harder to violate.**

The first half stands: a second of chain time does not systematically move recovery. The second
half does not follow from it. "No direction" covers only the **direct** effect on the recovery
value. It says nothing about the causal path that addendum 2 §5 exists to close:

    pinning to tip  ->  maximum reorg exposure for the pinned block
      ->  an unretrievable pinned state is an rpc_error
      ->  bounded retry against the same block, then the whole round is dropped
      ->  fewer rounds  ->  fewer episodes  ->  falsifier 1 easier to pass

Block selection sits **upstream of the drop policy**, and the drop policy is pinned precisely
because of this path.

Worse, the two sections argue opposite sides of one question:

> §5: The observable pressure runs the other way ... **but the direction of the pressure is not a
> reason to leave the input unwritten.**
> §6: ...it has no direction, **so it cannot make a falsifier easier or harder to violate.**

A registration whose value rests on being checkable cannot hold both.

## 8. What the collector actually does

Verified in the collector source, since the argument above depends on it:

- The block is read once per round from `eth_blockNumber` and **every** quote in that round uses
  it. There is no re-pinning path anywhere.
- A quote that fails with `rpc_error` is retried **against the same block**; when the bounded
  retry is exhausted the entire round is dropped and nothing is written.
- A round takes 60 to 85 seconds while the chain advances roughly 700 blocks, so from its second
  call onward a round is already reading historical state.

So block selection feeds the drop channel of §5. It does **not** move rounds off the sampling
grid of §4: a dropped round is absent, not displaced.

## 9. Block selection is pinned

The trigger is evaluated only on rounds whose block is the value returned by `eth_blockNumber`
at sampling time, **with no lag constant**.

Measured width of this effect in the calibration window is **zero**: no round was dropped in ten
days. The direction of a plausible change (pinning to tip minus N for reorg safety) is
**conservative** — it would drop fewer rounds and make the rule look worse, not better.

**Neither of those is a reason to leave it unwritten.** That is §5's own rule, applied to the
input §6 exempted from it.

## Why this is still an addendum

The floor, the cell set, the episode definition and the three falsification thresholds are
unchanged. This addendum removes a freedom that addendum 2 left open and corrects an argument,
before any round the rule will be evaluated on exists.

## Status of this file

Never edited. Its git commit timestamp is the evidence that it predates the window it applies
to.
