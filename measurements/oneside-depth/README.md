# One-sided measurements — the artifacts the cards cite

Published 2026-09-26. Five JSON files, ~65 KB total. They are here because two demo cards cite
them by name: a card that points at a file only its author can open is a claim, not a citation.

**Scope note, stated once and meant everywhere:** the venue sets in these files were found by
enumerating each asset's `Transfer` counterparty flow, not by matching a factory pattern. That
method finds more than the old one did and it is still **not claimed to be exhaustive**.

## The files

| file | block(s) | what it is | sha256 |
|---|---|---|---|
| `depth_fixed.json` | 72,245,711 | nine assets × four rungs, best route per rung | `2edb84c7be45b4de3dc9c2521696734303b82ef8ca4423e554bc6e32cf3712d0` |
| `v3_nonserial_12cells.json` | 54,088,399 · 61,129,566 · 70,427,772 | 3 blocks × 4 sizes, same-pool round trip, **held book** | `5c179f852d1bdebb021f8a28531604bb8d07fcb9a65618fad58b3be909b98813` |
| `one_sided.json` | 54,088,399 · 61,129,566 · 70,427,772 | the same blocks and the same pool, both directions separately | `a766135448b569374f7bf3dfe3cda521486f56fb8cd6659cf2a4f8e192571a3a` |
| `usdg_onesided.json` | 72,236,870 | 108 rows: 9 assets × 4 rungs × 27 USDG-quoted pools | `e4710bab98156a47e0c8507da992fbcfdd23752293c37f4fd014fad82ec4353a` |
| `weth_onesided.json` | 72,235,716 | 56 rows: 9 assets × 4 rungs × 14 WETH-quoted pools | `004233ae5d0dc20d4a9ed207553978021d33804d2ff7864f9c4b7c3aa36d489c` |

Block hashes, from the files themselves:

```
depth_fixed.json            0x7d5572108c50b1bab07aef03ab507761049b99eff60691a51390ef5e0c35a7fd
v3_nonserial_12cells.json   54088399 → 0x1ab9aed1e89e48c08350fd4f090a2949f438b3e2218f473b9a035a29a907f14f
one_sided.json              54088399 → 0x1ab9aed1e89e48c08350fd4f090a2949f438b3e2218f473b9a035a29a907f14f
usdg_onesided.json          0x3c7b19a17395b12c95470a0cd8f0d6e5e1dfc90926de778e20d71811c67e64c9
weth_onesided.json          0x03b8390e15d66002c41047628936335ab05d8006c57f65839a14961225972a0a
```

⚠️ **Units.** `v3_nonserial_12cells.json` stores **fractions** — `0.9989986200` is 99.89986200%,
and the report page prints it as 99.8999%. `one_sided.json` stores **percentages** —
`slippage_pct = 0.130940806` is 0.130940806%. The two files sitting next to each other with
different conventions is a trap that has already caught one reader (this one), so it is written
down rather than left to be discovered.

## What the two generations measure

`v3_nonserial_12cells.json` and `one_sided.json` are one pool: `0xd60a5d14db690b7afad71f76b108071d7175597d`,
fee 0.05%, a standard UniV3-style pool. The name says *non-serial*: the sell leg is quoted against
the book as it stood **before** the buy, so the buy's price impact is not carried into the sell.

That construction is the point. Its cost is the buy-side cost **plus** the sell-side cost, which is
what `one_sided.json` measures separately. At block 54,088,399, QQQ, $100,000:

```
buy side            0.133016%
sell side           0.130941%   (the side a forced seller walks)
sum                 0.263957%
round trip, measured 0.263675%   ← 0.263956674 - 0.26367545 = 2.8e-4 pp, 0.107% relative
```

So a round trip is charged in both directions. A liquidator sells; it walks one side. Read the two
files together and the difference between them stops being a mystery and becomes arithmetic.
`one_sided.json` carries its own note for this: `slippage_pct` is the sell side, the side a
liquidator faces.

## What these files do not say

* They are **single block snapshots**, not series. Nothing here is a time series and nothing here
  supports a trend. The registered series with a forward window is `rhdepth-oneside-v1`
  (registered 2026-09-25, window opened 2026-09-26 00:00 UTC); its records live under `data/`.
* `depth_fixed.json` ranks by **absolute USD proceeds for an identical share count**; the
  reference mid labels the rung and is not the executing pool's mid. A cell can therefore sit a
  hair above what the executing pool's own mid would give. Its `rungs[]` carry `pool`,
  `pool_mid_usd`, `fee` and `quote` per rung so this is checkable per cell.
* The 27 and 14 pool sets in the last two files **do not overlap at all** (intersection 0): they
  are the USDG-quoted and WETH-quoted scans, and the file names mean what they say — the pool the
  spine card names (`0xd60a5d14…`, fee 0.05%) appears in the USDG file and not in the WETH one.
* **The enumeration itself is not reproducible from these files.** They record which pools were
  quoted and what came back; they do not contain the log scan that found the pools. That is the
  part a third party still cannot re-run, and pretending otherwise would be the same defect this
  project exists to document.
