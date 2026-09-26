# PREREG-oneside-depth addendum 3 — two places the run did not match the registration

Date: 2026-09-26. Series: canon `rhdepth-oneside-v1`
(`PREREG-oneside-depth-2026-09-25.md`, addendum, addendum 2). Forward window opened
2026-09-26 00:00 UTC.

This addendum **changes no rule**. It records two places where the series as RUN did not hold to
the series as REGISTERED. Both are inside the forward window, both were found on 2026-09-26 by an
independent review of the collecting host, and both are recorded rather than repaired:

* the affected rounds are **not** withdrawn — A8: published rounds are never rewritten;
* the affected rounds are **not** compliant either, and nothing here should be read as saying
  they are.

## R1 — rounds 1–4 name an enumeration that was never archived

§2a registers, verbatim:

> a  Every enumeration is archived as `enumerations/pools-<block>.json` and never overwritten.
>    A round records `enumerated_at_block`, and that number has to point at a file that still
>    exists; a single overwritten current-list would make the number unresolvable.

The first four rounds — 00:01, 01:01, 02:01 and 03:01 UTC on 2026-09-26 — carry
`pools_source.enumerated_at_block = 71,909,188`. **No archived list for that block exists.** The
collector of that version kept one current list and overwrote it in place, which is precisely the
failure §2a was written against.

**What was not done.** The enumeration was not re-run at that block and published as the source of
those four rounds. Re-running would produce *an* enumeration of that block; it would not produce
*the* list those rounds were quoted against, and publishing it under their names would be
fabrication. The four rounds keep their numbers and lose their resolvability, which is the honest
description of what happened.

**What was done.** An explicit absence record:
`data-oneside/enumerations/MISSING-71909188.json` (6,655 bytes). It states what is missing and why,
names the four affected rounds, and carries 41 `(asset, pool, quote)` pairs recovered from those
rounds' own quote rows — which is evidence, since it comes from the rounds themselves.

It also states what it does **not** contain: `present_not_quoted`, `unclassified` and
`per_asset_candidates`. The collector version that produced those rounds never recorded them, and
they cannot be recovered from anywhere. A missing record that lists its own holes is worth more
than one that quietly omits them.

**Publication.** `data-oneside/` is published by the same daily sync as `data/`, and only for
complete days, so this file first appears in the public repository with the 2026-09-27 06:01 UTC
sync. Until then the four rounds' `enumerated_at_block` is unresolvable **and the record saying so
is also not yet public**; that window is stated here rather than left to be discovered.

**Status: rounds 1–4 do not satisfy §2a.**

## R2 — `pools_source` changed shape twice inside the window

```
00:01 – 03:01    no age_blocks, no refresh, no window_blocks
03:01            + age_blocks, refresh, window_blocks
11:42 onwards    + present_not_quoted, unclassified      (10 keys, the current shape)
```

§2b registers, verbatim:

> b  Every round carries how old its list is and whether the last refresh succeeded:
>    `pools_source.age_blocks`, and `pools_source.refresh.{last_attempt_ok, last_success_utc,
>    consecutive_failures}`. A refresh failure does not stop collection -- the previous list is
>    used -- but a stale list is never allowed to look freshly enumerated.

The first three rounds therefore lack two fields §2b registers as per-round. **The rounds are not
edited** (A8). The guard is now `REGISTERED_SOURCE_KEYS` in the collector: a round whose
`pools_source` does not carry exactly the ten registered keys raises `AssertionError` instead of
being written, so the shape cannot change a third time in silence.

**Effect on verification — checked, not assumed.** `pools_source` is not part of the canon
preimage (`block|sell_sym|side|size_usd|route|amount_in_raw|mid_amount_raw|amount_out_raw|status`),
so `roundKeccak` is unaffected by either change in shape. The round hashes of the affected rounds
verify against what was published for them.

## Not in this addendum

**The unclassified revert.** One round — 15:00 UTC on 2026-09-26 — was refused wholesale by the
registered rule, and the collector of that version truncated the failing error to 60 characters.
The selector is `0xc46d6f03`; it is not in 4byte.directory and is not one of the standard
UniV3 reverts. **The full reason is permanently lost.** It is not classified here, and the
absence is not evidence of anything except that a rule which voids a whole round is only
auditable when the reason survives. From 16:00 UTC the refusal record
(`<day>/refusals.jsonl`) keeps `code`, the full `message`, the full `data`, the selector and the
revert bytes, and is not part of the canon preimage or of `roundKeccak`.

## What this addendum does not do

It does not amend §2a or §2b. Both are correct as written; the run failed them. An earlier draft
of this record proposed relaxing §2a to allow "the list in use at the time". That would have made
the registration describe what happened instead of what was required, which is the one thing a
pre-registration must never be adjusted to do.
