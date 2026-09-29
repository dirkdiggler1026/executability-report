# Addendum 2 to `PREREG-tsv-volume-cap-2026-09-28.md`

**Written 2026-09-28, still before the run.** No numerator, denominator or ratio exists, and
the collecting machine holds no volume artifact. This addendum replaces §2 ① of the
registration, because a measurement taken while preparing the run showed the assumption behind
it was the wrong shape — not wrong in value, wrong in kind.

It also registers a test, with its criteria, **before the data that would answer it is looked
at**. The data already exists in this repository; it has not been read for this purpose.

---

## 1. What §2 ① assumed, and why it cannot stand

The registration treated the token:share ratio as an unknown *constant*, and handled it as a
two-branch sensitivity: "X% if one token is one share; 10X% if one token is one tenth".

It is not a constant. Each stock token emits, on **every transfer**, an event carrying two
`uint256` values whose ratio is identical across every event at a given moment, differs by
asset, and moves in **steps**:

```
topic0  0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802
data    [0] = the transferred amount   (verified equal to the recipient's post-transfer
              balanceOf at an archive endpoint, for a mint into an empty address)
        [1] = a second value, >= [0]

measured 2026-09-28, [1]/[0], median over every event in the sampled window, zero spread:
        SPY   1.001717991   +17.180 bp     pays a dividend
        QQQ   1.000700791    +7.008 bp     pays a dividend
        AAPL  1.000566080    +5.661 bp     pays a dividend
        TSLA  1.000000000     0.000 bp     pays none
        RDDT  1.000000000     0.000 bp     pays none
        (AMC, GME, GOOGL, NVDA: too few events in the windows sampled to report)
```

Every payer is above 1, every non-payer is **exactly** 1, and the three payers rank in the
order of their dividend yields. The QQQ value was 1.000000000 on 2026-09-19 and 2026-09-21,
and 1.000700791 from 2026-09-22; a bisection places the change between block 69,183,271
(2026-09-21 23:14 UTC) and block 69,263,499 (2026-09-22 01:28 UTC).

## 2. Status labels, per §5 of the registration

```
MEASURED     the event exists on every transfer; the two values; their ratio; that the ratio
             is uniform across events at one moment, differs by asset, is exactly 1 for the
             two non-payers sampled, and stepped once for QQQ inside a 2 h 14 min window.
INTERPRETED  that the ratio is a dividend accrual index. The evidence is the payer/non-payer
             separation, the yield ordering, and the step shape -- strong, and still an
             interpretation.
OPEN         whether [1]/[0] IS the token:share ratio. It could be an internal accounting
             unit that happens to track distributions. Nothing on chain says which, and the
             contracts declare no ratio (sharesPerToken, underlying, exchangeRate and the
             rest are all absent).
```

🔴 **Not claimed:** that this design is novel. Accrual-style wrappers are not new in this
field. What is measured here is this chain, per asset, on chain, with non-payers landing on
exactly 1 — and that we have not seen it published.

## 3. Replacement for §2 ①

> **① UNIT.** The denominator is a share count, so the numerator must be one. The token count
> is **not** a share count: each token carries a per-asset index, observable on chain, that
> steps. The numerator is therefore computed as
>
> ```
> shares(asset, block) = Σ token_amount × index(asset, block)
> ```
>
> with `index` read from the transfer event at, or immediately before, each block rather than
> assumed. Where the index cannot be read for a block, the row is left empty and counted in a
> coverage line — it is not back-filled with 1.
>
> **The index is applied as MEASURED; the claim that it converts tokens to shares is OPEN.**
> Every published ratio therefore carries both figures: the raw token count and the
> index-adjusted one, with the difference stated. At today's values the two differ by under
> two basis points for the assets sampled, so the choice does not change any order of
> magnitude — which is a reason to report both rather than a reason to ignore it.

The two-branch 1:1 / 1:10 sensitivity registered in §2 ① is **withdrawn**: it was an answer to
a question that is not the one the chain poses.

## 4. A test, and its criteria, written before the data is read

**Question.** Does the market price the index, or is it an accounting quantity only?

**Why the obvious test does not work.** "Did the pool price jump 7 bp at the step" cannot be
answered: 7 bp is far below QQQ's ordinary price movement over the 2 h 14 min the step is
bracketed in. A test whose signal is smaller than its noise returns nothing, whichever way the
world is.

**The test that has power.** Compare the token against the chain's own oracle for the same
asset, and carry a control that cannot move for this reason:

```
R(asset, t) = pool mid (USD per token)  ÷  Chainlink feed answer (USD)

  Robinhood QQQ / USD   0x80901d846d5D7B030F26B480776EE3b29374C2ae   subject
  Robinhood TSLA / USD  0x4A1166a659A55625345e9515b32adECea5547C38   control, index is 1.000000000

data     rhdepth-v2, already published, one round every 30 minutes; data/2026-09-21 and
         data/2026-09-22 bracket the step. Oracle answers read at the same pinned blocks.
window   at least 12 rounds either side of block 69,183,271–69,263,499.
```

```
REGISTERED READINGS
  R(QQQ) steps up by ~7.0 bp AND R(TSLA) does not      ⇒ the market prices the index
  neither steps                                        ⇒ the index is accounting only, and
                                                         "token price vs share price"
                                                         comparisons must subtract it
  both step                                            ⇒ something else moved (oracle,
                                                         quote asset); the test says nothing
                                                         about the index and is reported as
                                                         inconclusive
  R(QQQ) steps by materially more or less than 7.0 bp  ⇒ inconclusive; a partial or
                                                         coincident move is not evidence for
                                                         the index
```

The control is the point. "QQQ moved" on its own establishes nothing, for the same reason the
crypto feeds are a control in the oracle-staleness measurement: without something that cannot
move for the reason under test, a move is not attributable.

**The data for this test exists and has not been read for it.** That is why the criteria are
here, in a dated file, rather than in the write-up.

## 5. What this addendum does not do

- It does not change the symbol set, the pool readings, the window, the direction rule, the
  attribution limit, or §3-as-amended-by-addendum-1.
- It does not resolve the OPEN dependency. It replaces a guessable constant with a measurable
  quantity, which is a different thing from knowing what the quantity means.
- It does not assert that any published figure of ours is affected. The depth statistics are
  ratios of proceeds to notional in which the unit cancels, so the index does not enter them;
  that is stated here so the absence of corrections elsewhere is on the record as checked
  rather than as overlooked.
