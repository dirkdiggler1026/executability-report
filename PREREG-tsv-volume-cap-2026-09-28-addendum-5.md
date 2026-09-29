# Addendum 5 to `PREREG-tsv-volume-cap-2026-09-28.md`

**Written 2026-09-29, before the run.** Corrects two wrong counts in §2 ③ and replaces the
pool set with one that does not change under the run's feet. Found by trying to start the run
and reading the file it names.

---

## 1. The counts in §2 ③ are wrong, and they came from the wrong artifact

§2 ③ reads "every pool in the enumeration (41 (asset, pool, quote) rows)" and "USDG-quoted
pools only (27 rows)".

```
41 / 27  is the size of the list in enumerations/MISSING-71909188.json -- the list
         RECONSTRUCTED from the quote rows of the series' first four rounds. It is not
         an enumeration at all.

the actual enumerations, all published:
  pools-72764101.json   2026-09-26   63 pools   (USDG 44 / WETH 19)
  pools-73619413.json   2026-09-27   55         (USDG 40 / WETH 15)
  pools-74476245.json   2026-09-28   56         (USDG 41 / WETH 15)
  pools-75336022.json   2026-09-29   56         (USDG 41 / WETH 15)
```

A count taken from one artifact and used to describe another. Same family as the state root
reported as a revert selector, and as the first-screen figure that had stopped being true —
a number that looks specific, is checkable, and is about something else.

The definitions in §2 ③ — *all enumerated pools* and *USDG-quoted only* — are unchanged and
were never wrong. Only the parenthetical counts were.

## 2. The pool set moves daily, so naming "the enumeration" is not enough

The list is re-enumerated at 03:30 UTC every day, and it moves: 63, then 55, then 56, 56.
A run that says "the enumeration" produces a different answer depending on the day it is
started, which makes it unreproducible for the worst possible reason — not a chain change, a
scheduling accident.

> **Registered replacement for §2 ③.** The pool set is the **union of every archived
> enumeration published at the time of the run**, deduplicated on `(asset, pool, quote)`.
> Each pool carries the list of enumeration blocks it appeared in.
>
> ```
> union of the four archived at 2026-09-29:  66 pools  (USDG 47 / WETH 19)
>   present in all four enumerations:        53
>   present in exactly one:                  10
> reading A  all 66
> reading B  the 47 USDG-quoted
> ```
>
> The union is used because every gap in §3 runs the same way: a pool that was enumerated once
> and not again still traded, and dropping it removes volume that happened. The union cannot
> add volume that did not happen — a pool either has Swap events in the window or it does not.

This also replaces the sentence in §2.1 that said the pool set was "enumerated on 2026-09-26".

🔴 **What the union does not fix.** It is a union of enumerations that all ran *after* the
window opens on 2026-09-01. A pool that existed in early September and had stopped classifying
by 09-26 is in none of them. §2.1's coverage line still applies and is now computed against
the union: each pool's creation block is read, and the run reports how many of the 66 could
have traded for the whole window.

## 3. Status

```
MEASURED     the four enumerations' contents and their union; the counts above
CORRECTED    §2 ③'s parenthetical counts, which described a different file
OPEN         unchanged -- the three dependencies in §4 of the registration
```

## 4. What this addendum does not do

- It does not change the numerator formula, the index rule, the symbol set, the window, the
  direction rule, the attribution limit, or the test in addenda 3 and 4.
- It does not claim the union is complete. §3 as amended by addendum 1 still governs: the
  figure is an estimate over a stated pool set, and the set is now stated as a union of
  published files rather than as whichever file happened to be current.
