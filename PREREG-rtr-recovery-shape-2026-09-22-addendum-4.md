# PREREG-rtr-recovery-shape-2026-09-22 — addendum 4

**Date** 2026-09-25. Corrects §10 and addendum 3. The measurements cited here are artifacts
(`depth_fixed.json`, `one_sided.json`); where no artifact exists, no number is quoted.

## 1. `(1−f)²` is a lower bound, not a ceiling

For a same-pool round trip inside one range, with `k = net₀·u₀/L`:

```
buy    net₀ = in·(1−f)      u₁ = u₀/(1+k)            out₁ = L·(u₀−u₁)
sell   net₁ = out₁·(1−f)    u₂ = u₁ + net₁/L         out₀ = L·(u₂−u₁)/(u₁·u₂)

⇒ recovery = out₀/in = (1−f)² / (1 − f·Δu/u₀)   >   (1−f)²
```

The second leg's fee is charged on the position actually bought, which is worth less than the
notional, so the total fee is below `2f`. The excess over `(1−f)²` is therefore a measurement of
the buy leg's price movement — not an error, and not noise.

§10 calls `(1−f)²` "the arithmetic **ceiling**". It is a **floor**.

## 2. "Below the ceiling" means the pool did not fill

§10 reads:

> The measured figures sit below those ceilings, which is what price impact on top of the fee
> looks like.

Both halves are wrong. Price impact inside one pool is undone by the leg that retraces it, so it
moves the figure **above** the floor, not below. A figure below the floor is evidence of
**partial fill** — or, in the production construction, of the effect described in §3.

Measured across three fee levels, every **fully-filled** cell sits above `(1−f)²`, matching the
expression in §1 to four decimals. No artifact for that run has been published, so no numbers are
quoted here; §1 is algebra and stands independently of it.

## 3. The published figure is a static-book round trip, and the label should say so

The collector quotes both legs with independent calls against the same pinned block: it buys at
the best pool for that size, then sells the amount actually bought back through that same pool —
but the sell leg is priced against the book **as it was before the buy**.

```
realised (impact-retracing)  ≈ (1−f)², essentially size-independent   ⇒ cannot see depth at all
static book (what we publish) ≈ 2× one-sided impact + 2× fees,
                               degrades with size                     ⇒ is the depth signal
```

So the published numbers are right and the **name** is wrong: the column measures the cost of
trading against a static book. Recorded on the report page as **error 13**. The fix is a label and
two further columns — filled fraction, and one-sided slippage — not new numbers.

## 4. A round trip blends two directions; a forced seller walks one

Same pool, same pinned block, $100,000:

```
buy side   1.7354%        sell side   0.1214%        14.3× asymmetry
```

(artifact `one_sided.json`; the liquidity is lopsided.)

A round trip averages the two directions. A liquidator faces one of them. That they can differ by
an order of magnitude **in the same pool at the same block** is the measured case for replacing
the field rather than extending it.

Measured one-sided instead — best venue among all enumerated venues, block **72,245,711**
(`0x7d5572108c50b1bab0…`), 36 cells, 0 failures (artifact `depth_fixed.json`) — loss against
notional:

| asset | $100 | $1,000 | $10,000 | $100,000 | winning pool at $100,000 |
|---|---|---|---|---|---|
| AAPL | 0.047% | 0.051% | 0.087% | 0.609% | `0xaae0d815ee…` fee 500 |
| AMC | 0.436% | 0.483% | 0.954% | 4.537% | `0xaa34fea710…` fee 3000 |
| GME | 0.192% | 0.214% | 0.438% | 1.329% | `0xe9713f453a…` fee 10000 |
| GOOGL | 0.032% | 0.083% | 0.126% | 0.576% | `0x34d0dc122c…` fee 500 |
| NVDA | 0.012% | 0.029% | 0.063% | 0.116% | `0xd4eb21209c…` fee 500 |
| QQQ | 0.088% | 0.090% | 0.114% | 0.354% | `0xd60a5d14db…` fee 500 |
| RDDT | 0.319% | 0.420% | 0.926% | 2.048% | `0xa8744e76ae…` fee 10000 |
| SPY | 0.001% | 0.014% | 0.055% | 0.409% | `0x38453c1156…` fee 150 |
| TSLA | 0.128% | 0.226% | 0.386% | 1.541% | `0xf4acdaeeb7…` fee 3000 |

**Caveat carried with the table:** "best among all enumerated venues" assumes routing can reach
both the USDG-quoted and the WETH-quoted pools at once. A single venue routes only its own set, so
its own disclosure would show a considerably worse number. **That gap is the argument**, not a
defect of the table.

## 5. Addendum 3's scope sentence is too wide

Addendum 3 says the figures were *"quoted against every initialized QQQ/USDG pool"*. They were
quoted against every pool in **one venue's factory**. At least three further venue classes exist
on this chain, two of them behind other factories, and the fee tiers are not a fixed menu. See
**error 12** on the report page. We do not claim the enumeration is complete; what we can state is
which windows we searched and by what criterion.

## 6. A capacity duration that disagrees with the filed comment

Addendum 3 says capacity *"moved across two orders of magnitude in seven weeks"*. The filed
comment letter says *"about thirty-four times in nineteen days"* for the same series. Both cannot
be right. This needs reconciling before either figure is relied on.

## What this does not change

§10's conclusion — that the fee is the part no execution technique can lift — stands for a given
pool. What changes is that the fee is not the whole of what a seller loses, and that a round trip
is the wrong statistic to ask for in the first place.

## The landing point

Not "we measured better". **Both numbers are true, and the disclosure can only see the worse one.**
