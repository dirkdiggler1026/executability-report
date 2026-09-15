# Serialization note — how a round hash is built (canon `rhdepth-v2`)

Written 2026-09-15 UTC, so that a second implementation can be written **without reading
`code/collect.py` or `code/verify.py`**.

## Honest boundary — read this before relying on the result

This document is **derived from the reference implementation**, by the same party that wrote it.
It is therefore independent of the *code text*, not of the *understanding behind the code*. A
second implementation built from this document and agreeing with the published hashes shows that
**this document is sufficient to reproduce the format**. It does not show that the format is free
of ambiguity, because the ambiguity and the description have a common author.

The result that survives that limitation is **partial disagreement**: if some rounds match and
others do not, an ambiguity exists that will bite any reader, and the common author does not
protect against it.

Spec §2.2 names the byte-level authority as the published `rounds.jsonl` plus `code/verify.py`.
That remains true. This note is a description of that authority, not a competing definition; the
published test vectors below are what detect any drift between the two.

**Method rule for anyone testing against this note:** do not search the vectors for a format that
fits. Inputs and hashes are both public, so a brute-force over field orders and separators will
eventually produce a combination that matches — and that is fitting to the answer, not an
independent implementation. Implement one reading of this document, evaluate once, and only then
diagnose a mismatch.

## The line format

One line per row. Nine fields, in this order, joined by `|` (U+007C):

    block | sell_sym | side | size_usd | route | amount_in_raw | mid_amount_raw | amount_out_raw | status

- **`block`** — the block number the whole round is pinned to, as a decimal string. Every row in
  one round carries the same value.
- **`sell_sym`** — the stock token's symbol, e.g. `QQQ`. Uppercase ASCII as published.
- **`side`** — in canon 2 always the literal `roundtrip`. It **is** part of the preimage.
- **`size_usd`** — the notional in whole US dollars, decimal string: `100`, `1000`, `10000`,
  `100000`.
- **`route`** — the Uniswap v4 **poolId**, a key into the PoolManager singleton, **not an
  address**. It appears in the data as `0x` plus 64 lowercase hex digits, and **the value is
  copied through unchanged**. The reference implementation applies no case folding and no
  normalisation of any kind. Read this as a statement about the value, not as a rule to apply:
  an implementation that lower-cases the field agrees on every published round (no published row
  contains an upper-case hex digit — 0 of 21,908) and would disagree the first time one did.
- **`amount_in_raw`** — USDG paid in, in the token's smallest unit, decimal string.
- **`mid_amount_raw`** — the raw integer the quoter returned for the **first** leg: how many stock
  tokens the USDG bought. Decimal string.
- **`amount_out_raw`** — the raw integer the quoter returned for the **second** leg: how much USDG
  came back from selling that entire amount through the **same** pool. Decimal string.
- **`status`** — `ok` or `no_liquidity`. No other value may appear in a published round; see
  "Statuses" below.

Integers are always rendered as **decimal strings**, never as a numeric type. Several of these
values exceed 2^53 and would lose precision in any IEEE-754 double. `mid_amount_raw` in the
vectors below is 30 digits for exactly this reason.

## Empty values

A field with no value renders as the **empty string**, so consecutive `|` appear.

**The coercion rule is "falsy becomes empty", not "null becomes empty".** In the reference
implementation the expression is Python's `value or ""`, which maps `None`, `""`, and **`0`** all
to the empty string.

> **Cross-language note.** JavaScript's `??` is not equivalent: `0 ?? ""` yields `0`, while
> `0 || ""` yields `""`. This diverges only on a **numeric** field holding zero.
>
> In canon 2 that is currently unreachable. Only `block` and `size_usd` are numeric; `block` is
> never 0 and `size_usd` is one of 100 / 1000 / 10000 / 100000. The three `*_raw` amounts are
> already strings in the data and are concatenated without conversion, so a non-string there
> raises rather than producing a different hash, and the string `"0"` is truthy under both
> operators. `null` behaves identically under both.
>
> It is recorded because the exclusion rests on the current value domains, not on the
> serialisation: should a numeric field ever be able to hold 0, `??` and `||` part company, and
> no vector would show it.

## Sorting

The lines of one round are sorted **after rendering**, as whole strings, in ascending Unicode code
point order (Python's default `sorted` on `str`; JavaScript's default `Array.prototype.sort` on
strings is the same order for this alphabet).

Sorting is over the rendered line, **not** over structured fields. Collection order is irrelevant:
the same round assembled in any order yields the same hash.

## Preimage and hash

    preimage = "rhdepth-v2" + "\n" + lines.join("\n")

- The canon version is the literal ASCII `rhdepth-v2`, followed by one `\n`.
- Lines are joined by `\n` (U+000A). **There is no trailing newline.**
- The preimage is encoded **UTF-8**.
- The hash is **keccak-256** (the Ethereum variant, not SHA3-256 as standardised by NIST).
- It is published as `0x` plus 64 **lowercase** hex digits.

**The canon version is inside the preimage.** A round recorded under a different canon therefore
hashes differently by construction; canon versions are not comparable and are not meant to be.

## Statuses

Only two statuses may appear in a published round:

- **`ok`** — both legs quoted.
- **`no_liquidity`** — the pool declined to quote the round trip. This is an **on-chain fact**, so
  it belongs in the series.

`rpc_error`, `ok_partial` and `revert_other` are **never written**. They are instrument faults or
defects; on encountering one the entire round is discarded and recorded in `failures.jsonl`. This
matters for the preimage: the status string is *in* the hash, so writing a fault would place our
own infrastructure trouble inside a commitment that claims to be reproducible.

A round is therefore all-or-nothing. **A round with fewer rows than expected is not a damaged
full round; it is a different preimage and a different hash.** No partial round is ever published.

## Test vectors

### Published rounds — the primary vectors

Every published round is a vector, and they are already public:

    executability-report/data/<YYYY-MM-DD>/quotes.jsonl.gz   the input rows
    executability-report/data/<YYYY-MM-DD>/rounds.jsonl      the expected roundKeccak

Use rows whose `block` matches the round's `block`. **Filter by canon at the round level, not on
the rows:** `rounds.jsonl` records carry a `canon` field, the rows in `quotes.jsonl.gz` do not
(0 of 21,908 rows have one). Take the rounds whose `canon` is `rhdepth-v2`, then take the rows
matching those blocks.

### Synthetic vector — `no_liquidity`, which no published round contains

Every published round to date is `ok`; there are zero `no_liquidity` rows in the entire published
series. The empty-field path is therefore **untested by the primary vectors**, and it is the path
that will be exercised the first time a pool stops quoting — which is precisely the round a third
party will most want to recompute.

Input rows (order irrelevant):

```json
{"block":60000000,"sell_sym":"AAA","side":"roundtrip","size_usd":100,"route":"0x1111111111111111111111111111111111111111111111111111111111111111","amount_in_raw":"100000000","mid_amount_raw":"123456789012345678901234567890","amount_out_raw":"99939710","status":"ok"}
{"block":60000000,"sell_sym":"BBB","side":"roundtrip","size_usd":100000,"route":"","amount_in_raw":"100000000000","mid_amount_raw":null,"amount_out_raw":null,"status":"no_liquidity"}
```

Rendered and sorted:

```
60000000|AAA|roundtrip|100|0x1111111111111111111111111111111111111111111111111111111111111111|100000000|123456789012345678901234567890|99939710|ok
60000000|BBB|roundtrip|100000||100000000000|||no_liquidity
```

Expected hash:

    0x01d0be93c1fe57d0830ec9a0b94965db51ae70f190cee1ffd8551860414541c8

**Residual limitation.** This vector's expected value comes from the reference implementation, so
it tests agreement with that implementation, not the absence of ambiguity in this note. That layer
cannot be removed by any vector; only the prose can close it, which is why the empty-value and
sorting sections above are written the way they are.

## What this note does not cover

How a round is *produced* — which pool wins, how retries are bounded, when a round is dropped — is
not part of the serialization. Two implementations that agree on this note will agree on the hash
of any given set of rows, whether or not they agree on how those rows were obtained.

## Revisions

**2026-09-15, after the first second-implementation run (478 rounds, 478 matches, 0 mismatches).**
The agreement showed the note was sufficient to reproduce the format. Three corrections came out
of the same run, none of which changed a single hash — they were found by reading the reference
implementation alongside the note, not by any vector:

1. `route` was described in a way that reads as an instruction to lower-case. The reference
   implementation copies the value through untouched. Both readings agree on every published row
   and would part company on the first upper-case one.
2. The `??` trap was stated as a live risk. It is unreachable under the current value domains;
   it is now recorded as a conditional rather than a hazard.
3. The vectors section told the reader to filter rows by `canon`. Rows carry no such field; the
   filter belongs at the round level.

This is the result the note's own honest-boundary section predicted in a different form. Total
agreement did not prove the format unambiguous — **two readings of one sentence survived every
vector, and only a second reader comparing prose against code found them.**
