# Base exit-depth recheck — block 52,367,749

_Hand-written. The one generated file in this directory is `COMPARISON.md`: it is declared in
`GENERATED.json` and `code/check_published.py` re-runs its generator and compares byte for byte.
Everything below is counted from the artifacts beside it; nothing is typed from memory._

- **Pinned block:** `52367749` (`0x173140a22455bdb229c181ba882b1ebdb14e25d45e79aa7b691c8100dcece26c`), reads pinned by block hash with `requireCanonical`
- **The same ladder as the published base-depth run** — this is that row set re-read at a later block, not a new row set. `COMPARISON.md` reports 43 rows at both blocks, 0 only at one side.
- **Result: 43 rows · 43 read cleanly in both runs · 0 read failures in either run · 0 disagreements on the claim-bearing fields**

## What the two run tags are

`base-ladder-B-run1.json` and `base-ladder-B-run2.json` are two invocations at the same pinned
block, each carrying its own read archive (`reads-173140a22455-run1.*` and
`reads-173140a22455-run2.*`, named by that run's own `reads_archive` field).
`reads-173140a22455-run1.json` and `reads-173140a22455-run2.json` are the read records for those
two archives: they were extracted verbatim from each ladder's `reads_archive` block — no digest
retyped — and each verified with `python code/verify_reads.py <record>`, which is the record file
the harness now writes itself; it gained that behaviour only after this measurement was taken. Both records report
2866 calls, 2866 entries, 735 cache hits and `read_failures: 0`, and both answer all 43 rows.

## The honest boundary: this is one piece of evidence in two copies

The two read archives are **byte-identical**. The index file is the same file twice — sha256
`a01a32e5a9ae2cb592aa2ddcb7d6b8fc0d87d7ab73e5a61c69a8275db7879e7f`, 1558221 bytes each — and
the compressed responses likewise, sha256
`2c82ae2805ddfad856a5d1f508c15166ccc1422c93eac5ef87763cdcf746e7c6`, 12608 bytes each; both
records carry the same `index_sha256` and the same `responses_sha256_uncompressed`.

So what these two runs demonstrate is that **the read sequence is deterministic**: the same block,
read twice, produced the identical call list in the identical order with the identical responses.

What they do **not** demonstrate is independent reproduction. Byte-identical archives mean there
is one piece of evidence here in two copies. The second run is not a second witness; it is the
same witness, asked twice, and it answered the same way.

That is a property of *this* pair, not of the method, and the contrast is in the artifacts rather
than asserted. The previous pair at this same block — `rerun-A1.json` and `rerun-A2.json` in the
measurement working directory, not copied here — did not agree with itself: that run1 recorded
2350 calls and 543 cache hits against run2's 2607 calls and 695 cache hits, and run1's own read
archive is not preserved at all (both records name the surviving file, whose 2607 entries match
run2's 2607 calls and not run1's 2350). A read sequence is not deterministic because it was
measured twice; it is deterministic when it is measured twice and the two agree.

## Why failures are published as failures

An earlier pair at this same block came back with eleven rows carrying no number in one run —
three rows classed `error` and eight dropped along with their two pools — against eight recorded
read failures (`read_failures: 8` in `rerun-A1.json`; that run's log attributes them to
`rpc_error: URLError` on `tickBitmap` calls, a transient endpoint condition and not a property of
the pools).

Those rows are published as failures rather than removed, and that is the point. Had they been
silently dropped, the run would have looked like a clean run over a thinner row set, and the
difference between "thin data" and "a bad moment at the endpoint" could no longer be told. A
failure that is deleted is a failure that cannot be distinguished from an absence.

## Side by side

`COMPARISON.md` carries the table for block `52175000` (the published base-depth run) against
block `52367749` (run2 above). It prints what each block answered and does not say depth changed:
a difference between two blocks is equally consistent with withdrawal, with a price move and with
a reweighting, and that table adjudicates between none of them.
