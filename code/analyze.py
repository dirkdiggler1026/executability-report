#!/usr/bin/env python3
"""Summarise round-trip measurements for publication.

Two rules that shape the output:

  * Percentile range, not min-max. A single round where a market maker
    briefly pulled depth would make raw min-max misrepresent the normal
    state. p10-p90 resists that and still exposes bimodality: if a token
    really sits at either 30% or 98% and nothing between, the quantiles
    show the gap.

  * A round where the size could not be filled is NOT zero. It is a
    different kind of observation and is counted separately. Averaging it
    in as 0% would hide the thing worth reporting: "3 of 12 rounds could
    not fill $10,000 at all".

US market sessions are derived from the wall-clock timestamp, which is
deliberately not part of the hash preimage — it exists here for analysis
only, and applies retroactively to rounds collected before this script.

    python3 analyze.py [--min-rounds 12]

--- 中文 ---
🔴 用分位而非裸 min~max：一次瞬时抽走深度会让极值夸大常态。
🔴 缺测（吃不下）不计为 0%，单列计数 —— 「12 轮里有 3 轮连一万都吃不下」
   这个信息不能被平均数吃掉。
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path("/root/predict-data/dexfeed_data/uniswap_v4_rh")
SIZES = [100, 1_000, 10_000, 100_000]
ORDER = ["NVDA", "TSLA", "AAPL", "SPY", "GOOGL", "RDDT", "AMC", "GME", "QQQ"]


def session(ts: int) -> str:
    """美股时段（9 月为 EDT = UTC-4）。"""
    h = time.gmtime(ts).tm_hour + time.gmtime(ts).tm_min / 60
    wd = time.gmtime(ts).tm_wday
    if wd >= 5:
        return "weekend"
    if 13.5 <= h < 20:
        return "regular"
    if 8 <= h < 13.5:
        return "pre"
    if 20 <= h < 24:
        return "after"
    return "overnight"


def pct(v: list[float], q: float) -> float:
    v = sorted(v)
    if len(v) == 1:
        return v[0]
    i = q * (len(v) - 1)
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rounds", type=int, default=12)
    a = ap.parse_args()

    rows = []
    for f in sorted(glob.glob(str(ROOT / "*" / "quotes.jsonl.gz"))):
        if ".pre-" in f or ".rhdepth-v1-" in f:
            continue
        rows += [json.loads(l) for l in gzip.open(f, "rt") if l.strip()]
    rows = [r for r in rows if r.get("side") == "roundtrip"]
    if not rows:
        print("无 v2 数据")
        return 1

    blocks = sorted({r["block"] for r in rows})
    n = len(blocks)
    span_h = (blocks[-1] - blocks[0]) * 0.1 / 3600
    sess = defaultdict(int)
    for b in blocks:
        ts = next(r["ts"] for r in rows if r["block"] == b)
        sess[session(ts)] += 1
    print(f"轮次 {n}  区块 {blocks[0]:,} → {blocks[-1]:,}  跨度 {span_h:.1f} 小时")
    print(f"时段分布: " + "  ".join(f"{k} {v}" for k, v in sorted(sess.items())))
    if n < a.min_rounds:
        print(f"⚠️ 未达 {a.min_rounds} 轮门槛，以下仅供观察，不可发布\n")
    else:
        print()

    ok = defaultdict(lambda: defaultdict(list))
    miss = defaultdict(lambda: defaultdict(int))
    for r in rows:
        k, s = r["sell_sym"], r["size_usd"]
        if r.get("status") == "ok" and r.get("recovery_pct") is not None:
            ok[k][s].append(r["recovery_pct"])
        else:
            miss[k][s] += 1

    print(f"{'代币':7s}{'档位':>10s}{'中位':>9s}{'p10–p90':>18s}{'样本':>7s}{'吃不下':>8s}")
    print("-" * 62)
    for sym in ORDER:
        for sz in SIZES:
            v, m = ok[sym][sz], miss[sym][sz]
            lbl = f"{'$'+format(sz,','):>10s}"
            if not v:
                print(f"{sym if sz==SIZES[0] else '':7s}{lbl}{'—':>9s}"
                      f"{'全部吃不下':>18s}{0:>7d}{m:>8d}")
                continue
            rng = f"{pct(v,.1):.1f}%~{pct(v,.9):.1f}%"
            print(f"{sym if sz==SIZES[0] else '':7s}{lbl}{st.median(v):>8.2f}%"
                  f"{rng:>18s}{len(v):>7d}{m:>8d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
