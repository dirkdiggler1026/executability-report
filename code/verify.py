#!/usr/bin/env python3
"""独立复核一个轮次的 roundKeccak。

这就是「证据承诺」卖的那件事本身：**任何人拿区块号 + 本文件，
就能在同一区块高度重放全部报价、重算哈希、和记录的轮次哈希逐字节比对。**
不需要信任提交者，只需要信任算术。

**本脚本的锚点是 git 历史，不是链。** `rounds.jsonl` 与数据在同一个仓库里，
所以重算比对证明的是「未被事后改动，且任何改动都留在 git 历史里」——
这是真的保证，但它不是链上承诺。早先这里写的是「和链上承诺逐字节比对」，
而已发布轮次的 `committed` 全部是 false —— 一个事实写在两处然后漂移，
这份仓库自己犯过一次。
 ⚠️ **链上锚点自 2026-09-19 起是存在的**(EvidenceLedger @ 46630)——
   「不是链」说的是**本脚本不去查它**，不是「没有链上锚点」。
   上一句警告的正是「一个事实写在两处然后漂移」；回填落地那天，
   它自己成了漂掉的那一份。

**`committed` 永远不会翻成 true，不要指望本脚本自己跟进。**
`rounds.jsonl` 在 MANIFEST.sha256 里，改动它会让已发布校验和失效；
它同时逐日进 git，所以任何事后改动也留在 git 历史里。
A8「已发布文件只增不改、链上状态不回写进数据文件」正是这个意思。
 **有两份同名的 MANIFEST.sha256，覆盖范围不同，别把一份的结论套到另一份上。**
   已发布那份由发布脚本在发布时生成，覆盖 quotes.jsonl.gz 与 rounds.jsonl 两个文件。
   采集机上还有一份由备份脚本生成，只覆盖 `*.jsonl.gz` —— 它服务异地备份的完整性，
   不是已发布校验和。2026-09-16 有人读了后者，据此断言前者「不含 rounds.jsonl」，
   把一句真话「更正」成了假话，并推进了公开仓库。
   **断言「X 是假的」之前，先读一遍 X 本身。**
🔴 **2026-09-19：上面预言的那一天到了,而这里做的【不是】它说的那个改法。**
   回填已落地(测试网 46630,610 轮,水印 64,907,249),于是原先那行
   `anchor: git history (not committed on chain yet)` 变成了假话。
   但更早的问题是:那个括号**断言了本工具从未查过的事** ——
   它不是那天才变假的,它从第一天起就没有依据,只是碰巧为真。
   而且那行的三元表达式有一条分支**永远走不到**(`committed` 按 A8 恒为 false),
   看起来在处理两种情况,其实只有一种。
   **这次只做一件事:把断言收回到查过的范围内**,并删掉走不到的那条分支。
**D4 那个改法(把锚点来源换成账本本身:查 getRoundHash / latestCommittedBlock,
或本地 append-only 的 commits.jsonl)仍然欠着,不要因为这一行不再说假话就以为它做了。**

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
        return (f"this RPC cannot read historical state at block {block:,}: {m}\n"
                "  The endpoint does not keep state history (it is not an archive\n"
                "  endpoint, or it is temporarily unavailable).\n"
                "  Point RHCHAIN_RPC at a Robinhood Chain archive endpoint and retry.")
    if r is None:
        return (f"the RPC returned nothing for block {block:,}; this round cannot be checked.\n"
                "  Use an archive endpoint.")
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
            print(f"Block {arg} belongs to the superseded canon {canon} (in {where}/).")
            print(f"That round is not checked: the local canon is {CANON_VERSION}, so the")
            print("preimage differs and the hash cannot match. The quarantined data stays")
            print("readable so the correction can be inspected, not as a checkable result.")
            return 2
        print(f"No round record for block {arg} (data root {root})")
        if not any(root.glob("*/rounds.jsonl")):
            print("There is no rounds.jsonl under that root. If you cloned the repository,")
            print("run this from the repository root, or set RHDEPTH_DATA to the data directory.")
        return 1

    print(f"round      block {rec['block']:,}  canon {rec['canon']}")
    print(f"  recorded round hash {rec['roundKeccak']}")
    # `rec["committed"]` 按 A8 恒为 false(链上状态不回写进数据文件),
    # 所以【不能】拿它判断上链与否。只说查过的:哈希在 git 历史里。
    # 链上状态要问账本本身 —— 本工具不查,所以本工具不说。
    print("  anchor: git history (this tool does not query the ledger)")
    if rec["canon"] != CANON_VERSION:
        print(f"   canon mismatch (local {CANON_VERSION}); the hash cannot match")

    bad = preflight(rec["block"])
    if bad:
        print(f"\n   {bad}")
        return 3

    rows = rebuild(rec["block"])
    got = round_keccak(rows)
    print(f"  recomputed          {got}")
    ok = got == rec["roundKeccak"]
    print(f"\n  {'MATCH -- this round is independently reproducible' if ok else 'MISMATCH'}")
    if not ok:
        orig = []
        for qf in sorted(root.glob("*/quotes.jsonl.gz")):
            orig += [json.loads(l) for l in gzip.open(qf, "rt") if l.strip()]
        orig = [r for r in orig if r.get("block") == rec["block"]]
        a, b = set(canon_lines(orig)), set(canon_lines(rows))
        print(f"  only in published: {len(a-b)} lines; only in recomputed: {len(b-a)} lines")
        for x in list(a - b)[:3]:
            print(f"    published:  {x}")
        for x in list(b - a)[:3]:
            print(f"    recomputed: {x}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
