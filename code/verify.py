#!/usr/bin/env python3
"""独立复核一个轮次的 roundKeccak。

这就是「证据承诺」卖的那件事本身：**任何人拿区块号 + 本文件，
就能在同一区块高度重放全部报价、重算哈希、和链上承诺逐字节比对。**
不需要信任提交者，只需要信任算术。

    python3 verify.py <block>        复核指定轮次
    python3 verify.py --latest       复核最近一轮

 需要归档节点（在历史区块上 eth_call）。公共端点通常不支持，
   配 RHCHAIN_RPC 指向 Alchemy 一类的归档端点。
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collect import CANON_VERSION, SIZES, canon_lines, load_pools, round_keccak
from collect import ROOT as COLLECT_ROOT
from rhchain import POOL_MANAGER, QUOTES, STOCKS, quote
from evm import rpc as _rpc


def data_root() -> Path:
    """数据目录。按优先级取三处之一。

     这里原先直接用 collect.ROOT —— 一个写死的采集机绝对路径。
       第三方 clone 本仓库后,那个目录在他机器上不存在,而
       Path.glob() 对不存在的目录不报错,只静默返回空。症状是
       「找不到区块 X 的轮次记录」,看起来像数据没发布,实际是
       复核脚本压根没在别人的机器上跑通过 —— 而「自己算一遍」
       正是这份报告卖的东西。
    """
    env = os.environ.get("RHDEPTH_DATA")
    if env:
        return Path(env)
    repo = Path(__file__).resolve().parent.parent / "data"   # 仓库自带的数据
    if any(repo.glob("*/rounds.jsonl")):
        return repo
    return COLLECT_ROOT                                       # 采集机上的实时目录


def preflight(block: int) -> str | None:
    """先确认这个 RPC 能读【历史状态】,不能就立刻停。返回错误说明,可用则 None。

     没有这一步,第三方拿公共端点跑会看到两行输出、然后「卡死」几分钟 ——
       324 次调用逐个撞同一个状态剪枝错误,一条解释都没有。
       报告卖的就是「你自己跑一遍」,**一个看起来挂死的脚本比一个报错的
       脚本伤害大得多** —— 前者让人以为数据是假的,后者只是让人去换端点。
    """
    r, err = _rpc("eth_getBalance", [POOL_MANAGER, hex(block)])
    if err:
        m = str(err.get("message") or err)
        return (f"RPC 无法读取区块 {block:,} 的历史状态:{m}\n"
                "  这个端点读不了历史状态(不是归档节点,或端点暂时不可用)。\n"
                "  用 RHCHAIN_RPC 指向一个 Robinhood Chain 归档端点后重试。")
    if r is None:
        return f"RPC 对区块 {block:,} 返回空,无法复核。请改用归档端点。"
    return None


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
    #  跨天查找。轮次按 UTC 日期分目录，但被复核的区块可能在任何一天 ——
    #    只翻今天的目录，历史轮次就永远「找不到」，而第三方复核的
    #    恰恰多是历史轮次。
    root = data_root()
    recs, superseded = [], {}
    for rf in sorted(root.glob("*/rounds.jsonl")):
        for line in rf.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            #  按记录自带的 canon 字段过滤,不按目录名。
            #    目录名是同一个事实的第二份抄写,迟早会漂移:隔离目录
            #    先叫 .pre-*,后来又有 .rhdepth-v1-defective,任何写死
            #    后缀的判断都会漏掉下一种,把已作废的轮次放进复核集。
            if r.get("canon") != CANON_VERSION:
                superseded[str(r["block"])] = (r.get("canon"), rf.parent.name)
                continue
            recs.append(r)
    recs.sort(key=lambda r: r["block"])
    rec = recs[-1] if arg == "--latest" else next(
        (r for r in recs if str(r["block"]) == arg), None)
    if not rec:
        if arg in superseded:
            canon, where = superseded[arg]
            print(f"区块 {arg} 属于已作废的规范 {canon}(在 {where}/)。")
            print(f"该轮不参与复核:本地规范是 {CANON_VERSION},原像不同,哈希必然对不上。")
            print("隔离数据保留可访问只是为了让更正可查,不是可复核的结论。")
            return 2
        print(f"找不到区块 {arg} 的轮次记录(数据目录 {root})")
        if not any(root.glob("*/rounds.jsonl")):
            print("该目录下没有任何 rounds.jsonl —— 若是从仓库 clone 而来,")
            print("请在仓库根目录运行,或用 RHDEPTH_DATA 指向数据目录。")
        return 1

    print(f"复核轮次  块 {rec['block']:,}  规范 {rec['canon']}")
    print(f"  链上承诺 {rec['roundKeccak']}")
    if rec["canon"] != CANON_VERSION:
        print(f"   规范版本不符（本地 {CANON_VERSION}），哈希必然不同")

    bad = preflight(rec["block"])
    if bad:
        print(f"\n   {bad}")
        return 3

    rows = rebuild(rec["block"])
    got = round_keccak(rows)
    print(f"  独立重算 {got}")
    ok = got == rec["roundKeccak"]
    print(f"\n  {' 一致 —— 该轮数据可被独立复现' if ok else ' 不一致'}")
    if not ok:
        orig = []
        for qf in sorted(root.glob("*/quotes.jsonl.gz")):
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
