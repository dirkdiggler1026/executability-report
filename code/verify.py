#!/usr/bin/env python3
"""独立复核一个轮次的 roundKeccak。

这就是「证据承诺」卖的那件事本身：**任何人拿区块号 + 本文件，
就能在同一区块高度重放全部报价、重算哈希、和链上承诺逐字节比对。**
不需要信任提交者，只需要信任算术。

    python3 verify.py <block>        复核指定轮次
    python3 verify.py --latest       复核最近一轮

🔴 需要归档节点（在历史区块上 eth_call）。公共端点通常不支持，
   配 RHCHAIN_RPC 指向 Alchemy 一类的归档端点。
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collect import CANON_VERSION, ROOT, SIZES, canon_lines, load_pools, round_keccak
from rhchain import QUOTES, STOCKS, quote


def rebuild(block: int) -> list[dict]:
    """在指定区块高度重新执行同池往返，重建该轮的可复现字段。

    v2 的每条记录是一次【闭环】：在同一个池里用 USDG 买入，再把买到的
    全部卖回。所以重放必须复现两条腿，中间量 mid_amount_raw 也进原像 ——
    没有它，第三方只能验证「投入和产出」，无法验证中间那一步走的是
    哪个池、拿到了多少代币。
    """
    idx = load_pools()
    U, UD = QUOTES["USDG"]
    bh = hex(block)
    rows = []
    for sym, ps in sorted(idx.items()):
        for sz in SIZES:
            amt_in = sz * 10 ** UD
            best = None
            for p in ps:
                o, st = quote(p, U, amt_in, bh)
                if not o:
                    continue
                back, st2 = quote(p, STOCKS[sym], o, bh)
                if back and (best is None or back > best[0]):
                    best = (back, o, p)
            if best is None:
                rows.append({"block": block, "sell_sym": sym, "side": "roundtrip",
                             "size_usd": sz, "route": "",
                             "amount_in_raw": str(amt_in), "mid_amount_raw": None,
                             "amount_out_raw": None, "status": "no_liquidity"})
                continue
            back, mid, p = best
            rows.append({"block": block, "sell_sym": sym, "side": "roundtrip",
                         "size_usd": sz, "route": p["id"],
                         "amount_in_raw": str(amt_in), "mid_amount_raw": str(mid),
                         "amount_out_raw": str(back), "status": "ok"})
    return rows


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "--latest"
    # 🔴 跨天查找。轮次按 UTC 日期分目录，但被复核的区块可能在任何一天 ——
    #    只翻今天的目录，历史轮次就永远「找不到」，而第三方复核的
    #    恰恰多是历史轮次。
    recs = []
    for rf in sorted(ROOT.glob("*/rounds.jsonl")):
        if ".pre-" in str(rf):          # 隔离的误报存档不参与复核
            continue
        recs += [json.loads(l) for l in rf.read_text().splitlines() if l.strip()]
    recs.sort(key=lambda r: r["block"])
    rec = recs[-1] if arg == "--latest" else next(
        (r for r in recs if str(r["block"]) == arg), None)
    if not rec:
        print(f"找不到区块 {arg} 的轮次记录")
        return 1

    print(f"复核轮次  块 {rec['block']:,}  规范 {rec['canon']}")
    print(f"  链上承诺 {rec['roundKeccak']}")
    if rec["canon"] != CANON_VERSION:
        print(f"  ⚠️ 规范版本不符（本地 {CANON_VERSION}），哈希必然不同")

    rows = rebuild(rec["block"])
    got = round_keccak(rows)
    print(f"  独立重算 {got}")
    ok = got == rec["roundKeccak"]
    print(f"\n  {'✅ 一致 —— 该轮数据可被独立复现' if ok else '❌ 不一致'}")
    if not ok:
        orig = []
        for qf in sorted(ROOT.glob("*/quotes.jsonl.gz")):
            if ".pre-" in str(qf):
                continue
            orig += [json.loads(l) for l in gzip.open(qf, "rt") if l.strip()]
        orig = [r for r in orig if r.get("block") == rec["block"]]
        a, b = set(canon_lines(orig)), set(canon_lines(rows))
        print(f"  原始独有 {len(a-b)} 行，重算独有 {len(b-a)} 行")
        for x in list(a - b)[:3]:
            print(f"    原始: {x}")
        for x in list(b - a)[:3]:
            print(f"    重算: {x}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
