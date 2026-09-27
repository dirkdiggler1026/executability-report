# PREREG-oneside-depth addendum 4 — the "selector" in addendum 3 is a stateRoot

Date: 2026-09-27. Series: canon `rhdepth-oneside-v1` (`PREREG-oneside-depth-2026-09-25.md`,
addenda 1–3).

This addendum corrects addendum 3. It changes no rule, and it does not touch the R1/R2 findings
recorded there; both stand as written.

## What addendum 3 says, and what is wrong with it

Addendum 3's closing section ("Not in this addendum") reads:

> The selector is `0xc46d6f03`; it is not in 4byte.directory and is not one of the standard UniV3
> reverts. **The full reason is permanently lost.**

Three statements, all false:

* `0xc46d6f03` **is not a selector**, and there was no revert at all;
* it is **not revert data** of any kind;
* the reason was **not lost** — it was misidentified. It is stated below.

## What `0xc46d6f03` is

It is the **leading four bytes of the `stateRoot` of the block that round was pinned to**.

```
block 73,173,259   (2026-09-26 15:00 UTC, the refused round)
  blockHash   0x93a68cd5a4ed64f36ec4d62f4883cecb00a2ec461f9ccc461f3f54737bcfd4cb
  stateRoot   0xc46d6f033a414de8b1e1b7149e66c29796bf9eb511aa5e6f0a26105da7127ce9
              ^^^^^^^^^^ published in addendum 3 line 121 as "the selector"

block 73,530,638   (2026-09-27 01:00 UTC, whose refusal message survives in full)
  blockHash   0x95cea3bb42595a52d359226e5f3882d7958ff5a15cc68c4aef3245db82a36d66
  stateRoot   0x9240a35a7f8192388a0d9fcb799ad679d974de183d25caa9a8b034dbf4b107df
              ^^^^^^^^^^ the leading hex inside that message's brackets
```

Both were read from the **public** endpoint on 2026-09-27, with no key and no archive node,
because **block headers are never pruned — only state is**. That distinction is itself evidence
for the cause below. Reproduce with:

```sh
curl -s -X POST https://rpc.mainnet.chain.robinhood.com \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getBlockByNumber","params":["0x45cf14b",false]}' \
  | grep -o '"stateRoot":"[^"]*"'
```
`0x45cf14b` = 73,173,259; `0x461b64e` = 73,530,638.

## How it was produced

The collector's first `err_record()` pulled the first `0x…` it found in the human-readable part
of the JSON-RPC error and reported its first ten characters as a selector. Prose is not an ABI.
The string it found was inside a bracketed prefix of the message, and the 60-character truncation
that was then in place cut it off **inside the stateRoot**, six characters short of the closing
bracket — which is why it did not look like the beginning of a bracketed string at the time.

This is the same error class as the truncation itself, and as the storage-slot read recorded in
`ievidence-ledger/MEASUREMENTS.md`: **a quantity produced by our own parsing or by our own boundary,
read as a property of the object.** It is also, by the error archive's own criterion, a precise
number that looked like an insight.

## What actually happened, and what is established versus inferred

**Established.** The 2026-09-27 01:00 refusal carries the message, in full:

```
[0x9240a35a7f8192388a0d9fcb799ad679d974de183d25caa9a8b034dbf4b107df] layer stale
missing trie node c333c6b8eb5a27be418ebd1a5faa88d7eb98614036853d9a06b48e2e2f5d81db (path 0f) layer stale
```
code `-32000`, block 73,530,638, AAPL $100,000, pool `0x6f7368f0dd…`. The bracketed string is
that block's `stateRoot`, byte for byte. Nothing here is a contract revert: the endpoint was
**pruning the state of the pinned block while the round was still running**. A round pins a block
and then takes about 110–122 seconds to finish; the report page records that this endpoint keeps
roughly five to ten minutes of state (3,100–5,900 blocks, measured 2026-09-11 → 09-15). The margin
was always thin, and two rounds were voided when it ran out.

**Inferred, and left as inference.** That the 2026-09-26 15:00 message's second half carried the
same `layer stale` text. One sample exists whose shape matches, and the leading hex matches that
block's stateRoot; the message text itself is still lost. The two statements are not merged below
or anywhere else in this addendum.

**Not a finding about the pool.** Both refusals name the same pool, `0x6f7368f0dd…`. That is not
evidence about that pool: the pruning landed on whichever call was in flight, and this one is late
in the iteration order. Recorded so that it is not read as a discovery.

## What changed in the collector (as reported by the collecting host)

* `err_record()` takes `selector` **only** from `error.data`, never from the message text;
* `kind` is one of `state_unavailable` / `rate_limited` / `revert` / `rpc`;
* `state_unavailable` is now **retried** with a 3 / 6 / 9 s backoff — the public endpoint sits
  behind a load balancer, so "this node pruned it" is not "every node pruned it";
* `<day>/refusals.jsonl` carries `kinds`, and the health check reports the failure kind rather
  than a selector that never existed.

The retry is the substantive change: two whole rounds (212 rows each) were voided by a condition
the first version did not retry at all.

## Where this error is recorded

It is an instrument error of exactly the kind the report's error archive exists for, and it was
found **after** the figure it corrects had been published — addendum 3 is in the public
repository. It is being recorded there as the fourteenth entry, which makes the archive's split
seven before publication and seven after. The page's count is **derived from the entries' own
attributes**, not typed, so adding the entry moves the count by construction.

Artefacts that print a count are dated artefacts. The film was recorded 2026-09-26 and says
"thirteen of them"; card 4 is a 2026-09-26 image and shows 13 / 7 / 6. Neither is rewritten. This
addendum, and the archive entry, are where the fourteenth is stated — and where a reader who
notices the difference between a recording and a live page finds the explanation.
