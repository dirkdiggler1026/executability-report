# Findings

One line per finding, with the block it was measured at, the artifact that carries it, and the
command that reproduces it. Everything here is checkable without asking us anything.

**What this repository measures:** what a position actually realises when it exits - not the mark,
not TVL, not a price-impact quote. Same pinned block, both legs priced against the same state, a
size ladder, a failure class per row, and the raw reads shipped alongside.

---

## Tokenized equities

### F1 - The same underlying is not the same venue (Base, Coinbase-issued wrappers)

At pinned block `52175000`, two `NVDAc/USDC` pools differ by roughly **600x** on a USD 100 exit:
one returns **99.31%**, the other **cannot return more than 0.168%** - because that is all it holds.
The bound is an on-chain holdings bound (`balanceOf`), not a walk result. A cap sized from TVL or
from a 2%-impact figure sees neither the difference nor its direction.

- Artifact: `measurements/base-depth/` (README with both tables, DISCLOSURE, raw read logs)
- Reproduce: `python base_ladder.py --block 52175000` (twice) then `python publish_from_pair.py`
- Exact rows: `measurements/base-depth/base-depth-publishable-Y.json`

### F2 - Read failures look like values (the reason F1 needed a validated reader)

A failed `ticks()` read returned 0 - which the walk reads as "no liquidity change here" - and a
failed `tickBitmap` read returned a sentinel - read as "nothing initialised in this direction".
Four runs pinned to the same block hash disagreed on 7 of 43 rows, by up to **3.49x**; and the
majority across runs pointed at the **corrupted** value (3:1). Both defaults now raise instead of
defaulting, every read failure is recorded per (pool, size, fee, spacing, leg, selector), and a row
that failed to read is published as *having no number* rather than a wrong one.

- Artifact: `measurements/base-depth/DISCLOSURE.md`, `reads-Y1.json`, `reads-Y2.json`
- Drill: `drill_readfailed.py` (two arms; the arms must differ or the drill has no power)

### F3 - Method boundaries must not be published as asset properties

`exhausted` / `sentinel` / `iteration_cap` are our reader's boundaries, not facts about an asset.
They are recorded per row, and rows whose claim depends on a bitmap read are published with an
on-chain holdings bound as the claim instead.

- Artifact: `measurements/base-depth/README.md` (Panel A vs Panel B)

### F4 - xStocks have no on-chain enumerable registry (Monad)

The seven xStock tokens exist on Monad at byte-identical EIP-1967 proxy code, decimals 18 - but
every wrapped xStock reports `totalAssets() == 0`, no real pool was found, and no on-chain registry
could be enumerated (Monad's token list, Chainlink's feed directory, the proxy admin, DEX factory
enumeration: all negative). The token addresses came only from the issuer's off-chain API, made
checkable by cross-chain address identity (9,296/9,296 comparisons, 0 differences).

- Artifact: this file; reproduction notes in `docs/` on request
- Why it matters: an asset whose address cannot be derived on-chain cannot have its depth
  independently verified either

---

## Method notes (for anyone writing a v3 / CL reader)

- **A transport failure must never be a value.** Defaulting on error turns silence into a number.
  Raise, and record the failure against the row it touched.
- **Pin reads by block hash, not by block number** (`{"blockHash": ..., "requireCanonical": true}`).
  A backend that cannot serve that block then errors instead of quietly answering with another one.
- **Retry only to satisfy validation - never to agree with another result.** If the retry's stop
  condition mentions a comparison with another read, it is a vote, and voting selects the corrupted
  value when failures are biased.
- **Two-arm drills.** Every check needs an input that should fail and a control that should pass,
  and the two arms must differ; otherwise the check has no discriminating power even when it
  "passes".
- **A criterion needs a lower bound.** A check that iterates a set must assert the set is non-empty
  (or above a stated floor), or an input failure reports as a pass.
- **An artifact without a failure log has "provisional" as its ceiling.** If failures were not
  recorded, how much of the table was affected cannot be stated afterwards.

## Known gaps, stated rather than implied

- `measurements/base-depth`: rows whose legs cross more than one liquidity range are measured but
  withheld - multi-range accumulation has not been validated against a real swap (no suitable
  sample found in recent history).
- The round-trip composition (leg 1's output, minus fee, as leg 2's input, both against the same
  pinned state) is defined by the method, not validated by replay; each leg separately is.
- One earlier table (block `52170281`, published 2026-10-04) was produced before the read
  validation and is kept, with its reason, in `measurements/base-depth/DISCLOSURE.md`.
