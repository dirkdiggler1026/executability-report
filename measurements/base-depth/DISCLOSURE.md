# Disclosure — Base exit-depth

- Pinned block `52170281`. The pool set is the set on **that block**; the same pool may have no liquidity on another block.
- Script hashes (sha256, first 16): `base_ladder.py` `9c6c2488c9c78282…`, `tickwalk_b.py` `c1b10b9f5a2beff0…`, `base_discovery.py` `8cf422aa45964cfe…`
- Sealed rows: 24. Reasons: a leg traversed more than one liquidity range (multi-range accumulation is not replay-validated); the round-trip composition is defined by the canon, not replay-validated.
- Rows whose answer depends on a bitmap read are published **with the holdings bound as the claim**; the walk figure is shown alongside, marked, and is not the published fact.
- **Open, unadjudicated:** two runs at the same pinned block returned different tick-bitmap reads on tick-heavy rows. A quiet probe did not reproduce a silent fallback to `latest`; a load-triggered fallback is not excluded. Until this is adjudicated (block-hash-pinned reads, or a storage proof anchored to the block hash), Panel A's claim stays as narrow as worded above.
- Method boundary, not an asset property: `exhausted` / `iteration_cap` / `sentinel` termination reasons are recorded per row.
