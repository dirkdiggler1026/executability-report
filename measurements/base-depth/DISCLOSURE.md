# Disclosure — Base exit-depth

**Canon `basedepth-v3-1` at pinned block `52175000`**, block hash
`0xbdc05b988f40295dd6e28b987bdfa41ef3e6e0f89a31fcc32724cf5292dcc13d`, reads pinned by that hash with `requireCanonical`. No date appears in this
file on purpose: the hash is the time anchor, and anyone can resolve it with
`eth_getBlockByHash` rather than trusting a date copied in here. The endpoint read was
`https://mainnet.base.org`.

## What this run established

- **38 of 43 rows** read cleanly in both of two independent runs and were
  **identical across them**, with **0 disagreements**. Rows that were not identical in both
  runs are not published.
- **18 rows are publishable** — Panel A 15 (claim: the measured curve),
  Panel B 3 (claim: the on-chain holdings bound). **20 rows are sealed.**
- A failed read raises instead of returning a default, and every read failure is recorded per
  (pool, size, fee, spacing, leg, selector).

## What this run did not establish

- **5 rows have no figure.** Those rows issue the most reads and failed with
  HTTP 429 on `tickBitmap(int16)` in each run, and the two runs lost different rows. Their
  absence is a property of our read budget in that run, not of the pool. The rows:

  | pool | size | run 1 | run 2 |
  |---|---|---|---|
  | `0x60661b31…` | 100000 | read_failed | absorbed_in_range |
  | `0x8634ee41…` | 10000 | sentinel | read_failed |
  | `0x97f35d1e…` | 10000 | absorbed_in_range | read_failed |
  | `0x97f35d1e…` | 100000 | read_failed | read_failed |
  | `0xa0790118…` | 100000 | read_failed | sentinel |
- **Two runs agreeing on the same block hash cannot exclude a deterministic degradation.** A
  fallback triggered by load would make both runs give the same answer. Excluding it needs a
  check that does not depend on the endpoint agreeing with itself — a storage proof anchored
  to the block hash — and that has not been done.
- **Multi-range accumulation is not replay-validated** (`multi_cross_validated`:
  `false`), and **the round-trip composition is not replay-validated**
  (`roundtrip_composition_validated`: `false`). Each leg was
  checked separately against real swaps; their composition was not. Rows depending on either
  are sealed rather than published.
- Termination reasons (`exhausted` / `iteration_cap` / `sentinel`) are recorded per row. They
  are a boundary of the method, never a property of the asset.

## The evidence files beside this table

reads-Y1.json and reads-Y2.json are a sample of the reads, not an archive of them. Each run issued about 2,450 calls and each file keeps the first 400, and each entry keeps the head of the response rather than the whole response. They are enough to show which rows failed and why, and they are not enough to recompute this run's figures. The reads of this run cannot be recovered: what was not kept at the time does not exist now.

The table can be recomputed by re-reading the chain at block 52175000 by block hash, which needs an endpoint that still serves that block: the provable window on this chain is about 30 days and slides. Past that, this run is not independently recomputable, and no file here changes that.

From the next run on, the complete read list is kept, each entry carrying the request parameters and the sha256 of the full response, with one sha256 over the whole list, and the full responses shipped separately. That makes a later run checkable against its own logs for having been unaltered - anchored in git history, which is a weaker claim than re-reading the chain and is stated as the weaker claim.

## Funding

This measurement was unfunded: no party paid for it. Refused, in advance rather than on request: the issuer of any asset measured here, or any party acting for one; any party whose own parameters this measurement would be an input to. When a measurement is funded, the funder is named in this field and printed here above the table it paid for. The fee buys the measurement and not a conclusion, and a result that is unflattering to whatever it is attached to is published as measured.

Licence: code/ is Apache-2.0 (LICENSE covers code/ only); the measurement data and the report are CC BY 4.0 (data/LICENSE). Attribution is the only condition. Nothing is gated and there is no subscription tier.

## Provable window

`base-8453`, about `1283204` blocks, measured
`2026-10-01` and marked derived. Verifying anything older than that window needs an
archival endpoint.

---

Earlier statements about this measurement, what was superseded and why, and one promise that
was made and not kept, are in [HISTORY.md](HISTORY.md). Nothing in this file is history: it
describes the current run only. Instrument properties measured on a different run pair are in
[INSTRUMENT.md](INSTRUMENT.md).
