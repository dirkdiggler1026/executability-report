#!/usr/bin/env python3
"""Numerator for the TSV volume-cap test, per PREREG-tsv-volume-cap-2026-09-28 + addenda 1-5.

    python3 tsv_volume.py --day 2026-09-15          one day, for verification
    python3 tsv_volume.py --from 2026-09-01 --to 2026-09-30

Writes <out>/tsv-volume-<from>_<to>.json. Reads logs from the PUBLIC endpoint: this needs no
archive key (addendum, registration §6).

What it computes, and every choice here is registered rather than decided at runtime:

  pool set     union of every archived enumeration, deduped on (asset, pool, quote)   add-5
  numerator    stock-side |amount| of each Swap, counted once                         §2 ④
  unit         shares = tokens x index(asset, block); BOTH reported                   add-2
  index        from the transfer-event ratio; observed / carried / none               add-4
  readings     A = all pools, B = USDG-quoted only                                    §2 ③ / add-5
  coverage     each pool's first-seen block against the window                        §2.1 / add-5

🔴 The word "lower bound" is not used about the total, and neither are "at least" or
   "no less than" (addendum 1). The total is an estimate over a stated pool set.
🔴 "within the limit", "compliant" and "does not exceed" are not available to this
   measurement at all (§3).
"""
from __future__ import annotations

import argparse
import bisect
import collections
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evm import keccak256                                        # noqa: E402

RPC = "https://rpc.mainnet.chain.robinhood.com"
# The enumerations are published; from a clone of the report repository this is
# data-oneside/enumerations. TSV_ENUM_DIR overrides it.
ENUM_DIR = os.environ.get("TSV_ENUM_DIR") or (
    "data-oneside/enumerations" if os.path.isdir("data-oneside/enumerations")
    else "/root/predict-data/dexfeed_data/oneside_depth/enumerations")
SWAP = "0x" + keccak256(
    b"Swap(address,address,int256,int256,uint160,uint128,int24)").hex()
IDX_EV = "0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802"
LOG_CAP = 10_000          # the endpoint's result cap; a day is ~1/5 of it (§6)


def log(*a):
    print(f"{datetime.now(timezone.utc):%H:%M:%S} |", *a, flush=True)


# 🔴 2026-09-29 的一天验证跑:66 个池里 61 个失败,八个资产"0 条指数观测" ——
#    全部是 `Too Many Requests`，而下面这个判据当时写的是
#      "429" in m or "rate" in m.lower() or "limit" in m.lower()
#    "Too Many Requests" 一个都不含 ⇒ 限流【没被当成限流】，一次就放弃。
#    更坏的是 index_observations 把失败变成空列表 ⇒ "被限流"长得和"没有事件"一模一样。
#    同一个判据在 tools/feed_staleness.py 里是写对的 —— 两处各写一遍，一处写错。
def _is_rate_limited(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m or "too many requests" in m or "rate limit" in m
            or "rate-limit" in m or "exceeded" in m or "throttl" in m)


# 全局节流。公共端点是共享的，按它的节奏来，不要靠退避硬顶。
_MIN_GAP = float(os.environ.get("TSV_MIN_GAP", "0.35"))
_last_call = [0.0]


def post(payload, tries=6):
    last = ""
    for i in range(tries):
        gap = _MIN_GAP - (time.time() - _last_call[0])
        if gap > 0:
            time.sleep(gap)
        _last_call[0] = time.time()
        try:
            r = subprocess.run(
                ["curl", "-sS", "-m", "70", "-X", "POST", "-H",
                 "content-type: application/json", "-d", json.dumps(payload), RPC],
                capture_output=True, timeout=100)
            j = json.loads(r.stdout.decode())
        except Exception as ex:
            last = f"transport:{ex}"[:80]
            time.sleep(2 * (i + 1)); continue
        if "error" in j:
            m = str(j["error"].get("message", ""))
            last = m[:140]
            if _is_rate_limited(m):
                time.sleep(2.0 * (i + 1) ** 2)      # 2, 8, 18, 32, 50 秒
                continue
            return None, last                        # 合约/参数层的错：不重试
        return j.get("result"), ""
    if _is_rate_limited(last):
        last = f"rate-limited after {tries} tries: {last}"
    return None, last


def get_logs(addr, a, b, topic):
    return post({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [
        {"address": addr, "fromBlock": hex(a), "toBlock": hex(b), "topics": [topic]}]})


def block_ts(n):
    r, e = post({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                 "params": [hex(n), False]})
    return int(r["timestamp"], 16) if r else None


def head():
    r, _ = post({"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []})
    return int(r, 16)


def block_at(target_ts, lo, hi):
    """First block with timestamp >= target_ts. Plain bisection on the chain."""
    while lo < hi:
        mid = (lo + hi) // 2
        t = block_ts(mid)
        if t is None:
            lo = mid + 1; continue
        if t < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


# ---- pool set: the union, per addendum 5 -----------------------------------------
def pool_union():
    pools, seen_in = {}, collections.defaultdict(list)
    files = sorted(glob.glob(os.path.join(ENUM_DIR, "pools-*.json")))
    for p in files:
        d = json.load(open(p))
        b = d["enumerated_at_block"]
        for x in d["pools"]:
            k = (x["asset"], x["pool"].lower(), x["quote"])
            pools[k] = x
            seen_in[k].append(b)
    return pools, seen_in, [os.path.basename(f) for f in files]


# ---- index, per addenda 2 and 4 --------------------------------------------------
class IndexScanFailed(Exception):
    pass


# 🔴 指数是阶跃函数,所以【不需要】把每条事件都读回来。
#    第一版那样做,在 AMC 上一个 4 万块窗口就超过 1 万条上限 —— 而且它本来就浪费:
#    两次阶跃之间的几万条事件,携带的是同一个值。
#    改为:稀疏采样 + 对差异段二分定位阶跃块。产出与全量扫描等价,
#    前提是采样间隔内不会发生"跳上去又跳回来"——采样密度一并输出,由读者判断。
#
# 🔴 取值用【该窗口里 n0 最大的那条】。比值是 n1/n0,而 n1 是定点乘法后取整,
#    所以相对误差约 1/n0:小额转账的比值会偏。09-15 的一天验证里 AAPL 出现 111 个
#    "不同值",绝大多数是这种舍入,不是阶跃 —— addendum 2 里"零方差"那句
#    是小样本的假象,需要更正。
SAMPLE_SPAN = 1_500


def _index_sample(token, blk, span=SAMPLE_SPAN):
    """(ratio, block, n0) from the largest transfer in [blk, blk+span], or None."""
    r, e = get_logs(token, blk, blk + span, IDX_EV)
    if r is None:
        raise IndexScanFailed(f"{token} sample @{blk}: {e}")
    best = None
    for l in r:
        d = l["data"][2:]
        n0 = int(d[:64], 16)
        n1 = int(d[64:128], 16)
        if n0 and (best is None or n0 > best[2]):
            best = (n1 / n0, int(l["blockNumber"], 16), n0)
    return best


def index_steps(token, a, b, samples=26):
    """[(from_block, ratio)] -- a step table, plus the sampling record."""
    pts, gap = [], max(1, (b - a) // samples)
    x = a
    while x <= b:
        s = _index_sample(token, x)
        if s:
            pts.append(s)
        x += gap
    if not pts:
        return [], {"samples": samples, "hits": 0, "steps_bisected": 0}
    steps, bisected = [(a, pts[0][0])], 0
    for i in range(1, len(pts)):
        if abs(pts[i][0] - steps[-1][1]) > 1e-9:
            lo, hi = pts[i - 1][1], pts[i][1]
            lo_r = steps[-1][1]
            for _ in range(22):
                if hi - lo <= 1:
                    break
                mid = (lo + hi) // 2
                s = _index_sample(token, mid, min(SAMPLE_SPAN, max(1, hi - mid)))
                if s is None:
                    lo = mid + 1
                    continue
                if abs(s[0] - lo_r) <= 1e-9:
                    lo = s[1]
                else:
                    hi = s[1]
            steps.append((hi, pts[i][0]))
            bisected += 1
    return steps, {"samples": len(pts), "span": SAMPLE_SPAN,
                   "gap_blocks": gap, "steps_bisected": bisected,
                   "values": [round(v, 12) for _, v in steps]}


def index_for(steps, blk):
    """(ratio, source, from_block) -- observed / carried / none, per addendum 4.

    A step table entry applies from its block onward, so anything after the first step
    is 'carried' unless the block IS the step block."""
    if not steps:
        return None, "none", None
    i = bisect.bisect_right([s[0] for s in steps], blk) - 1
    if i < 0:
        return None, "none", None
    sb, r = steps[i]
    return r, ("observed" if sb == blk else "carried"), sb


# ---- swaps -----------------------------------------------------------------------
def swap_stock_amount(logrec, stock_is_token0):
    """|stock-side amount| of one Swap, counted once (§2 ④)."""
    d = logrec["data"][2:]
    a0 = int(d[:64], 16)
    a1 = int(d[64:128], 16)
    a0 = a0 - (1 << 256) if a0 >= 1 << 255 else a0
    a1 = a1 - (1 << 256) if a1 >= 1 << 255 else a1
    return abs(a0 if stock_is_token0 else a1)


def _logs_recursive(addr, a, b, failures, tag, depth=0):
    """getLogs over [a,b], halving when the endpoint refuses. Returns (logs, "") or (None, why).

    🔴 The two refusals that need splitting rather than retrying are the result cap and the
       query timeout: both mean "this range is too big", and both were reported as plain
       failures by the first version, losing five pools a day each.
    """
    r, e = get_logs(addr, a, b, SWAP)
    too_big = (r is None and ("exceeds limit" in (e or "") or "timed out" in (e or "")))
    if r is not None and len(r) < LOG_CAP:
        return r, ""
    if r is not None:
        too_big = True                       # at the cap: assume truncated, split
    if not too_big:
        failures.append(dict(tag, why=e, blocks=[a, b])); return None, e
    if b - a <= 1 or depth > 12:
        failures.append(dict(tag, why=f"irreducible: {e}", blocks=[a, b])); return None, e
    mid = (a + b) // 2
    r1, _ = _logs_recursive(addr, a, mid, failures, tag, depth + 1)
    r2, _ = _logs_recursive(addr, mid + 1, b, failures, tag, depth + 1)
    if r1 is None or r2 is None:
        return None, "partial"
    return r1 + r2, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--day")
    ap.add_argument("--out", default="/root/predict-data/dexfeed_data/tsv_volume")
    a = ap.parse_args()
    if a.day:
        a.d0 = a.d1 = a.day
    if not (a.d0 and a.d1):
        print("need --day or --from/--to", file=sys.stderr); return 2

    pools, seen_in, files = pool_union()
    tokens = {}
    for (asset, _, _) in pools:
        tokens.setdefault(asset, None)
    from rhchain import STOCKS
    for asset in tokens:
        tokens[asset] = STOCKS.get(asset)
    log(f"pool union: {len(pools)} from {len(files)} enumerations: {', '.join(files)}")

    H = head()
    d0 = datetime.strptime(a.d0, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    d1 = datetime.strptime(a.d1, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    days = []
    cur = d0
    while cur <= d1:
        days.append(cur); cur += timedelta(days=1)

    log(f"locating day boundaries for {len(days)} day(s) by bisection…")
    bounds = {}
    lo = 1
    for dt in days + [days[-1] + timedelta(days=1)]:
        b = block_at(int(dt.timestamp()), lo, H)
        bounds[dt.strftime("%Y-%m-%d")] = b
        lo = b
    log(f"  {min(bounds.values()):,} … {max(bounds.values()):,}")

    # index observations, once per asset over the whole span
    span_a = min(bounds.values())
    span_b = max(bounds.values())
    idx, idxrec = {}, {}
    for asset, tok in tokens.items():
        if not tok:
            continue
        try:
            st, rec = index_steps(tok, span_a, span_b)
        except IndexScanFailed as ex:
            log(f"  index {asset:5} FAILED: {ex}")
            idx[asset], idxrec[asset] = [], {"failed": str(ex)[:120]}
            continue
        idx[asset], idxrec[asset] = st, rec
        log(f"  index {asset:5} {rec['samples']:3} samples, {rec['steps_bisected']} step(s): "
            f"{rec['values']}")

    rows, failures = [], []
    for i, dt in enumerate(days):
        ds = dt.strftime("%Y-%m-%d")
        b0 = bounds[ds]
        b1 = bounds[(dt + timedelta(days=1)).strftime("%Y-%m-%d")] - 1
        per = collections.defaultdict(lambda: {"tokens_raw": 0, "swaps": 0})
        for (asset, pool, quote), meta in pools.items():
            # 🔴 一天对最活跃的池太大:撞 10,000 上限或超时。递归对半,直到能取回。
            #    取不回才算失败 —— 而失败【绝不静默】,它按口径分列进 failures。
            r, e = _logs_recursive(pool, b0, b1, failures,
                                   {"day": ds, "asset": asset, "pool": pool,
                                    "quote": quote})
            if r is None:
                continue
            for l in r:
                amt = swap_stock_amount(l, meta["stock_is_token0"])
                blk = int(l["blockNumber"], 16)
                ratio, src, frm = index_for(idx.get(asset) or [], blk)
                k = (asset, quote)
                per[k]["tokens_raw"] += amt
                per[k]["swaps"] += 1
                per[k].setdefault("index_src", collections.Counter())[src] += 1
                if ratio is not None:
                    per[k]["shares"] = per[k].get("shares", 0.0) + (amt / 1e18) * ratio
                else:
                    per[k]["no_index_tokens"] = per[k].get("no_index_tokens", 0) + amt
        for (asset, quote), v in sorted(per.items()):
            rows.append({
                "day": ds, "asset": asset, "quote": quote,
                "block_from": b0, "block_to": b1,
                "swaps": v["swaps"],
                "tokens_raw": v["tokens_raw"] / 1e18,
                "shares_index_adjusted": v.get("shares"),
                "tokens_without_index": v.get("no_index_tokens", 0) / 1e18,
                "index_source": dict(v.get("index_src", {})),
            })
        log(f"  {ds}  blocks {b0:,}-{b1:,}  "
            f"{sum(x['swaps'] for x in per.values()):5} swaps  "
            f"{len(per)} (asset,quote) cells")

    os.makedirs(a.out, exist_ok=True)
    out = {
        "prereg": ["PREREG-tsv-volume-cap-2026-09-28.md"] +
                  [f"PREREG-tsv-volume-cap-2026-09-28-addendum{s}.md"
                   for s in ("", "-2", "-3", "-4", "-5")],
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"from": a.d0, "to": a.d1,
                   "block_from": span_a, "block_to": span_b},
        "pool_set": {
            "rule": "union of every archived enumeration, deduped on (asset,pool,quote)",
            "files": files, "count": len(pools),
            "by_quote": dict(collections.Counter(k[2] for k in pools)),
            "seen_in_n_enumerations": dict(
                collections.Counter(len(v) for v in seen_in.values())),
        },
        "not_a_bound": ("An estimate over the stated pool set. Pool-to-venue attribution is "
                        "not observable on chain, so this is neither an upper nor a lower "
                        "bound on the quantity section II.F caps. It cannot be used to say a "
                        "threshold was not exceeded."),
        "index_sampling": idxrec,
        "rows": rows,
        "failures": failures,
        "failures_by_reading": {
            "A_all_pools": len(failures),
            "B_usdg_only": sum(1 for f in failures if f.get("quote") == "USDG"),
        },
        "failure_note": ("A cell with failures is INCOMPLETE, not small. Read this before "
                         "reading any figure for the assets listed here."),
        "corrections_to_prereg": [
            {"file": "PREREG-tsv-volume-cap-2026-09-28-addendum-2.md",
             "claim": "the three payers rank in the order of their dividend yields",
             "status": "withdrawn",
             "why": ("measured 2026-09-15: NVDA 1.000775159 above AAPL 1.000566080 while "
                     "NVDA's yield is far lower, and QQQ and SPY were still exactly 1.0 that "
                     "day. The index is cumulative since inception, so its level is not a "
                     "function of current yield.")},
            {"file": "PREREG-tsv-volume-cap-2026-09-28-addendum-2.md",
             "claim": "zero spread across every event at a given moment",
             "status": "withdrawn",
             "why": ("an artifact of small samples. A full scan of one day of AAPL events "
                     "returns 111 distinct ratios, almost all rounding: n1 = round(n0 x "
                     "index) gives a relative error of about 1/n0. The run therefore reads "
                     "the index from the largest transfer in each sample window.")},
            {"file": "PREREG-tsv-volume-cap-2026-09-28.md",
             "claim": "every pool in the enumeration (41 rows) / USDG only (27 rows)",
             "status": "corrected in addendum 5",
             "why": "those counts describe MISSING-71909188.json, a different artifact."},
        ],
        "quantity": ("There is no index field and no getter. Every transfer emits a log "
                     "carrying two amounts; the quantity used here is their ratio, which "
                     "moves in steps. \"index\" below is shorthand for that ratio, not for "
                     "a value any contract exposes."),
        "survives_unchanged": ("every dividend payer has a ratio above 1 and every "
                               "non-payer is exactly 1.000000000; the ratio steps."),
    }
    p = os.path.join(a.out, f"tsv-volume-{a.d0}_{a.d1}.json")
    json.dump(out, open(p, "w"), indent=1)
    log(f"wrote {p}  ({len(rows)} rows, {len(failures)} failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
