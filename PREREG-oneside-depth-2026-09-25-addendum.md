# Addendum 1 to `PREREG-oneside-depth-2026-09-25.md`

**Written 2026-09-25, before the forward window opens at 00:00 UTC on 2026-09-26. No forward
data existed when this was written, and none was consulted.**

Nothing in §1, §9, or §8 of the registration changes: the statistic, the preimage, and the
falsification conditions stand exactly as registered. This addendum records a property of the
registered statistic that a dry run surfaced, and fixes how its sign is to be read.

---

## 1. `L` can be negative, and that is the definition working

`L := 1 − P / N`, with `N = s · m_A` and `m_A` the **median** of the candidate pools' mids.
The sale is quoted into every pool and `P` is the best proceeds. When the pool that pays best
is priced above the median, `P` can exceed `N` and `L` is negative.

Measured in the dry run of 2026-09-25 (block 72,352,396, no round written):

```
NVDA  pool mids 207.1899 / 224.8336 / 225.4917 / 225.559   median 225.1626
      best mid is +0.1761% above the median
      slippage at $100 is about 0.05%
      L = 0.05% − 0.176% = −0.13%      (the run reported −0.132%)
```

## 2. What a negative `L` means, and what it does not

```
It means      the best-paying pool is priced above the median of the pools enumerated.
              That is cross-pool price dispersion, and it is a real property of the chain.
It does not   indicate a profit. N is not money anyone paid; it is s × m_A, a construct whose
mean          only job is to turn a share count into a rung label.
```

**`L` is therefore renamed in all reporting from "one-sided loss" to "one-sided shortfall
against the median-priced notional".** The formula is unchanged; the name was wrong for a
quantity that can be negative, and a name that invites the reading "profit" is a defect in the
name.

## 3. Which part of `L` is the depth signal

The level of `L` carries the reference; the change across rungs does not, to first order.

```
L(N) = 1 − (P(s) / N)  ≈  1 − (p_best / m_A) · (1 − slip(s))

changing m_A    scales (p_best / m_A) and shifts every rung of the asset together
L(N₂) − L(N₁)  ≈ (p_best / m_A) · (slip(s₂) − slip(s₁))     <- the size-dependent part
```

So: **the spread of `L` across the ladder is the depth reading; the level of `L` is the depth
reading plus a dispersion offset.** Both are published; a reader is told here which is which.
For NVDA above, the ladder spread is `−0.024 − (−0.132) = 0.108 pp` — that is the cost of size,
and it does not depend on the median having been chosen.

## 4. The reader can also compute the per-pool figure, which is never negative

Every row carries `pool_mid_usd_per_share`. Slippage of the winning pool against **its own**
mid is therefore derivable from the published rows and is non-negative by construction:

```
own_mid_slippage = 1 − amount_out_usd / (shares_consumed_raw / 1e18 × pool_mid_usd_per_share)
```

This is not a new field and does not enter the preimage. It is stated here so that a reader
who wants a quantity that cannot go negative does not have to guess that the ingredients are
already in the file.

## 5. What this addendum does not do

- It does not change `L`, the preimage, the cell set, the enumeration method, or any
  falsification condition. The registration of 2026-09-25 stands and keeps its date.
- It does not introduce a threshold. §7 of the registration still registers none.
- It does not claim the dispersion measured in the dry run persists. One block, no round
  written, and it is calibration in the sense of §0.1.
