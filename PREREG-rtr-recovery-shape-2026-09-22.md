# Pre-registration: RTR and Recovery shape

**Registration date: the date this file first appears in the public repository. Forward
evaluation starts at 00:00 UTC on the day after that.**

A local commit timestamp is not evidence of anything: `GIT_COMMITTER_DATE` can be set to any
value, so a commit that has not been published carries no time evidence for a third party.
What cannot be backdated is the earliest moment the file was publicly observable, and that is
what the registration date therefore means.

This document fixes a metric and a four-state classification before either is evaluated
forward. Everything below was written while looking at data through 2026-09-22, and the
one-off classification in the addendum was computed on that same window. That classification
is therefore **calibration, not test** — it says only that the boundaries do not produce an
absurd partition there, which is part of how they were chosen.

The two boundaries are not fitted to the window. Each is derived from a structure that does
not reference the data, and the derivation is stated so that a reader can check *that* claim
independently of the outcome. See §3 for what this does and does not establish.

## 1. RTR — round-trip recovery

At a pinned block, buy `$N` of a token with the quote currency and sell the entire position
back **through the same pool**. RTR is the proceeds returned to the principal, as a
percentage.

- One block, one pool, one size — that combination is a **cell**.
- Sizes: `$100` · `$1,000` · `$10,000` · `$100,000`.
- Quote currency: USDG.
- A size that cannot be filled is recorded as **unfilled**, never as a zero.

**Two units, and they are not the same unit.** `RTR`'s unit is a `(token, size)` cell — one
block, one pool, one size. **`Recovery shape`'s unit is a ladder** — one token's four cells at
one block. The shape rules read the whole ladder: `every size` quantifies over four cells, and
`concentration` needs the steps between them. **A single cell has an RTR; it does not have a
shape.** AMC at `$10,000` and AMC at `$100,000` are different cells carrying different RTRs;
they do not carry different shapes.

**This is a normal-state reading, not a post-default statistic.** The word *recovery* is
borrowed from credit, where it describes what is recovered *after* an event. RTR is measured
on an ordinary day with no event: it is the standing exit cost of a cell.

**Why `round-trip` is in the name.** It fixes the comparator: the principal, not a chosen
convention (arrival price, VWAP, close). The class of argument that has occupied conventional
transaction-cost analysis for twenty years — which benchmark — has no purchase here, because
the comparator is the thing that was put in.

## 2. Recovery shape

Two levels, applied in order. The level test runs first so that a ladder which is entirely
sound cannot be labelled by the shape of a decline that does not matter.

### First level — level test, boundary `Λ = 65%`

```
every size  ≥ Λ   ⇒  Flat
every size  < Λ   ⇒  Collapse
otherwise         ⇒  shape test
```

**`Λ` is derived from the liquidation identity, not chosen.**

At a liquidation threshold `T`, liquidation triggers when `loan / collateral value ≥ T`, so
`collateral value = loan / T`. A liquidator must recover `loan` from that collateral:

```
R ≥ loan / (loan / T) = T
```

The entry LTV cancels — it is an entry ratio, not an exit requirement. `T = 65%` therefore
sets both the trigger and the required recovery.

**Using `T` as the boundary is conservative in one direction only.** Liquidation typically
overshoots the threshold, and a liquidation discount is required on top, so the true
requirement sits **above** 65%. A ladder classified `Flat` against a 65% boundary is therefore
genuinely usable. **The converse is not claimed**: a ladder classified `Collapse` is not
thereby proven unusable for every holder, and this document does not say so.

### Second level — shape test, boundary `2/3`

```
concentration = largest single step ÷ total decline
concentration ≥ 2/3  ⇒  Switch     (a plateau, then a cliff)
concentration < 2/3  ⇒  Slope      (a decline spread across steps)
```

**`2/3` is derived from the arity of the ladder, not from the data.** Four sizes give three
steps. A decline spread evenly gives `1/3`; a decline concentrated in one step gives `1`. The
midpoint of those two structural values is `2/3`.

**`concentration` is undefined for ladders the level test decided.** `Flat` and `Collapse` are
not classified by shape, so no concentration is reported for them — not because the value is
uninteresting, but because it does not participate in the classification and printing it
would invite a reader to divide a number that plays no role.

### Ordering: `Flat → Slope → Switch → Collapse`

`Switch` sits after `Slope` for a mechanical reason: an even decline can be managed by
splitting the order, but splitting does not move a ladder out of the state it is in. A `Switch`
ladder has a size at which the exit is bad, and cutting the order does not remove that size.

### Reading it

    "AMC is Switch — the cliff is between $10,000 and $100,000"
    "QQQ is Collapse"

Naming the cliff's position is not decoration: it is the part a risk reader can act on, and it
is the part the shape rules actually produce. An earlier draft of this section gave the example
as *"AMC is Flat to $10,000 and Switch at $100,000"* — two labels on one ladder, neither of
which any rule in §2 can emit. A cell has an RTR; a ladder has a shape.

That sentence — not a decimal — is what a reader repeats to a risk committee.

## 3. What the boundary derivations carry, and what they do not

Stated in the same spirit as separating a floor from the minimum it sits below:

- **`65%` belongs to the liquidation identity.** It is not a clearance below anything observed.
- **`2/3` belongs to the ladder's arity.** It is not a midpoint of an observed gap.
- **The interval `(56.14%, 97.95%]`** — over which the calibration-window classification is
  unchanged — **belongs to the calibration window, not to the boundary.** It is a consequence,
  computed after the boundary was fixed, and it is not a justification for the boundary. Its
  width is not evidence of anything except that the calibration window is coarse. **The two
  ends are bracketed differently on purpose:** a boundary placed exactly at `97.95%` leaves the
  classification unchanged, so that end is closed; a boundary placed exactly at `56.14%` does
  not, so that end is open. Both files carry the same string, checked by searching rather than
  by reading.

**One thing this cannot claim.** Both derivations were written by people who had already seen
the calibration window. The derivations do not reference it, which a reader can check by
reading them; but the honest statement is *"the derivation does not use the data"*, **not**
*"the authors had not seen it"*. That distinction is the reason §5 exists.

## 4. What the calibration window cannot settle

A window in which every gate is passed by 10 points of margin, in which no cell sits near `Λ`
and no ladder's concentration sits near `2/3`, **cannot test either boundary.** It can only
show that the boundaries do not misfile anything in it. Whether `65%` is the right place for `Flat`, and whether `2/3` is the
right place to call a decline concentrated, are questions the forward window answers, and only
the forward window.

## 5. The day of publication belongs to neither window

Calibration is data through 2026-09-22. **The day this document is published belongs to neither
window, deliberately**: it was written while looking at data through 2026-09-22, so that day
cannot serve as a forward test, and folding it into calibration after the fact would move the
window to fit the rule. Anyone counting days will find it missing; it is missing on purpose,
and this paragraph is why there is no silent hole. **The forward window opens at 00:00 UTC on
the day after publication, whatever day that turns out to be** — which is what makes the
window's start unfalsifiable rather than asserted.

## 6. What the forward window reports

Each calendar month, starting from the opening of the forward window:

1. **Every change of a ladder's state**, with the two states, the blocks on either side, and the
   round-trip values that carry them. **Zero changes is a result and gets reported.**
2. Ladders evaluated, so the change rate has a denominator.
3. Any ladder that could not be evaluated, and why.
4. The current state of every ladder, so a label can be read without reading the history.

## 7. What would make this wrong

- **The labels churn.** A ladder that changes state more than once per month averaged over three
  months means the states are not states — the ladder is moving inside one of them and the
  boundary is cutting noise. Since within-day dispersion in these cells is at or near zero,
  churn cannot be explained as measurement noise, which makes this condition sharper here than
  it would be elsewhere.
- **A ladder changes while its inputs do not.** Concretely: a state change with no change in the
  winning pool, its fee, or the pool's composition as recorded in the same round. That is a
  measurement or a classification fault and is reported as one, not as a finding.
- **The level boundary never separates anything.** If, over the forward window, no ladder is ever
  in `Collapse` and no `Flat` ladder approaches `65%`, then the boundary is not doing work in
  this population and the four-state scale is really a three-state one. That is a result about
  the scale, not about the market, and it is reported as such.
- **The shape boundary never separates anything.** Symmetric with the condition above, and a
  live risk rather than a hypothetical one: in the calibration window only three of nine tokens
  reach the shape test at all, and they fall `Switch · Switch · Slope`. If every ladder reaching
  the forward window's shape test lands on the same side of `2/3`, that boundary is doing no
  work and the scale is three states, not four. Reported as a result about the scale.
- **External validity — the strongest condition in this section, because it is the use case
  itself.** A ladder classified `Flat` is liquidated on chain at a material discount. That
  falsifies the `65%` derivation, or the assumption that liquidation happens at the threshold
  it is derived from. Unlike every other condition here, it does not depend on this project's
  instruments at all — it depends on real liquidation events. **It may also go untriggered for
  a long time**, in which case the report says "not assessable this period" and states the date
  from which it becomes assessable. A condition that cannot be evaluated is not a condition
  that passed.

## 8. What this does not do

It does not predict. It does not say whether a holder can exit. It does not set a trading
rule, an alarm, or a threshold anyone should act on: **the alarm threshold is a client's risk
parameter and is not this document's to set.** The boundaries here classify a measurement;
they do not decide anything about a position.

## 9. Recomputing a cell — two levels

These correspond to the two anchors this project already uses.

**Level 1 — recompute the hash. No archive endpoint, no key, no script of ours.** The
canonical preimage is nine fields per record (`block · sell_sym · side · size_usd · route ·
amount_in_raw · mid_amount_raw · amount_out_raw · status`), all of which are in the published
per-quote records (`data/*/quotes.jsonl.gz`). Recomputing `roundKeccak` from those bytes
establishes that the published record has not been altered since publication. This is the git
anchor.

**Level 2 — replay the call. Requires an archive endpoint.** Re-issuing the Quoter calls at the
pinned block reproduces the returns themselves and establishes that the returns were real.
Robinhood Chain's public endpoint keeps only a short rolling window of state — between about
3,100 and 5,900 blocks, roughly five to ten minutes — so a round taken inside that window can
be replayed with no key and no archive access; anything older needs an archive endpoint. This
is the on-chain anchor.

**Stated plainly, because it is the load-bearing sentence of this document:** a reader who
wants to check *the arithmetic* needs nothing but the published bytes. A reader who wants to
check *the measurement* needs an archive endpoint.

## 10. What Release 34-106402, Condition G does not require

Transcribed from the order itself, not from a summary: `34-106402.txt` lines 800–815.

    PDF  sha256 67bfb89a0d2497787e6366c716312097e921198b82cb152491b7cf7a30360b18
    txt  sha256 30e90be4051acd26b19eab8300f73097e5852fd6f87c1eb695f43b5bfb0e0667

> **G. Transaction Transparency**
>
> A TSV must make U.S. dollar-denominated data concerning transactions freely and publicly
> available in a machine-readable format for all transactions within the past thirty (30)
> days. The transaction data must be updated within ten (10) minutes of the occurrence of
> any transaction and include, at minimum, the following: (i) the symbols for each Tokenized
> NMS Stock and paired asset (non-security crypto asset, tokenized money market fund, or
> Tokenized NMS Stock), (ii) the transaction price, (iii) the transaction size, (iv) the
> transaction time at the AMM Liquidity Pool, and (v) the transaction direction. In addition,
> the TSV must provide information pertaining to the AMM Liquidity Pool and its smart
> contract address, daily asset pair share volume, and end-of-day size of the AMM Liquidity
> Pool per asset pair.

### Field by field, against RTR

| Condition G field | What RTR needs it for |
|---|---|
| (i) symbols of stock and paired asset | identifies the pair — **sufficient** |
| (ii) transaction price | a price that was *taken*; RTR needs the price a size *would* get |
| (iii) transaction size | the sizes that were traded, not the sizes asked about |
| (iv) transaction time at the pool | a timestamp; RTR pins a **block**, which is not required |
| (v) transaction direction | one leg; RTR is two legs through the same pool |
| AMM pool and smart contract address | identifies the pool — **sufficient, and this is the part that changes things** |
| daily asset pair share volume | a daily scalar |
| end-of-day pool size per pair | one scalar per pair per day |

### The column that is absent

**Every required field describes a transaction that happened. None describes what would
happen to a transaction that has not happened.**

That is not a gap in coverage; it is a gap in kind, and it is self-selecting. Executed trades
are the trades that were worth executing. Nobody executes the trade that returns three cents
on the dollar, so that trade never appears in any compliant disclosure — and it is precisely
the trade a lender is forced into during a liquidation.

Two consequences follow from the field list, each re-checked against the transcription above:

- **The fee of the route is not a required field.** Price, size, direction, pool address,
  daily volume and end-of-day pool size are required; the fee charged by the pool that would
  win a given route is not among them. A venue can comply with Condition G in full, and a
  reader can still not discover from the disclosure that the only available route charges 88%.
- **Pool size is a scalar, not a curve.** One end-of-day number per pair says how much is in
  the pool. It does not say what comes back out at `$1,000`, or at `$100,000`, and those two
  answers can differ by three orders of magnitude for the same pool on the same day.

### One measured example

QQQ on Robinhood Chain, medians from 2026-09-15 onward:

    $100 → 6.58%      $1,000 → 1.93%      $10,000 → 0.26%      $100,000 → 0.03%

**The mechanism is the fee, not the depth.** Across 48 rounds a day the winning pool is
constant: **70% at $1,000, and 88% at $10,000 and above.** A round trip pays the fee twice,
so the arithmetic ceiling through a 70% pool is `(1 − 0.70)² = 9.00%`, and through an 88%
pool `(1 − 0.88)² = 1.44%` — before any price impact at all. The measured figures sit below
those ceilings, which is what price impact on top of the fee looks like.

⚠️ The fee of the winning route at `$100` is not asserted here; the two fees above are the
ones that were measured per size.

This distinction is the whole point of naming the mechanism. "The pool is thin" invites the
reply *then split the order* — and splitting works against thinness. It does not work against
a fee: every slice pays the same 88%. A required disclosure that reports price, volume and
pool size will show this pool as one with liquidity in it, because it has liquidity in it.
What it does not show is that the liquidity is behind a toll.

**One objection to pre-empt.** A reader may answer that fees are recoverable from the
disclosed trade prices. They are not, without a reference price — the trade price alone does
not separate the fee from the market, and choosing a reference is exactly the benchmark
problem §1 exists to avoid.

⚠️ **Scope.** The order's volume limits compare traded volume to average daily volume in the
underlying, which is a different quantity from RTR and is not a substitute for it. And the
order does not permit leverage through the venue, so lending protocols that accept these
tokens as collateral sit outside this framework — which is where the question *can this be
liquidated* actually binds.

## 11. Positions

> 🔴 **UNATTESTED.** The declaration below is the operator's to make, and it has not been made.
> This section is published in that state **deliberately**: everything the tooling can check is
> checked and recorded beneath it, and the four things the tooling cannot reach are named at the
> end, so the verified half and the outstanding half are both visible. **Read it as an unfinished
> section, not as a declaration — do not cite the sentences below as made.** Per this document's
> own rule the attestation is appended as an addendum rather than inserted here, which is why
> the registration does not wait on it.

**As of 2026-09-22, the operator holds no position in any tokenized stock measured on this
page, and does not trade on any venue measured on this page.** Declared addresses:

    0x9d55010a9Cedb34aA1c5A94984ad0e076ec135E2
    0x4eFAE5B817d561602F17411C716c8C03211D9D9b

**What this establishes, and what it does not.** It is a statement by the operator about the
operator's own holdings and activity. A position in a measured tokenized stock held at a
declared address would contradict it, so it is falsifiable to that extent. It is **not** a
proof that no other address exists, and no such proof is possible.

**The falsifiable half, checked — all of it at one block, `69,570,738`.**

| check | 0x9d55…35E2 | 0x4eFAE5B8…9D9b |
|---|---|---|
| nine tokenized stocks, `balanceOf` | all zero | all zero |
| Uniswap v4 position NFT, `balanceOf` | 0 | 0 |
| native ETH | 0 | 0.000006788 |

    cast call <token> "balanceOf(address)(uint256)" <address> --rpc-url <rh mainnet>
    cast call 0x58daec3116aae6d93017baaea7749052e8a04fa7 "balanceOf(address)(uint256)" <address>

The dust on the receiving address is not a tokenized-stock position; it is recorded so that a
reader who looks does not find it unexplained.

**Why the second row exists, and how the contract was found.** Uniswap v4 holds all pool
liquidity inside the `PoolManager` singleton rather than in the addresses that supplied it, so
a token-balance check cannot see a liquidity position: **an address can be a liquidity
provider while every token balance it holds is zero.** The periphery path can be checked
directly, because liquidity supplied through Uniswap's `PositionManager` is an ERC-721. That
contract was identified from the chain rather than from a directory — scanning
`ModifyLiquidity` on the known `PoolManager` gives the senders, and this is the ERC-721 among
them (`name` "Uniswap v4 Positions NFT", `symbol` "UNI-V4-POSM") whose `poolManager()` returns
the `PoolManager` this project already uses.

**What is still unchecked.** The same scan shows other contracts modifying liquidity directly
against `PoolManager` without being ERC-721s, because v4 keys a raw position by its calling
contract rather than by a token. A position held that way is invisible to this check, as is
any other address and any other chain. That residue is the operator's to attest. **The larger
gap — that a balance check sees no liquidity position at all — is closed.**

The scope is deliberately narrow. It covers the tokenized stocks this project measures and the
venues it characterises. It does **not** claim anything about holdings in other assets — this
report also measures tokens such as WETH and SOL in its aggregator section, and a claim of no
position in *those* would be a different and much broader statement.

This is a statement about a moment. Updates are appended, not corrected in place.

## Fixing this document

Changing `RTR`'s definition, the cell set, the boundaries `Λ` or `2/3`, the four state names,
or any falsification condition in §7 ends this registration and starts a new one with a new
date. **This file is never edited.** The date on which it first appears in the public
repository is the evidence that it predates the window it is evaluated on.
