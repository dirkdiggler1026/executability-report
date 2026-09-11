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

# 🔴 **口径断点 2026-09-11：status 的语义变了**（至今没有一行不同，但语义变了）。
# 此前：任何一次 quote 失败都走同一个 `continue` —— rpc_error / revert_other /
#   no_liquidity 三者合流；全部池失败时整行硬编码成 no_liquidity。
#   这正是 rhchain.best_quote() 的 docstring 警告过的那件事：
#   **故障被记成「吃不下」，序列里出现由我们自己的限流造成的假枯竭。**
#   更危险的是另一半 —— 最优池 rpc_error、次优池成功时，会写下一个
#   **看起来完全正常、只是偏低**的数字，标着 ok，没有任何标记。
#   那个形状和 QQQ 0.03%、GME 94.9→7.4 不可区分。
# 现在：故障 → 同一 pinned block 有界重试 → 仍失败则**丢掉整轮**。
#
# 🔴 为什么是「丢整轮」而不是「把这行标成 rpc_error」：
#   status 在 canon 原像里（见 canon_lines）。写一行 rpc_error 进 series，
#   第三方在同一区块回放时 RPC 是好的 ⇒ 他算出 ok ⇒ **哈希永久对不上**，
#   而且无从得知原因。可复算是这个项目的全部可信度，宁可留一个诚实的空档。
#   这与本文件既有的「取区块高度失败，本轮放弃」是同一条原则。
# ⚠️ 也不能只丢那一行：rounds.jsonl 记 rows 数、轮次哈希覆盖全部行，
#   35 行的轮次不是残缺的 36 行轮次，是另一种东西。
#
# 归档节点上按 pinned block 重放是幂等的 ⇒ 重试不改变语义，只是重问一次。
QUOTE_RETRIES = 2                 # 首次 + 2 次重试
RETRY_SLEEP_S = 1.5               # 线性退避；evm._throttle 已在管发送速率


def quote_retry(p, token_in, amount_in, block):
    """同一 pinned block 上的有界重试。返回 (数量或 None, 状态, 尝试次数)。

    只对 rpc_error 重试 —— no_liquidity 和 revert_other 是【链上事实】，
    在同一区块重问一百次也是同一个答案，重试它们纯属浪费配额。
    """
    for i in range(QUOTE_RETRIES + 1):
        o, st = quote(p, token_in, amount_in, block)
        if st != "rpc_error":
            return o, st, i + 1
        if i < QUOTE_RETRIES:
            time.sleep(RETRY_SLEEP_S * (i + 1))
    return None, "rpc_error", QUOTE_RETRIES + 1


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
    failures = []           # rpc_error：故障，会导致丢轮
    reverts = []            # revert_other：池表/ABI 可能错了，单独报警
    # 🔴 **第一次重试耗尽即中止整轮，不要把剩下的问完。**
    #    任何一次耗尽都已经决定了这一轮要丢，继续问是纯浪费 —— 而且是危险的
    #    浪费：实测全故障场景下 288 次失败 × 退避 (1.5+3.0)s ≈ 21 分钟，
    #    会吃掉 30 分钟的轮次间隔并和下一轮叠起来（dexfeed 8-31 的占空比事故
    #    就是这么来的）。故障要**快速失败**，而不是慢慢耗死采集节奏。
    for sym, ps in sorted(idx.items()):
        if failures:
            break
        for sz in SIZES:
            if failures:
                break
            amt_in = sz * 10 ** UD
            best = None
            cell_revert = 0          # 本格出现过几次 revert_other
            t0 = time.time()
            for p in ps:
                # 同一个池内闭环：USDG → 股票 → USDG
                # 🔴 两条腿都要接住 status。旧版只接第一条、且两条都丢弃，
                #    于是「问不到」和「吃不下」在这个 continue 上合流。
                o, st, n1 = quote_retry(p, U, amt_in, bh)
                if st == "rpc_error":
                    failures.append({"sym": sym, "size_usd": sz, "leg": "buy",
                                     "pool_id": p["id"], "tries": n1})
                    break                        # 这一轮已注定要丢，快速失败
                if st == "revert_other":
                    reverts.append({"sym": sym, "size_usd": sz, "leg": "buy",
                                    "pool_id": p["id"]})
                    cell_revert += 1
                    continue
                if not o:
                    continue                     # no_liquidity —— 这是数据
                back, st2, n2 = quote_retry(p, STOCKS[sym], o, bh)
                if st2 == "rpc_error":
                    failures.append({"sym": sym, "size_usd": sz, "leg": "sell",
                                     "pool_id": p["id"], "tries": n2})
                    break                        # 同上，快速失败
                if st2 == "revert_other":
                    reverts.append({"sym": sym, "size_usd": sz, "leg": "sell",
                                    "pool_id": p["id"]})
                    cell_revert += 1
                    continue
                if back and (best is None or back > best[0]):
                    best = (back, o, p)
            ms = int((time.time() - t0) * 1000)
            if best is None:
                # 🔴 本格一个池都没成，而且期间出现过 revert_other ⇒ **不能写
                #    no_liquidity**。链没有说「吃不下」，它说的是别的；写成
                #    no_liquidity 就是在数据里放一句链没说过的话 —— 和这次
                #    要修的 rpc_error 合流是同一类错误，只是换了个来源。
                #    revert_other 意味着池表或 ABI 可能已失效，按缺陷处理：
                #    报警 + 丢轮，不当测量落盘。
                if cell_revert:
                    failures.append({"sym": sym, "size_usd": sz, "leg": "-",
                                     "pool_id": "", "tries": 0,
                                     "why": "revert_other 覆盖全部池，拒绝写成 no_liquidity"})
                    break
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

    # 🔴 **有任何一次重试耗尽的 rpc_error ⇒ 整轮不落盘。**
    #    不能只丢那一格：没问成的池可能恰好是最好的，剩下的池会给出一个
    #    偏低但看起来正常的数字（旧版 ok_partial 那一半）。也不能标记它：
    #    status 进 canon 原像，第三方回放算不出同一个值。
    #    ⚠️ 空档必须能和「采集器挂了」区分开，否则到齐率纪律失去意义 ——
    #      所以丢轮要留下可自证的记录，而不是静默 return。
    if failures:
        rec = {"ts": ts, "block": blk, "event": "round_dropped",
               "cells_failed": len(failures), "rows_would_be": len(out_rows),
               "detail": failures[:20]}
        with open(d / "failures.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))} | 块 {blk:,} | "
              f"🔴 丢轮：{len(failures)} 次 RPC 故障重试耗尽，本轮不落盘 "
              f"（宁可留空档，不写可能偏低的数字）", flush=True)
        return 2

    if reverts:
        # 14,384 行里一次都没出现过 ⇒ 任何一次出现都是信号，不设阈值。
        print(f"  🔴 {len(reverts)} 次 revert_other（非 NotEnoughLiquidity 回滚）"
              f"—— 池表或 ABI 可能已失效：{reverts[:5]}", flush=True)

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
    # 🔴 这里不再有 rpc_error 分支：故障轮次在上面就整轮丢掉了，永远走不到这。
    #    旧版这里有一个 `if c.get("rpc_error")` 的告警，而 row() 在本文件从未
    #    以 rpc_error 调用过 ⇒ 那个分支**永不触发**，等于故障发生时零信号。
    return 0


if __name__ == "__main__":
    sys.exit(main())
