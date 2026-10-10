# If I had to set a collateral cap on these assets today, here is the number and why

**What this is.** A decision made on this project's own published data, by me, with nobody
paying for it, as a demonstration that I will produce a number under a deadline rather than
only describe what is not established. **It is not advice to anyone.** Nobody has engaged me
on these assets, no issuer or parameter-setter has funded any part of this measurement, and
the conclusion below is mine rather than a client's. The reason it exists is narrow: every
other document here states what was measured and refuses to conclude, which is correct for an
artifact and leaves one question unanswered — whether the person who wrote them will decide
anything. This answers that question and nothing else.

**No figure below is typed here.** Each one is cited to the file and row that holds it, in the
same directory as this file. If a number here and the artifact ever disagree, the artifact is
right and this file is wrong.

---

## The decision

**On the evidence I hold, I would not support a supply cap above USD 1,000 per asset, and I
would support it only for `AAPLc` and `GOOGLc`.** For `MSFTc` I would cap at USD 100. For
`NVDAc` against USDC I would onboard no cap at all without first constraining the route.

That is a cap small enough to be useless for a lending market, and I want to be exact about
why: **it is a limit on what has been measured, not a claim about how deep these venues are.**
Those are different statements and a cap has to be set on the first one.

## What the evidence supports, size by size

Read from `base-depth-publishable-Y.json` (18 publishable rows) and `base-depth-panelb-Y.json`
at pinned block `52175000`, with the block hash and the two-run agreement recorded in
`README.md` beside them.

| size | publishable rows | rows in band 2 (≥90% recovered) |
|---|---|---|
| USD 100 | 7 | 6 |
| USD 1,000 | 3 | 2 |
| USD 10,000 | 1 | **0** |
| above USD 10,000 | **0** | 0 |

The shape is the decision. At USD 100, six pools recover above 90%. At USD 1,000, two do —
`AAPLc/USDC` at fee 3000 and `GOOGLc/USDC` at fee 10000; the figures are the rows in
`base-depth-publishable-Y.json`. **At USD 10,000 the only surviving publishable row is the one
pool that can return almost nothing**, and above USD 10,000 there are no publishable rows at
all. `MSFTc/USDC` has a row at USD 100 and none above it.

Everything else at the larger sizes is in one of two states, both recorded: twenty rows are
sealed because a leg crossed more than one liquidity range, which this method does not
replay-validate, and five rows have no figure because their reads failed — those five and
their per-run failure reasons are in `errors_detail`, and they are exactly the USD 10,000 and
USD 100,000 rows of the pools that would otherwise carry the large sizes. A sealed row and a
failed row are different things and neither is a measurement.

## The part that changes how the cap has to be written

A cap is survivable only if the liquidation path is. A liquidation is a forced exit, and it
routes through whatever pool is reachable, not through the best one.

**For `NVDAc/USDC` there are two pools, and one of them cannot return more than the fraction
recorded in `base-depth-panelb-Y.json` as its `upper_bound_pct` — not from slippage, but
because that bound is derived from `holding_raw`, which is everything the pool holds.** The
other pool's measured recovery at USD 100 is in the publishable rows and is above 99%. The two
differ by roughly the ratio those two files imply.

So for that pair, the honest input to a cap is **the worst routable pool, not the best one, and
not the sum of them**. Summing liquidity across pools would produce a number that no exit can
realise. If routing can be constrained — a liquidation path pinned to a named pool, or a
minimum-output guard that refuses the bad one — then the better pool's figure becomes usable
and the cap can be set against it. Without that constraint I would not set a cap on that pair
at any size, and the reason is not depth, it is dispersion.

That dispersion is also why a cap set from an aggregate figure for this venue would be wrong
in a way that is invisible: the pools differ by orders of magnitude, and an aggregate hides
which one a given exit routes through.

## When this decision expires, and what that costs

Made at pinned block `52175000`, on **2026-10-09**. A second measurement at block `52367749`
is in `../base-depth-recheck-2026-10-09/`, where the comparison table prints both blocks side
by side and adjudicates no mechanism between them.

The provable window on this chain is about 1.28 million blocks and it slides. At the time of
writing, roughly 1.09 million blocks of it remain on block `52175000`, which is about
**25 days — so around 2026-11-03** anyone can still re-read that block from a public endpoint
and recompute these rows. After that, recomputation needs an archival endpoint, and a figure
from one cannot be rechecked by a reader without the same access.

That is a real deadline on a decision, and it cuts both ways. It is why I would rather state a
cap now, with its coverage limits attached, than wait for better coverage and publish a number
nobody can independently verify. And it is why the read logs for the later run are archived
with their digests: after the window closes, that archive is the only thing that can show what
was read at the time.

## What would change this number

**New measured rows.** A publishable row in band 2 at USD 10,000 for any of these pools would
raise the cap for that pool directly, and it is the single cheapest thing that would. The
sizes are already in the ladder; what stopped them was reads, not method. Equally, a row that
comes back in band 0 or 1 at a size currently unmeasured would *lower* the cap, and I would
publish that with the same prominence.

**Read failures of a particular kind.** The five rows with no figure failed on the selector
that walks the tick bitmap, on the rows that issue the most reads, and the two runs lost
different rows — so their absence is a property of the read budget in that run and not of any
pool. If a re-run with pacing recovers them in band 2, the cap moves up. If they fail again
the same way, that is still not evidence about depth, and I would not let repeated absence
harden into a conclusion.

**The window closing.** After roughly 2026-11-03 these rows stop being recheckable from a
public endpoint. At that point the cap should not continue to rest on them: either a fresh
pinned-block measurement replaces them, or the cap reverts to whatever the most recent
recheckable measurement supports. A number that can no longer be verified should lose its
standing on a schedule, not when somebody notices.

---

Two things this file deliberately does not do. It does not recommend a parameter to any
protocol — it states what I would do with my own evidence, which is a different act. And it
does not price anything: if someone wants a cap set for them, what they would be buying is a
measurement and its limits, never a conclusion, and I take no money from the issuer of an
asset I measure or from a party whose own parameters the measurement would feed.
