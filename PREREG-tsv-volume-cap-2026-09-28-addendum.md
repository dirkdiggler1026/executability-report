# Addendum 1 to `PREREG-tsv-volume-cap-2026-09-28.md`

**Written 2026-09-28, still before the run.** No numerator, denominator or ratio exists at the
time of writing, and the collecting machine holds no volume artifact. §§1, 2, 4, 5, 6 and 7 of
the registration stand exactly as registered. This addendum corrects §3, which was wrong in a
direction that matters.

---

## 1. §3 called the figure a lower bound. It is not one.

The registration listed four gaps and concluded that every one of them makes the numerator a
lower bound. Three of them do. One does not, and it was written into the same list as if it
did:

```
①  the pool set is not claimed exhaustive           pools we never saw    ⇒ we UNDERCOUNT
②  pool-to-TSV attribution is not observable        see below             ⇒ EITHER DIRECTION
③  affiliated-TSV aggregation is a legal fact       see below             ⇒ EITHER DIRECTION
④  a backward scan uses a pool set enumerated
    at the end of the window                        pools that vanished   ⇒ we UNDERCOUNT
```

**② and ③ are the same unknown wearing two names**: we cannot see the map from pool to venue,
nor from venue to affiliate group. The registration treated ③ as "we miss the affiliates, so
we undercount", which is only one of its two modes. The other mode is the dangerous one:

```
if a pool in our set is NOT operated by the venue in question
   -- a permissionless pool holding the same token, or a pool of an unaffiliated venue --
then including it makes our figure LARGER than that venue's actual figure.
The exemption covers permissioned trading; nothing stops a pool existing outside it.
```

So the set of pools we sum over may be a superset of one venue's pools, a subset of them, or
neither. **The net direction is not provable, and "lower bound" asserts that it is.**

## 2. Why this is not a quibble about a word

"Lower bound" is read as *the real number can only be larger*. If our figure comes out above a
threshold, that reading turns an estimate into an accusation; and if it comes out below one, it
tells a reader the true value is worse than shown, when it may be better. **Either way the word
hands the reader a direction we cannot support**, which is the same defect as reporting a rate
limit as a chain fault, or a state root as a revert selector.

## 3. Registered replacement

> **The figure is an estimate over a stated pool set, not a bound.** It is the stock-side volume
> through the pools named in the published enumeration. The mapping from those pools to any
> particular Tokenized Securities Venue, and from any venue to its affiliate group, is not
> observable on chain, so the figure is neither an upper nor a lower bound on the quantity
> §II.F actually caps.

The wording **"lower bound"** is withdrawn from all reporting of this measurement, and so are
"at least" and "no less than" applied to the total.

### 3.1 The one place a bound survives

A bound is available for a narrower claim, and only that one:

> For **a single named pool**, the stock-side volume we measure through it is a lower bound on
> the volume through that pool, because a scan can miss events but cannot invent them.

Aggregating those per-pool bounds into a per-venue bound requires the attribution we do not
have. The bound stops at the pool.

## 4. What §3's other half still says, unchanged

The registered reading about the direction of *conclusions* stands and is, if anything,
stronger now:

> If the computed ratio comes out far below the cap, that is not evidence of compliance and
> will not be reported as such. "Within the limit", "compliant" and "does not exceed" are not
> available to this measurement.

That was registered because a low figure reads as reassurance. It now rests on a better
argument: not "the true figure can only be higher", which we cannot show, but **"we are not
measuring the quantity the rule caps"** — we are measuring a related quantity over a set of
pools we can name.

## 5. A property of §II.F worth registering before the numbers, because it changes what is useful

The order's penalty is stepped, and the first breach in a given stock carries no action:

> The first time a TSV exceeds a volume threshold in a Tokenized NMS Stock, it will not be
> required to take any action, other than to ensure that it does not exceed the volume
> thresholds going forward. … After the first time … each time the TSV subsequently exceeds the
> volume threshold in the applicable Tokenized NMS Stock, the TSV must immediately pause
> trading in such Tokenized NMS Stock for three months.

```
⇒ the cap is not a ceiling a venue must stay under; the first breach is a free allowance
⇒ so the interesting question is not "was it exceeded once" but "how close is it running,
   and has the free allowance already been spent"
⇒ a measurement taken once answers neither; the value is in a series
```

This is registered as an observation about the rule, **not** as a claim about anyone's conduct
or intent. It is here because it determines what a useful output looks like — a daily ratio
against the cap, rather than a single verdict — and that decision should be dated before the
first number, not after.

## 6. What this addendum does not do

- It does not change the six definitions, the window, the symbol set, the pool readings, or any
  of the three open dependencies.
- It does not weaken §3's registered reading about compliance; it replaces its justification
  with one that holds.
- It does not claim any pool in the enumeration is, or is not, operated by any venue. It records
  that we cannot tell, and stops.
