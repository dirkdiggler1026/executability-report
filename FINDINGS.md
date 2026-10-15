# Findings — what has been measured here, and where each one lives

An index, not a summary. One entry per question, each pointing at the directory that holds
the measurement, the raw reads, and the limits. **No figure is restated on this page.** Every
number lives in exactly one list, next to the block it was pinned to; a number copied into a
second document is a number that can drift away from its list.

Subjects covered: executable exit depth for tokenized equities (Base, Robinhood Chain), the
pre-expiry exit on a Pendle principal-token market, Uniswap v3 and v4 pool measurement,
prediction-market order books, what a public endpoint still serves and for how long, and the
accounting factors that sit between a wrapper token and the share it references.

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

## Pre-expiry exit on a Pendle PT market

**[measurements/orbio-pendle/](measurements/orbio-pendle/)** — what selling a principal token
into its own market returns before the market expires, captured hourly because on that chain the
state is gone minutes later and an expiry cannot be re-read after the fact.

The claim is deliberately isomorphic to the Base work: proceeds over the market's **own pre-trade
marginal quote** for the same size at the same block, with nothing from outside the market on
either side. PT's face value is computed too and labelled as a *second* quantity, never the
claim, because it climbs towards full value as expiry approaches whatever happens to the book.

**The finding worth the click is a correction to that caliber, made after it was settled.** The
claim is not clock-free either: the curve's scale parameter carries the time to expiry, so the
measured recovery rises as expiry nears with nothing happening to the book at all. Four captures
spanning most of four days, in a market that emitted no event in that window, show the measured
figure moving while a column recomputed at one fixed reference clock does not move at all. So a
single capture's recovery is a fact about its block, and **a series of them is not a depth
series** — which is the exact error the caliber had been chosen to avoid, one level up.

Two limits travel with every figure there, in the artifacts rather than here. The gate that says
"two runs agreed" is on the **read**, not on the arithmetic: the curve is closed-form over one
state, so running it twice agrees by construction and would be the emptiest check in this
repository — what is run twice is the capture of the same pinned block. And nothing in that
directory has been validated against a trade anybody actually made: the market has been dormant,
so every figure is the published formula evaluated on an archived state, and says so.

## Event logs of two PT markets, kept before they were needed

**[measurements/pendle-market-logs/](measurements/pendle-market-logs/)** — the raw logs both
markets have emitted, archived with digests, decoded by nothing.

They exist because a counterfactual quote can only ever be checked against a trade somebody
made, and those trades survive only as events. The retention claim the directory makes is the
narrow one: logs *came back* from a given depth, so the node serves them at least that deep. The
ranges that came back empty establish nothing, and the record says so — an empty range is
equally consistent with the market not existing yet, with no events, and with a dropped log
index that answers empty rather than erroring.

## What a public endpoint still serves, and for how long

**[measurements/rh-retention/](measurements/rh-retention/)** — state and events are retained on
different schedules, so a sentence about "this chain" is almost always a sentence about one of
them. A reader pointed that out; it is the first error in this project caught from outside it,
and the claim is now read from a re-runnable probe instead of being held as a literal.

The probe reports three things under three names that cannot be read as each other: **proven**
(rows actually came back from that depth), **answered** (the query returned without error, which
a node that has dropped its index can also do), and **refused** (a timeout, or one of the
endpoint's two query caps — neither of which is retention). State is reported as a bracket,
deepest served and shallowest pruned, because "gone by N" and "survives to N" are different
claims. And the artifact carries the chain's **block time, measured over three spans in the same
run with an agreement test**, because a depth in blocks only becomes minutes through a unit — and
this project has already converted this chain at the wrong unit once and been wrong by roughly
twenty times.

## Across issuers

**[measurements/wrapper-multipliers/](measurements/wrapper-multipliers/)** — the same
underlying, two issuers, two different multipliers. Reproducible from the script in the
directory.

## Negative results, published as such

**[measurements/index-priced-test/](measurements/index-priced-test/)** — a 24-hour oracle
cannot be the reference for a 30-minute comparison. Published because the design fault is
the useful part.

## Methods, generalised past this project

**[SILENT-DEFAULTS-NOTE.md](SILENT-DEFAULTS-NOTE.md)** — how a reader against Uniswap v3-shaped
state produces clean, plausible, repeatable wrong answers: failed reads that return a legal
value, a length check off by the prefix, why pinning a block number is not reproducibility, why
"retry until two runs agree" selected the wrong number here, why naming the round-trip
convention has to precede writing the formula, and the four ways a drill can report green while
testing nothing. Written for anyone building the same kind of reader.

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
