# Reading pool state at a pinned block: the failures that do not announce themselves

This is a methods note, not a measurement. It is here because the measurements in this
repository were wrong for a while in ways that produced clean, plausible, repeatable output,
and because every one of those ways is available to anyone else writing a reader against
Uniswap v3-shaped state. The numbers quoted below are all published in
[measurements/base-depth/DISCLOSURE.md](measurements/base-depth/DISCLOSURE.md); nothing here
is a new claim.

The failures have one shape. **A check was broken and did not say so.** Not "a bug produced a
wrong answer" — that is the easy kind, because the answer looks wrong. These produced answers
that looked right, and in several cases produced them *consistently*, which is worse: a
consistent wrong answer passes every sanity check that consists of running it again.

---

## 1. A failed read that returns a plausible value

Three instances, same mechanism:

| read | what a failure returned | how the code then read it |
|---|---|---|
| `ticks(int24)` | `0` | "no liquidity change at this tick" |
| `tickBitmap(int16)` | a sentinel | "nothing initialised in this direction" |
| `token1()` | the zero address | the row kept the label it already had |

Each of those is a legal value with a meaning. `liquidityNet == 0` is what an initialised tick
with balanced positions looks like. An empty bitmap word is what a sparse pool looks like. So
a transport failure was indistinguishable from a reading of the chain, and the walk kept
going — past liquidity it should have stopped at, or across a boundary it never saw.

The identity case is the one to dwell on. A failed `token1()` returning the zero address did
not stop the row; the row still carried `NVDAc/USDC` as its label, because the label came from
the pool table rather than from the read. **The label and the thing being measured had
different sources, so they could disagree without anything noticing.**

The fix is not better defaults. It is that a failed read must raise:

```python
class ReadFailed(Exception):
    pass

def liquidity_net(pool, tick, block):
    ok, r = call(pool, sel("ticks(int24)"), encode_int24(tick), block)
    if not ok:
        raise ReadFailed(f"ticks({tick}) on {pool} at {block}")
    ...
```

and that the row carrying the failure is published **as a failure with its reason**, not
dropped. A dropped row is a row that silently leaves the denominator.

## 2. A length check that is off by the prefix

`ticks(int24)` on a v3 pool returns eight words. The response is therefore
`2 + 64 * 8 = 514` hex characters, counting the `0x`. The check in place was:

```python
if len(r) < 2 * 64:          # wrong
    raise ReadFailed(...)
```

A response of 128 or 129 characters passes that and word 1 — `liquidityNet`, the field the
walk actually uses — is incomplete or absent. The correct check is exact:

```python
if len(r) != 514:            # 0x + 8 words, no slack
    raise ReadFailed(...)
```

Range checks on a struct response are the wrong shape in general. The length is known
exactly; accept exactly it. A `<` or `>` leaves a band of responses that are truncated and
welcome.

## 3. Pinning a block number is not reproducibility

There are three windows, and they are not the same width:

- **Readable.** On Base, more than 50 million blocks answer a state call.
- **Provable.** Roughly 30 days, sliding — the window in which a block hash still resolves and
  an archival read can be checked against it.
- **Reproducible.** Narrower than both, and not a property of the chain at all.

A load-balanced endpoint can serve two reads of *the same block number* from different
backends in different states. Pinning the number does not pin the state. What does is pinning
the **hash**, with the canonicality flag:

```json
{"blockHash": "0x…", "requireCanonical": true}
```

Worth verifying that your endpoint honours it rather than ignoring it: pass a forged hash and
confirm you get an error rather than an answer. An endpoint that silently falls back to
`latest` when it cannot serve a hash will give you a reproducible-looking number that is not
the number you asked for.

## 4. "Retry until they agree" is not a validation. It selected the wrong number here.

Four runs pinned to the same block hash disagreed on 7 of 43 rows, and on the recovery figure
itself in 3 of them. The largest disagreement was a factor of **3.49** on one row: the two
values were **5.646941%** and **19.712807%**.

The lower value was the corrupted one.

So a majority vote across runs, or a "run it until two agree" rule, would have selected the
wrong number — not by bad luck, but because the corrupting mechanism (a failed read returning
a plausible value) is more likely to repeat than the correct read is to be observed, when the
failure is load-correlated. **Agreement between runs is evidence about the reads, not about
the chain.** It is necessary and it is not sufficient.

What agreement is good for: once reads raise on failure and are pinned by hash, requiring two
independent runs to be **bit-identical** and publishing only the rows that are turns a
disagreement into a hard stop instead of a vote. In the run this repository publishes, 38 of
43 rows read cleanly in both runs and were identical across them, with **0 disagreements**;
the other 5 are published as rows with no number.

And what it still does not establish: two runs agreeing on the same block hash **cannot
exclude a deterministic degradation**. A fallback triggered by load would make both runs give
the same wrong answer. Excluding that needs a check that does not depend on the endpoint
agreeing with itself — a storage proof anchored to the block hash. Saying "two runs agreed" is
not the same as saying "the endpoint did not degrade", and the second sentence is the one a
reader might think they are being told.

## 5. Name the convention before you write the formula

For a round trip through one pool, there are two defensible conventions:

- **A, sequential:** leg 2 is priced against the state *after* leg 1.
- **B, same state:** both legs are priced against the same pinned state, opposite directions,
  no state threading.

Under B, with fee `f` and a trade of `dx` against virtual reserve `x_v`:

```
recovery = (1 - f)² / (1 + (dx / x_v)(1 - f)(2 - f))
```

which depends only on the ratio `dx / x_v`. Here is the part worth carrying away: under A,
`(1 - f)²` is a **floor** and recovery rises with size; under B it is a **ceiling** and
recovery falls with size, approaching `1/size`. Same pool, same fee, opposite slopes.

So the slope sign is a free detector of which convention a number was computed under. And
`recovery ≤ 100%` — the obvious sanity check — is satisfied by both, which makes it **blind to
the error**. A table built under one convention and documented under the other passes every
plausibility check anyone will apply to it.

I got this wrong in a pre-registration by writing the formula without naming the convention
first. The rule that came out of it: the convention is part of the definition, so it goes
above the formula, not in a footnote.

## 6. A drill with one arm proves nothing. Neither does one that cannot see what it checks.

The shape that works:

```
arm_broken  = run with the failure injected   ⇒ must fail, on the named check
arm_clean   = run with nothing injected       ⇒ must pass
assert arm_broken != arm_clean      ← without this, both can be true and nothing was tested
assert other_row identical in both  ← proves the injection was local, not a global break
```

The third line is the one people leave out, and it is the one that catches a drill whose
injection never took effect. Four ways that has happened here, all of which produced a drill
that reported green or whose failures were about the drill rather than the code:

**The injection could not take effect.** A block of shell extracted from a larger script for
testing began by assigning its own absolute paths. Under `eval` those assignments overwrote
the stubs, so the drill ran the real generator against the real directories and every injected
failure was a no-op — 7 of 11 assertions were measuring nothing. The fix is that production
values belong in the code as *defaults*:

```bash
WEEKLY_GEN="${WEEKLY_GEN:-/abs/path/to/generator.py}"
```

A block with hard-coded paths can only be drilled together with its real dependencies, which
means it cannot be drilled at all.

**The assertion could not observe the effect.** The code under test redirected its side
effects: `git add … >/dev/null 2>&1`, and a generator whose stderr was captured and printed
only on failure. A stub that reports by echoing is invisible through either. Stubs must
**record to a file** that the assertion then reads:

```bash
git() { echo "$*" >> "$td/git.calls"; }
```

**The arms shared state.** Two arms run in the same temporary directory: the first arm's
output became the second arm's input, and the control arm produced a confident, wrong result.
One fresh directory per arm.

**The assertion matched the presentation layer.** Three variants, all of which lose
discriminating power without raising: trimming whitespace off a line and then matching an
anchor that includes indentation; `grep` across multiple files, where each match is prefixed
with `filename:` and the prefix ends up inside the value you parsed out; and a check whose
label text contains the string the check searches for, so it matches itself.

The general version: **a failed read returns empty, every probe over it returns False, and
"nothing reported an error" is read as "everything passed."** Before interpreting content you
fetched or read, assert its length against a floor. Zero bytes must refuse to be interpreted,
not count as "no matches found".

## 7. The sealing rule

Two things in this work are validated per leg and not as a composition:

- a leg that traverses **more than one liquidity range** — multi-range accumulation is not
  replay-validated;
- the **round-trip composition itself** — it is defined by the method, and each leg was
  separately checked against real swaps, but the composition was never checked against a real
  round trip.

Rows that depend on either are sealed rather than published. The distinction matters because
"we validated the legs" is often offered as if it validated the product of the legs, and it
does not.

---

## Why this is published

Because the alternative is a repository whose instrument history is invisible, and because
every item above is cheap to avoid once named and expensive to find on your own. The report
page carries a numbered archive of this project's instrument failures, each with how it was
caught and which side of publication it landed on. This note is the part of that archive that
generalises past this project's own data.

If you are writing a reader against this kind of state and one of these is already in your
code, that is the useful outcome. The contact address and the correction policy are in the
[README](README.md).
