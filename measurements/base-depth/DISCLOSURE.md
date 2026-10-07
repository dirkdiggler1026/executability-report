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

## Provable window

`base-8453`, about `1283204` blocks, measured
`2026-10-01` and marked derived. Verifying anything older than that window needs an
archival endpoint.

---

Earlier statements about this measurement, what was superseded and why, and one promise that
was made and not kept, are in [HISTORY.md](HISTORY.md). Nothing in this file is history: it
describes the current run only.
