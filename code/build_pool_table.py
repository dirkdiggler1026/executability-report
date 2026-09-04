#!/usr/bin/env python3
"""Build the pool table used by the collector — reproducibly.

Which pools we measure IS part of the conclusion, so this selection has
to be reproducible by anyone. Two stages:

  1. Full-chain scan of Uniswap V4 Initialize events, keeping only pools
     that pair a stock token with USDG and were actually initialised.
     Any failed block range aborts the run: a partial pool table is worse
     than none, because it silently produces "this token can't be sold"
     for tokens whose real pools were never scanned. That exact failure
     invalidated a published conclusion on 2026-09-04.

  2. Probe every candidate with a $10,000 buy. Pools that cannot fill it
     are dropped. Of the survivors, keep the N that return the most.

Selection is by realised output at $10k, not by fee tier, pool count or
TVL — pool count in particular is actively misleading here: AMC has the
most pools (208) and among the fewest usable ones (10).

    python3 build_pool_table.py [--top N] [--probe USD] > stock_pools.json

--- 中文说明 ---
🔴 「选了哪些池」是结论的一部分，必须可复现。
   分两步：全链扫描（失败即中止）→ 用 $10,000 试探筛掉吃不下的。
   排序依据是【实际能换出多少】，不是费率/池子数/TVL ——
   池子数尤其误导：AMC 池最多（208）而可用的最少（10）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evm import rpc                                       # noqa: E402
from rhchain import (POOL_MANAGER, QUOTES, STOCKS,        # noqa: E402
                     _INIT_TOPIC, quote)


def scan(step: int = 2_000_000) -> list[dict]:
    """全链扫 Initialize。失败区间 → 抛异常，绝不返回半截池表。"""
    head_r, err = rpc("eth_blockNumber", [])
    if err:
        raise RuntimeError(f"取区块高度失败: {err}")
    head = int(head_r, 16)
    stockset = {a.lower() for a in STOCKS.values()}
    out, lo, win = [], 0, step
    while lo < head:
        hi = min(head, lo + win)
        lg, err = rpc("eth_getLogs", [{"address": POOL_MANAGER,
                                       "topics": [_INIT_TOPIC],
                                       "fromBlock": hex(lo),
                                       "toBlock": hex(hi)}], timeout=90)
        if err:
            if win > 20_000:
                win //= 2
                continue
            raise RuntimeError(f"区间 {lo}-{hi} 扫描失败: {err}")
        for ev in lg:
            c0 = "0x" + ev["topics"][2][-40:]
            c1 = "0x" + ev["topics"][3][-40:]
            if c0.lower() not in stockset and c1.lower() not in stockset:
                continue
            d = ev["data"][2:]
            if int(d[192:256], 16) == 0:      # 未初始化
                continue
            out.append({"id": ev["topics"][1], "c0": c0, "c1": c1,
                        "blk": int(ev["blockNumber"], 16),
                        "fee": int(d[0:64], 16), "ts": int(d[64:128], 16),
                        "hooks": "0x" + d[128:192][-40:]})
        lo = hi + 1
        if len(lg) < 3000:
            win = min(win * 2, 4_000_000)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8, help="每个代币保留几个池")
    ap.add_argument("--probe", type=int, default=10_000, help="试探金额（美元）")
    a = ap.parse_args()

    U, UD = QUOTES["USDG"]
    rev = {v.lower(): k for k, v in STOCKS.items()}
    pools = scan()
    idx: dict[str, list] = {}
    for p in pools:
        if U.lower() in {p["c0"].lower(), p["c1"].lower()}:
            s = rev.get(p["c0"].lower()) or rev.get(p["c1"].lower())
            if s:
                idx.setdefault(s, []).append(p)

    blk_r, err = rpc("eth_blockNumber", [])
    if err:
        raise RuntimeError(f"取区块高度失败: {err}")
    bh = hex(int(blk_r, 16))
    keep, report = [], []
    for sym, ps in sorted(idx.items()):
        scored = []
        for p in ps:
            o, st = quote(p, U, a.probe * 10 ** UD, bh)
            if o:
                scored.append((o, p))
        scored.sort(key=lambda x: -x[0])
        sel = [p for _, p in scored[:a.top]]
        keep += sel
        report.append((sym, len(ps), len(scored), len(sel)))

    for sym, total, usable, kept in report:
        print(f"  {sym:6s} {total:>4} pools → {usable:>3} can fill "
              f"${a.probe:,} → keeping {kept}", file=sys.stderr)
    print(f"\n  block {int(blk_r,16):,} · {len(keep)} pools selected",
          file=sys.stderr)
    json.dump(keep, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
