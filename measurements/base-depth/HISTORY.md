# History — Base exit-depth

Everything in this file is history, in the tense it was written. The current run is described in
DISCLOSURE.md; this file records what was said earlier, what was superseded and why, and one promise
that was made and not kept.

## 2026-10-04 — first table, at block 52,170,281

- Pinned block `52170281`. The pool set is the set on **that block**; the same pool may have no liquidity on another block.
- Sealed rows: 24. Reasons: a leg traversed more than one liquidity range (multi-range accumulation is not replay-validated); the round-trip composition is defined by the canon, not replay-validated.
- Rows whose answer depends on a bitmap read are published **with the holdings bound as the claim**; the walk figure is shown alongside, marked, and is not the published fact.
- **Open, unadjudicated:** two runs at the same pinned block returned different tick-bitmap reads on tick-heavy rows. A quiet probe did not reproduce a silent fallback to `latest`; a load-triggered fallback is not excluded.
- Method boundary, not an asset property: `exhausted` / `iteration_cap` / `sentinel` termination reasons are recorded per row.

## 2026-10-06 — why that table was provisional

Four runs pinned to the same block hash at a later block (`52171860`, `0x507273064355aca42df816f523019f0e4f49129f0c7190d738dd39313a1ed7b5`, `requireCanonical: true`) disagreed with each other on **7 of 43 rows** in at least one recorded field, and on the recovery figure itself in 3 of them. The cause is in my own reader, not in the chain or the endpoint: a failed `ticks()` read returned 0 and a failed `tickBitmap` read returned a sentinel, so a transport failure silently read as "no liquidity change here" or "nothing initialised in this direction". The largest disagreement was a factor of 3.49 on one row (`NVDAc/USDC` fee 3000 at $100,000: 5.646941% vs 19.712807%), and the lower value is the corrupted one, so a majority vote across runs would have selected the wrong number. A third default has the same shape in the identity layer: a failed `token1()` read returned the zero address while the row kept its label.

Those runs were not of the table below — they were of a later block — so the inference was indirect: the same reader produced that table, and that run carried no read-failure log, so which of its rows were affected could not be stated, only that small, low-crossing rows have the smallest exposure.

**Superseded by the replacement record of 2026-10-06 below.** At the time it was written, every figure in the 2026-10-04 table was to be treated as provisional.

## 2026-10-06 — replacement

The table published on 2026-10-04 at block 52,170,281 was produced before the read validation. It was replaced by a run at block 52,175,000 with that validation in effect: reads pinned by block hash with `requireCanonical`, a failed read raising instead of defaulting, and every read failure recorded per (pool, size, fee, spacing, leg, selector). In that run the row set was 43: 38 rows read cleanly in both of two independent runs and were identical across them (0 disagreements), and 5 rows failed to read in at least one of the two runs — recorded as having no number rather than a wrong one.

The 2026-10-04 artifacts remain in this directory as `base-ladder.json` and `base-ladder-gated.json`, with 19 publishable rows (Panel A 15 / Panel B 4) and 24 sealed. The current README is generated from the validated run and does not carry those numbers.

## 2026-10-04 — a promise made and not kept: `margin_to_next_tick`

The README of that date promised: "A per-row `margin_to_next_tick` will be added so the width of that claim is visible." The 2026-10-06 rewrite dropped the sentence, and the field does not exist anywhere in the tree. Panel A's claim rests on the next initialised tick not being closer than the absorption point, and the **margin** in that sentence is what a reader cannot see: where it is small, those rows are fragile in a way the table does not show. Delivering it is a measurement, not an edit — it needs the next measurement block. Until then this stands as a promise that was made and not kept, rather than one quietly deleted.

## 2026-10-07 — my own wording about the larger tiers was wrong

A sentence of ours described state the data did not license: it said the larger tiers were "measured but withheld". That is accurate for the sealed rows and not for five rows, which have **no figure at all** — those rows issue the most reads and failed with HTTP 429 on `tickBitmap(int16)` in each run, and the two runs lost different rows. Their absence is a property of our read budget in that run, not of the pool. The wording was corrected in place on the forum where it appeared, a reply was posted so the correction is visible rather than silent, and the corrected statement is in DISCLOSURE.md.

The lesson, which is the same error in the other direction from one we had guarded for a long time: saying "there is" when there is none is as wrong as saying "does not exist" when it was not observed. The artifact said only `read_failed`; "measured but withheld" was an inference about state that the data did not make.