# Pre-registration — independent computation of the TSV volume-cap numerator

**Written 2026-09-28, before any volume figure was computed.** No numerator, denominator or
ratio existed when this was written, and none was consulted. It freezes the definitions, and
it states in advance what the result can and cannot be used to conclude — because the second
half is worth nothing if it is written after the number is known.

The run's result is **not** a condition of publishing it.

---

## 1. What is being computed, and why it is worth computing

SEC Release No. 34-106402 (File No. 4-927), §II.F, caps how much of an NMS stock a Tokenized
Securities Venue may trade in tokenized form:

> Tier 1 Tokenized NMS Stock traded on a TSV under the TSV Exemption cannot exceed 75 symbols
> traded and **0.25 percent of the average daily share volume during the prior month** in the
> relevant NMS stock as reported by an effective transaction reporting plan. Tier 2 Tokenized
> NMS Stock … cannot exceed 250 symbols traded and **2.5 percent** …
>
> The percentage … shall be calculated using **the average daily share volume of a given
> Tokenized NMS Stock traded on the TSV as the numerator**, and the average daily share volume
> of the NMS stock (as reported by an effective transaction reporting plan) as the denominator.

It carries a stated consequence, which is why the arithmetic is not academic:

> After the first time a TSV exceeds the volume threshold in a given Tokenized NMS Stock, each
> time the TSV subsequently exceeds the volume threshold in the applicable Tokenized NMS Stock,
> the TSV must **immediately pause trading in such Tokenized NMS Stock for three months**.

Every input is public: the numerator is on chain, the denominator is published by the
transaction reporting plans, and the tier assignment is Appendix A of the LULD Plan. So the
figure is independently computable by anyone, and this registration is about computing it the
same way twice rather than about having access nobody else has.

## 2. The six definitions, frozen

```
① UNIT          The denominator is a SHARE count. The numerator must therefore also be a
                share count, not a dollar amount.
                🔴 The token:share ratio is NOT established -- see §4.1. This is handled as a
                   SENSITIVITY, not as an assumption: every ratio is reported as "X% if one
                   token is one share; 10X% if one token is one tenth of a share", with the
                   ratio named as an open dependency. A number that silently assumes an
                   unverified constant is the failure this project keeps finding.

② SYMBOL SET    All nine assets the collector already covers, with no selection:
                AAPL AMC GME GOOGL NVDA QQQ RDDT SPY TSLA.
                Fixing the set before the run is the point; picking symbols after seeing
                which look interesting is the same defect as not looking at all.

③ POOL SET      Two readings, reported side by side, neither chosen over the other:
                  A  every pool in the enumeration (41 (asset, pool, quote) rows)
                  B  USDG-quoted pools only (27 rows)
                Reason for both: the order caps volume "traded on a TSV", and which pools
                belong to a given TSV is a legal fact that is not visible on chain.

④ DIRECTION     The stock side of each swap, absolute value, counted once per swap. A buy of
                100 shares and a sale of 100 shares are 100 shares each, not 200.

⑤ WINDOW        One calendar month: 2026-09-01 00:00:00Z to 2026-09-30 23:59:59Z, by block
                timestamp. Both numerator and denominator are averaged over that same month.
                🔴 Registered as an INTERPRETATION, not as the order's text: the order says
                   "during the prior month" and does not define it further. Reading it as a
                   calendar month is our reading, and is labelled as ours.
                Both sides of the ratio are averages of daily share volume, per the order.

⑥ ATTRIBUTION   The order requires a TSV to aggregate with its affiliated TSVs. Affiliation is
                a legal fact and is not visible on chain. Our figure is therefore the volume
                through the pools we can see, and is declared as such wherever it appears.
```

### 2.1 Patch to ③, registered here rather than discovered later

The pool set was enumerated on 2026-09-26. Using it to scan a window that opens on 09-01 will
miss any pool that existed during the month and no longer classifies. **This gap is to be
measured, not described**: each pool's creation block is read, and the run reports *N of 41
pools covered the whole window, M appeared partway through*, with the dates. An unmeasured
"the list may be incomplete" is a sentence; a count is a fact.

## 3. What the result can and cannot support — registered before the number exists

```
Every construction above makes the numerator a LOWER BOUND:
    the pool set is not claimed exhaustive
    pool-to-TSV attribution is not visible on chain
    affiliated-TSV aggregation is a legal fact we cannot observe
    a backward scan uses a pool set enumerated at the end of the window

⇒ A lower bound can establish that a threshold WAS exceeded.
⇒ A lower bound can NEVER establish that a threshold was not exceeded.
```

> **Registered reading.** If the computed ratio comes out far below the cap, **that is not
> evidence of compliance** and will not be reported as such. The only sentence the figure
> supports in that direction is: *the visible portion alone is X% of the cap.* The words
> "within the limit", "compliant", and "does not exceed" are not available to this measurement
> and will not appear in reporting of it.

This is written now because it is the claim most likely to be made after the fact. A figure
far below a threshold reads as reassurance to everyone who did not do the arithmetic, and the
person best placed to prevent that reading is the person who produced the figure.

## 4. Three external dependencies, and the rule for each

None of these is on chain. Each is to be **looked up and cited, never inferred**; where a
lookup fails the field is left empty and the run says so.

### 4.1 The token:share ratio — the foundation, and it is not established

```
measured   All nine tokens carry decimals = 18 and their on-chain reference mids sit at the
           order of magnitude of the underlying's per-share price (AAPL 340.41, AMC 2.93,
           GME 23.65, GOOGL 343.70, NVDA 224.82, QQQ 745.21, RDDT 150.86, SPY 771.73,
           TSLA 372.47, all at 2026-09-27T23:01:52Z). Nine simultaneous agreements of
           magnitude is consistent with one token being one share.
absent     The contracts declare no ratio. sharesPerToken(), underlying(), ratio(),
           conversionRate(), exchangeRate(), assetsPerShare(), isin(), cusip() are all absent
           from the QQQ token 0xd5f3879160bc7c32ebb4dc785f8a4f505888de68; name() returns empty.
status     CONSISTENT WITH 1:1, NOT ESTABLISHED. The authoritative source is the issuer's
           terms, which is a document, not a chain read.
```

### 4.2 Tier assignment — Appendix A of the LULD Plan

The order states the tiers *are* the LULD Plan's tiers, and that the list is public:

> The NMS stock that comprises Tier 1 and Tier 2 of the LULD Plan are specified in Appendix A
> to the LULD Plan, which is publicly available on the LULD Plan website.
> See https://www.luldplan.com/plans.

Each symbol's tier is to be read from that appendix with the retrieval date recorded.
🔴 Tier is **not** to be inferred from company size or index membership. QQQ and SPY are ETPs
and AMC, GME and RDDT are the cases where a guess is most likely to be wrong; those three in
particular are left blank if the appendix cannot be read.

### 4.3 Denominator — the transaction reporting plans

The order's footnote defines the phrase: the CTA/CQ Plans and the Joint Self-Regulatory
Organization (UTP) plan. The denominator must come from the same source and the same month as
the numerator; a volume figure from any other vendor is a different quantity wearing the same
name.

## 5. Status labels used in reporting this

Each statement in the output carries one, in the same spirit as the error archive's
`data-found`:

```
MEASURED    read from the chain or from a cited document, with the read recorded
INTERPRETED our reading of text that admits another (§2 ⑤ is one)
OPEN        a dependency not yet resolved; the field is empty and the gap is named
```

## 6. Environment, so a third party hits no wall we already found

```
Swap event topic0   0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67
                    keccak("Swap(address,address,int256,int256,uint160,uint128,int24)")
endpoint            https://rpc.mainnet.chain.robinhood.com -- the public one. It accepts
                    getLogs over ~2,000,000-block ranges and caps results at 10,000.
slicing             One day per query. Measured 2026-09-28 on the busiest pool
                    (0xd60a5d14db690b7afad71f76b108071d7175597d): 1,882 Swap events in
                    855,765 blocks (24 h) -- a fifth of the cap, so a day is safe.
chain rate          ~9.9 blocks/second, so a calendar month is ~25.7 million blocks.
🔴 no archive key   This scan reads LOGS, not historical state, so it does NOT need an archive
                    endpoint. (An Alchemy free tier caps getLogs at 10 blocks and is useless
                    here; the archive key this project holds is for historical eth_call and is
                    not used by this run.) Stated so that nobody repeats the wrong experiment.
```

## 7. What this registration does not do

- It does not compute a denominator, assert a tier, or state a ratio. Those are §4, and they
  are open at the time of writing.
- It does not register a threshold of our own. The only thresholds are the order's.
- It does not claim the pool enumeration is complete. §2 ③ and §2.1 say the opposite, and §3
  turns that into the limit on what may be concluded.
- It does not assert anything about any venue's compliance. It registers how a number would be
  computed, and what that number cannot be used to say.
