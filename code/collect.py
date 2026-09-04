#!/usr/bin/env python3
"""Robinhood Chain 股票代币可执行深度采集。

🔴 **为什么独立于 dexfeed 而不是加一个 source**：
   ① dexfeed 的数据格式 2026-09-01 冻结，它的 SOURCES 模型假设的是
      「HTTP 聚合器 + 限流/配额」，而这里是无许可 RPC，语义对不上；
   ② 改 dexfeed 的 CHAINS/SOURCES 会牵动巡检、status.py、备份的断采检测，
      而那条 62 天的序列不能为一个新实验冒险。
   写进同一个数据根 ⇒ backup.sh 自动覆盖，无需改任何配置。

🔴 **每轮重新推汇率，不缓存。** 用 $100 买入的实际成交量反推「每美元多少
   代币」，再用它换算卖出方向的投入量。缓存汇率会在价格漂移后把卖出侧
   的规模算错，而那正是要测的东西。

⚠️ 采样窗口的教训（2026-09-03）：这条链 100ms 出块，「最近 400 万块」
   只有 4.6 天。任何按块数取窗口的分析，第一行先把它换算成时间。
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evm import keccak256, rpc                               # noqa: E402
from rhchain import QUOTES, STOCKS, STOCK_DEC, quote          # noqa: E402

ROOT = Path("/root/predict-data/dexfeed_data/uniswap_v4_rh")
POOLS = Path(__file__).parent / "stock_pools.json"   # 筛选后的池表，见 filter 流程
SIZES = [100, 1_000, 10_000, 100_000]
SOURCE = "uniswap_v4_rh"


def load_pools() -> dict:
    """按 (代币, 计价资产) 索引全链扫出来的池子。

    🔴 池表是**全链扫描**的产物，不能用「最近 N 块」重建 ——
    真正的股票代币池建在开链初期（块 84 万左右），而发射台每天
    造几千个垃圾池。窗口取窄了会只看到垃圾。
    """
    found = json.loads(POOLS.read_text())
    U = QUOTES["USDG"][0].lower()
    rev = {v.lower(): k for k, v in STOCKS.items()}
    idx: dict[str, list] = {}
    for p in found:
        pair = {p["c0"].lower(), p["c1"].lower()}
        if U not in pair:
            continue
        s = rev.get(p["c0"].lower()) or rev.get(p["c1"].lower())
        if s:
            idx.setdefault(s, []).append(p)
    return idx


def row(sym, side, size_usd, out, ts, ms, pool, status="ok", note="", blk=None,
        amt_in_raw=None, out_raw=None):
    """字段名对齐 dexfeed 的 quotes.jsonl，分析侧可以复用同一套代码。"""
    return {"source": SOURCE, "chain": "robinhood", "sell_sym": sym,
            "side": side, "size_usd": size_usd, "ts": ts,
            # 🔴 区块号是链上数据唯一可复现的锚点。墙钟时间无法让第三方
            #    在同一状态下复算 —— 而「可复算」是独立测量的全部可信度。
            "block": blk,
            "out_amount": out, "eff_price": None, "route": pool,
            # ok / no_liquidity（数据）/ rpc_error（故障，分析时必须剔除）
            "status": status,
            "detail": note, "latency_ms": ms, "tag": "",
            # 🔴 **原始整数是唯一可被第三方复现的量。**
            #    out_amount / eff_price 这些是我们除过小数位的浮点，
            #    不同语言的浮点序列化结果不同，不能进哈希原像。
            #    存成【十进制字符串】而不是数字：uint256 超过 JS 的 2^53，
            #    用数字类型会在别人解析时静默丢精度。
            "amount_in_raw": None if amt_in_raw is None else str(amt_in_raw),
            "amount_out_raw": None if out_raw is None else str(out_raw),
            # 🔴 产品要的那个数：卖出 $N 名义金额，实际收回名义金额的百分之几。
            #    直接存，不要留给分析侧再推 —— 推导规则会漂移，存下来的不会。
            "recovery_pct": None,
            # 买入方向相对 $100 档的价格冲击
            "impact_pct": None}


# ── 证据承诺：轮次哈希 ────────────────────────────────────────────
# 🔴 **原像里只能放「任何人在同一区块都能精确复现」的量。**
# 这是整个「证据承诺」功能成立与否的分界线：
#   ❌ ts / latency_ms  —— 墙钟时间与网络抖动，第三方永远算不出同一个值
#   ❌ out_amount / eff_price / *_pct —— 我们除过小数位的浮点，
#      不同语言的浮点序列化不一致，哈希必然对不上
#   ✅ block / poolId / 输入金额 / quoter 返回的原始整数 / status
#      —— 在同一区块高度重放 eth_call 就能逐字节复现
# 若把不可复现的字段放进原像，"任何人都能重算核对"这句话当场失效，
# 而且是【静默失效】：哈希照样生成、上链、看起来一切正常，
# 只是没有任何人能验证它 —— 那比不做这个功能更糟。
# 🔴 v2 起改用【同池往返】作为主指标（2026-09-04）。
# v1 的做法是：用「买入最优池」推出一个汇率，再用它换算卖出的投入量。
# 当买入最优池和卖出最优池不是同一个池时，那个汇率不属于任何一个池，
# 算出来的「名义金额」是虚的 —— 实测产出过 106.58% 的回收率，
# 即「买了立刻卖回能多拿 6.58%」，物理上不可能长期存在。
#
# 同池往返不需要任何汇率假设：投入 $N，在同一个池里买了再卖回，
# 实收多少就是多少。它自带合理性校验（必然 ≤100%，差额就是双边费用
# 加价格冲击），也更接近用户的真实体验：按下买入再按下卖出，亏多少。
CANON_VERSION = "rhdepth-v2"


def canon_lines(rows: list[dict]) -> list[str]:
    """规范化序列化。格式必须与文档一字不差，否则第三方复算不出。

    每行：block|sym|side|size_usd|poolId|amount_in_raw|mid_amount_raw|amount_out_raw|status
    整数一律十进制字符串（uint256 超 2^53，不能用数字类型传递），
    空值统一为空串，行按字典序排序后用 \n 连接。
    """
    out = []
    for r in rows:
        out.append("|".join([
            str(r.get("block") or ""),
            r.get("sell_sym") or "",
            r.get("side") or "",
            str(r.get("size_usd") or ""),
            r.get("route") or "",
            r.get("amount_in_raw") or "",
            r.get("mid_amount_raw") or "",
            r.get("amount_out_raw") or "",
            r.get("status") or "",
        ]))
    return sorted(out)


def round_keccak(rows: list[dict]) -> str:
    body = (CANON_VERSION + "\n" + "\n".join(canon_lines(rows))).encode()
    return "0x" + keccak256(body).hex()


def main() -> int:
    idx = load_pools()
    U, UD = QUOTES["USDG"]
    blk_r, err = rpc("eth_blockNumber", [])
    if err:
        print(f"取区块高度失败，本轮放弃: {err}", flush=True)
        return 1                      # 🔴 宁可丢一轮，不写无锚点的数据
    blk = int(blk_r, 16)
    # 🔴 **整轮钉在同一个区块高度上**（2026-09-03 由 verify.py 抓出）。
    #    这条链 100ms 出块，一轮 324 次调用要跑 60~85 秒 = 链推进约 700 块。
    #    若各次调用都打 "latest"，会同时坏掉两件事：
    #      ① 记录的 block 与报价实际状态对不上 ⇒ 第三方永远复核不了
    #      ② 64 行之间互相也对不上 ⇒ 违反 dexfeed 立过的「同时性是命脉」
    #    ⚠️ 代价：整轮在历史区块上取值，需要归档节点（Alchemy 有；
    #      公共端点只保留最近约 128 块的状态，降级后这条会失效）。
    bh = hex(blk)
    ts = int(time.time())
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    out_rows = []
    for sym, ps in sorted(idx.items()):
        for sz in SIZES:
            amt_in = sz * 10 ** UD
            best = None
            t0 = time.time()
            for p in ps:
                # 同一个池内闭环：USDG → 股票 → USDG
                o, st = quote(p, U, amt_in, bh)
                if not o:
                    continue
                back, st2 = quote(p, STOCKS[sym], o, bh)
                if back and (best is None or back > best[0]):
                    best = (back, o, p)
            ms = int((time.time() - t0) * 1000)
            if best is None:
                out_rows.append(row(sym, "roundtrip", sz, None, ts, ms, "",
                                    "no_liquidity", "", blk, amt_in, None))
                continue
            back, mid, p = best
            r = row(sym, "roundtrip", sz, back / 10 ** UD, ts, ms,
                    p["id"], "ok", "", blk, amt_in, back)
            r["mid_amount_raw"] = str(mid)          # 中间拿到的股票代币数量
            r["recovery_pct"] = back / 10 ** UD / sz * 100
            out_rows.append(r)

    d = ROOT / day
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / "quotes.jsonl.gz", "at", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 🔴 轮次哈希：链上证据承诺的原料。只承诺可复现的部分（见 canon_lines）。
    #    这里只算不提交 —— 私钥不上这台机器，提交由本地在回填窗口批量做。
    rk = round_keccak(out_rows)
    with open(d / "rounds.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"block": blk, "ts": ts,
                            "canon": CANON_VERSION,
                            "rows": len(out_rows),
                            "roundKeccak": rk,
                            "committed": False}, ensure_ascii=False) + "\n")
    from collections import Counter
    c = Counter(r["status"] for r in out_rows)
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))} | 块 {blk:,} | "
          f"{len(out_rows)} 行 | " + " ".join(f"{k}={v}" for k, v in sorted(c.items()))
          + f" | roundKeccak {rk[:18]}…")
    if c.get("rpc_error"):
        print(f"  ⚠️ {c['rpc_error']} 行是 RPC 故障，不是流动性枯竭 —— 分析时必须剔除",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
