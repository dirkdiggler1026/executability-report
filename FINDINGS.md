# Findings — what has been measured here, and where each one lives

An index, not a summary. One entry per question, each pointing at the directory that holds
the measurement, the raw reads, and the limits. **No figure is restated on this page.** Every
number lives in exactly one list, next to the block it was pinned to; a number copied into a
second document is a number that can drift away from its list.

Subjects covered: executable exit depth for tokenized equities (Base, Robinhood Chain),
Uniswap v3 and v4 pool measurement, prediction-market order books, and the accounting
factors that sit between a wrapper token and the share it references.

---

## Tokenized equities on Base — exit depth

**[measurements/base-depth/](measurements/base-depth/)**

What a holder of a Coinbase-issued equity wrapper on Base (chain 8453) actually gets back
on exit, measured pool by pool at a single pinned block, with a size ladder and a failure
class on every row.

The finding worth the click: **two pools for the same pair, at the same block, answer the
same question differently by orders of magnitude** — and the two answers are published as
*different classes of evidence*, not as two numbers in one column. One is a measured path
through the pool's liquidity. The other is an upper bound derived from what the pool holds,
because a pool cannot return more than its own balance; the walk figure is printed beside
that bound, marked, and is not the claim.

Method, in the words that make it checkable: reads pinned by block **hash** with
`requireCanonical: true`, both legs of each round trip priced against the same pinned state,
the composition rule stated rather than implied, two independent runs required to agree
bit-for-bit before a row is publishable, and rows that failed a read published as failures
with their reason instead of dropped. `DISCLOSURE.md` in that directory carries what is
withheld and why.

## Tokenized equities on Robinhood Chain

**[measurements/oneside-depth/](measurements/oneside-depth/)** — one-sided exit cost as an
hourly series, which is the half a round-trip figure hides. These are the artifacts the
report's cards cite by name, published so that a card points at a file a reader can open.

**[measurements/accrual-multiplier/](measurements/accrual-multiplier/)** — the per-asset
factor in the transfer logs, and what it does to any accounting that assumes one token is
one share. Includes when it last moved, bounded.

**[measurements/issuer-feed/](measurements/issuer-feed/)** — three public issuer endpoints
read against the chain. The multiplier is published three ways; *when it changes* is not.
That asymmetry is the finding.

**[measurements/tsv-volume/](measurements/tsv-volume/)** — September 2026 volume for nine
symbols: the numerator of the ratio capped by §II.F of the tokenized-stock exemption, with
the denominator explicitly absent rather than estimated.

## Across issuers

**[measurements/wrapper-multipliers/](measurements/wrapper-multipliers/)** — the same
underlying, two issuers, two different multipliers. Reproducible from the script in the
directory.

## Negative results, published as such

**[measurements/index-priced-test/](measurements/index-priced-test/)** — a 24-hour oracle
cannot be the reference for a 30-minute comparison. Published because the design fault is
the useful part.

---

## The recurring series

- **Daily:** `data/<date>/` — one row per measurement, a canonical hash per round, checksums.
- **Weekly:** [weekly/latest.json](weekly/latest.json) — a machine-readable depth figure per
  asset and size. See the cadence note in the top-level README for what this feed does and
  does not yet guarantee.

## How to cite, and how to correct

The citation format — stable block plus volatile block — is in the top-level
[README](README.md), along with the contact address and the correction policy. Corrections
are published whoever is relying on the figure, and the report page carries a numbered
archive of this project's own instrument failures: what each one was, how it was caught, and
which side of publication it landed on.

If a number here is wrong, the useful thing you can do is say so.
