# The accrual multiplier on Robinhood Chain tokenised stocks

**How to read it, what it is today, and what it does to an accounting that assumes 1 token = 1 share**

Prepared 2026-09-29 by Lianqing Hu · github.com/dirkdiggler1026/executability-report · dirkdiggler871026@gmail.com

Written as the technical attachment to a letter to desks that set collateral parameters for
tokenised equities, and published so that it can be checked rather than believed.

Everything below is re-derivable from a public RPC in about a minute (§4). Nothing here is anchored,
and no number is quoted from a vendor.

Labels used throughout: **MEASURED** = reproducible from public chain data by §4 · **INTERPRETED** = our
reading of measured facts · **OPEN** = not established here.

---

## 1. What is on the chain (MEASURED)

Every ERC-20 transfer of a tokenised stock on Robinhood Chain (chainId 4663) is accompanied by a second
log, emitted by the same token contract, carrying the same sender and recipient:

```
topics[0] = 0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802
topics[1] = from            topics[2] = to
data      = (w0, w1)  with  w0 = the transferred amount   and   w1 = floor(w0 × k)
```

So the ERC-20 `Transfer` event shows one number, this log shows two, and **k is the ratio of the two**:
`k = w1 / w0`. The event's declared name is not in the ABIs we could reach, so we treat it as
unlabelled. We found no view call returning k; whether one exists is **OPEN** — we did not enumerate
every selector. In practice k is readable only by decoding a transfer log.

Which side is shares and which is tokens is **OPEN** (the log alone does not say). The ratio is k either
way, and it is the ratio that breaks a 1:1 assumption.

| token | address | k (2026-09-29) |
|---|---|---|
| SPY | `0x117cc2133c37b721f49de2a7a74833232b3b4c0c` | 1.001717991187472003 |
| NVDA | `0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec` | 1.000775159164630595 |
| QQQ | `0xd5f3879160bc7c32ebb4dc785f8a4f505888de68` | 1.000700791241405425 |
| AAPL | `0xaf3d76f1834a1d425780943c99ea8a608f8a93f9` | 1.000566080061092436 |
| GOOGL | `0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3` | 1.000193924414112587 |
| TSLA | `0x322f0929c4625ed5bad873c95208d54e1c003b2d` | 1.000000000000000000 |
| GME | `0x1b0e319c6a659f002271b69db8a7df2f911c153e` | 1.000000000000000000 |
| AMC | `0x05a3d1cd21d0c88145e82600e62e7e496e0f222b` | 1.000000000000000000 |
| RDDT | `0x05b37fb53a299a1b874a619e1c4c404d52c36f4c` | 1.000000000000000000 |

## 2. k today, and how tightly it is pinned (MEASURED)

Window **2026-09-29 10:37:14Z → 11:31:32Z** (blocks 75,590,000–75,622,284). For each asset, take every
log in the window and intersect the intervals `k ∈ [w1/w0, (w1+1)/w0)` that each log implies. For all
nine assets the intersection is **non-empty** — one constant k explains every log in the window — and
narrower than 10⁻¹⁸, i.e. k is pinned to more digits than are printed above. For QQQ the interval is
`[1.000700791241405424993835484132337316216, 1.000700791241405425087210042175461916910)`,
9.3 × 10⁻²⁰ wide.

| token | logs in window | first / last log block | failed ranges |
|---|---|---|---|
| NVDA | 4,399 | 75,590,035 / 75,622,280 | 0 |
| SPY | 2,651 | 75,590,005 / 75,622,277 | 0 |
| AAPL | 1,013 | 75,590,168 / 75,621,996 | 0 |
| GME | 568 | 75,590,297 / 75,622,201 | 0 |
| TSLA | 514 | 75,590,024 / 75,622,278 | 0 |
| GOOGL | 431 | 75,590,355 / 75,621,123 | 0 |
| AMC | 398 | 75,590,025 / 75,621,190 | 0 |
| QQQ | 313 | 75,590,147 / 75,621,290 | 0 |
| RDDT | 41 | 75,594,811 / 75,622,008 | 0 |

Four of the nine are exactly 1 in every log: TSLA, GME, AMC, RDDT. **INTERPRETED**: those four pay
nothing through this mechanism. **MEASURED**: the ratio is exactly 1 in every one of those logs.

## 3. One change, bounded to 32 seconds (MEASURED)

QQQ, exhaustive over the four hours 2026-09-21 22:00Z → 2026-09-22 02:00Z:

```
1,421 logs at k = 1.000000000000000000   ending   block 69,216,810  2026-09-22 00:10:33Z
2,398 logs at k = 1.000700791241405425   starting block 69,217,129  2026-09-22 00:11:05Z
319 blocks, 32 seconds between the last log of one value and the first log of the next
```

The multiplier changed in that window, and **nothing announces it**: the only visible difference is
that the two words in the transfer log stop being equal. The bound is a pair of transfers, not an
instant, because a change with no transfer in between emits nothing at all.

An earlier note in the repository bounds the same change to 37 seconds (block 69,216,761); both
bounds hold on the same event, and this one is tighter because it is an exhaustive scan of every
transfer in the surrounding four hours rather than a bisection.

## 3b. The rest of September, and one distinction that is easy to get wrong (MEASURED)

Read at 47 points per asset across 2026-09-01 → 09-29, about 15 hours apart, intersecting the exact
intervals of every log in each window:

| token | September | when it moved, to the resolution of the grid |
|---|---|---|
| NVDA | rose from exactly `1` to `1.000775159164630595` | between 2026-09-09 18:11Z and 2026-09-10 09:05Z |
| GOOGL | rose from exactly `1` to `1.000193924414112587` | between 2026-09-15 09:36Z and 2026-09-16 00:44Z |
| SPY | rose from exactly `1` to `1.001717991187472003` | between 2026-09-17 21:34Z and 2026-09-18 12:28Z |
| QQQ | rose from exactly `1` to `1.000700791241405425` | between 2026-09-21 15:15Z and 2026-09-22 06:07Z — bounded to 32 s in §3 |
| AAPL | **did not move**: `1.000566080061` at every one of the 46 points that had a log | its step is **before** 2026-09-01, outside this window |
| TSLA, GME, AMC, RDDT | exactly `1.000000000000000000` at every point that had a log (46, 46, 45, 46 of 47 respectively) | never moved through this mechanism |

**Being above 1 and having moved in the window are statements about different assets.** Four moved
inside the window (NVDA, GOOGL, SPY, QQQ). One is above 1 and did not (AAPL) — its multiplier was
already `1.000566080061` on 2026-09-01, so nothing here bounds when it stepped. Four are exactly 1.
An earlier draft of this page grouped AAPL with the movers, by reading "above 1 today" as "stepped
this month"; the two are not the same claim, and grouping them is the error this table exists to
prevent. The window bounds above are the resolution of the scan, not a claim about the instant: a
change with no transfer in between is invisible (§5).

The repository's own September reading (`measurements/tsv-volume/`, 28 complete days, 9,786,117
swaps, 0 failed ranges) sorts the same nine into the same three groups: it is a second read of the
same logs, on a coarser grid and by a different method.

Two of the 423 samples failed on the node's 10,000-log-per-query cap — one point each for NVDA and
AMC — and are recorded as gaps rather than as "unchanged", in the run's own output and in
`accrual-index-month-2026-09.json` next to this file. A sample with no log at all is also recorded
as no observation, never as stability.

## 4. Reproduce it (no dependencies beyond Python's standard library)

```python
import json, urllib.request
from decimal import Decimal, getcontext
from fractions import Fraction
getcontext().prec = 40
RPC   = "https://rpc.mainnet.chain.robinhood.com"        # any node on chainId 4663 will do
TOKEN = "0xd5f3879160bc7c32ebb4dc785f8a4f505888de68"     # QQQ
TOPIC = "0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802"
def call(m, p):
    req = urllib.request.Request(RPC,
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
        {"Content-Type": "application/json", "User-Agent": "k/1.0"})   # this node 403s empty UAs
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["result"]
head  = int(call("eth_blockNumber", []), 16)
logs  = call("eth_getLogs", [{"address": TOKEN, "topics": [TOPIC],
                              "fromBlock": hex(head - 20000), "toBlock": hex(head)}])
pairs = [(int(l["data"][2:][0:64], 16), int(l["data"][2:][64:128], 16)) for l in logs]  # (w0, w1)
lo = max(Fraction(w1, w0)     for w0, w1 in pairs)   # any valid k satisfies k >= w1/w0
hi = min(Fraction(w1 + 1, w0) for w0, w1 in pairs)   # ... and k <  (w1+1)/w0
d = lambda f: str(Decimal(f.numerator) / Decimal(f.denominator))                     # noqa: E731
print(len(logs), "logs   k in [", d(lo), ",", d(hi), ")   one constant k fits:", lo < hi)
```

Exact integer arithmetic, no floats: `lo < hi` means one constant k explains every log in the window,
and `lo >= hi` means the multiplier changed inside it. The scripts that produced §2 and §3 are the
same idea with block-walking added: `code/read_accrual_index.py` and `code/accrual_index_history.py`
in the repository above, which run from a plain clone against the public endpoint.

## 5. What this does not say (OPEN)

- **What drives it.** Dividend, withholding, fee, share-lending income — the log carries no reason
  field, and we have not seen the operator's documentation. **OPEN.**
- **Whether it can decrease.** Every window we scanned shows non-decreasing values. Not proven
  monotone. **OPEN.**
- **Whether it can change with no transfer at all.** Not observable from logs: if it changed and
  nobody transferred, nothing would be emitted, and we would see exactly what we see now. **Absence
  of these logs is not evidence that k did not change.**
- **Whether 1 token = 1 share.** We have not verified the issuer's terms. **OPEN**, and it matters:
  k is only the accrual part of the token-to-share ratio.
- **Whether the market prices k.** We tried to test it and the test **failed**, for a reference-data
  reason worth knowing independently: the equity price feeds available here update on an
  86,400-second heartbeat, so comparing an on-chain price to them at 30-minute granularity compares
  it to a staircase. The pre-registered control (TSLA, k ≡ 1) fired and the test was published as a
  failure, with all three series and the raw numbers:
  `github.com/dirkdiggler1026/executability-report/tree/main/measurements/index-priced-test`.
  The question stays **OPEN**; answering it needs a reference without the multiplier.

## 6. If your accounting assumes 1 token = 1 share (INTERPRETED)

Then k − 1 is your error term, and it is **step-wise, unannounced, and readable only from transfer
logs**: currently 17.2 bp for SPY, 7.8 bp NVDA, 7.0 bp QQQ, 5.7 bp AAPL, 1.9 bp GOOGL, 0 for TSLA,
GME, AMC, RDDT.

Which steps we have actually bounded, and which we have not: QQQ's, to a 32-second window (§3), and
the other three movers only to the ~15-hour grid of §3b. AAPL's step is not bounded here at all,
because it happened before 2026-09-01. Reading "above 1 today" as "moved recently" is the one
mistake this page most wants to prevent, because it looks right and is checkable.

Two rounding notes, so a monitor does not mislead itself: the ratio in a log reads exactly 1 for
amounts below `1/(k−1)` wei (≈10⁻¹⁵ tokens — we saw 5 such logs out of 561 for AAPL in one window),
and the two words only reveal k to the precision of the amount moved.

---

**Provenance.** Read 2026-09-29 between 11:18Z and 11:31Z (chain head 75,614,339 → 75,622,284) against
`rpc.mainnet.chain.robinhood.com`. §2 and §3 scans: 0 failed ranges. One earlier scan hit the node's
10,000-log-per-query cap; the range was halved and the refusal recorded — nothing was skipped
silently. The multiplier values here reproduce, to nine decimals, an independent read taken
2026-09-28 on a different window, and the block at which QQQ's new value first appears (69,217,129)
is the same block addendum 3 of the repository's pre-registration records for that step.
Instruments: `code/read_accrual_index.py`, `code/accrual_index_history.py`, `code/accrual_index_samples.py`.
