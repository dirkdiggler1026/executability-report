# Addendum to the absolute-floor pre-registration (2026-09-14)

Refers to `PREREG-floor90-2026-09-14.md`, sha256
`0150937253e628d0cb6eb2d89ec218799253def7766a9ed0f5ce26dcd538929e`. Written 2026-09-14 UTC,
before the forward window opens at 2026-09-15 00:00 UTC, and therefore before any round that
this rule will be evaluated on exists.

**It narrows the rule and adds no degree of freedom.** The floor, the cell set, the episode
definition and the three falsification thresholds are unchanged. That is why this is an
addendum and not a new registration: nothing here can be chosen to fit a result, because no
result exists yet.

## 1. Canon is pinned

The trigger is evaluated only on rounds whose `canon` is `rhdepth-v2`.

Recovery is *defined* by the canon version: the canonical preimage fixes which pools are in
the universe, and "best among the pools" is meaningless without it. Every round in the
calibration window is `rhdepth-v2`; no other canon has ever been written to this series.

canon v3 is scheduled independently and would widen the pool universe. A wider universe can
only improve the best available route, so recovery can only rise, so the floor becomes harder
to reach — **the trigger rate would fall for a reason that is not the market**, while the
floor, the cells and the falsifiers all sit still. Nobody reading the monthly reports would
see the quantity change underneath them.

**A change of canon ends this registration and starts a new one with a new date**, exactly as a
change of floor does. The original document's list of registration-ending changes omits canon;
that was an omission, not permission.

**This collision is scheduled, not hypothetical.** canon v3 is planned for after the
competition window, which falls inside the three months this rule needs. This registration will
most likely be cut short by it. What to do then — run v2 in parallel so the registration
completes, or close it and re-register on v3 — is not decided here, because deciding it here
would add back the freedom this document exists to remove.

## 2. When the median falsifier becomes evaluable

The 30-day rolling median cannot be computed before 2026-10-15. From 2026-09-15 to 2026-10-14
only the episode-rate falsifier is evaluated, and each monthly report states which falsifiers
were evaluable that month.

Stated here so that the first report does not silently choose between skipping the check and
computing it on a partial window. Both would be a definition settled at the moment of the
result.

## 3. One count corrected

"None below 92.8%" in the original is off by one round.

The lowest recovery observed in the twenty cells is **92.799766311**, which the original
displays as `92.7998` — a round-up. Since 92.799766311 < 92.8, exactly one round lies below
that bound: the minimum itself. The full-precision value is given here so the same off-by-one
is not derived again from the four-digit display.

Corrected counts over 9,320 cell-rounds:

    below 96.25 %   24
    below 95    %   13
    below 94    %    3
    below 93    %    2
    below 92.8  %    1
    below 90    %    0

No threshold changes. The floor remains 90.0000%.

## Status of this file

Like the document it amends, this file is never edited. Its git commit timestamp is the
evidence that it predates the window it applies to.
