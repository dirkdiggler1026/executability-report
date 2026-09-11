"""Robinhood Chain (4663) 股票代币可执行深度读取。

**为什么走 V4 而不是 V3**（2026-09-03 实测）：
   官方部署页列了 v3 factory，`getPool` 也返回非零地址 —— 但那个池
   **从未 initialize**（sqrtPriceX96 = 0）。真实流动性全在 Uniswap V4
   的 PoolManager 单例里。**「已部署」不等于「有流动性」。**

**地址必须用官方部署表，不能用区块浏览器搜索排序。**
   Blockscout 上「已验证、排序第一」的 StateView 指向一个
   余额为 0、Initialize 事件为 0 的空 PoolManager。
"""
from __future__ import annotations

import json
from pathlib import Path

from evm import call, enc_addr, enc_uint, keccak256, rpc, selector

# 官方部署表 developers.uniswap.org/docs/protocols/v4/deployments
POOL_MANAGER = "0x8366a39cc670b4001a1121b8f6a443a643e40951"
STATE_VIEW = "0xf3334192d15450cdd385c8b70e03f9a6bd9e673b"
V4_QUOTER = "0x8dc178efb8111bb0973dd9d722ebeff267c98f94"

NATIVE = "0x" + "0" * 40
QUOTES = {                       # 计价资产 → 小数位
    "USDG": ("0x5fc5360d0400a0fd4f2af552add042d716f1d168", 6),
    "WETH": ("0x0bd7d308f8e1639fab988df18a8011f41eacad73", 18),
    "ETH":  (NATIVE, 18),
}
STOCKS = {
    "NVDA": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
    "TSLA": "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
    "SPY":  "0x117cc2133c37b721f49de2a7a74833232b3b4c0c",
    "QQQ":  "0xd5f3879160bc7c32ebb4dc785f8a4f505888de68",
    "AAPL": "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
    "GOOGL": "0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3",
    "GME":  "0x1b0e319c6a659f002271b69db8a7df2f911c153e",
    "AMC":  "0x05a3d1cd21d0c88145e82600e62e7e496e0f222b",
    "RDDT": "0x05b37fb53a299a1b874a619e1c4c404d52c36f4c",
}
STOCK_DEC = 18

_INIT_TOPIC = "0x" + keccak256(
    b"Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)").hex()
_QSEL = selector(
    "quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))")


def pool_id(c0: str, c1: str, fee: int, ts: int, hooks: str) -> str:
    """poolId = keccak256(abi.encode(PoolKey))。已对着 Initialize 事件验过一致。"""
    enc = bytes.fromhex(enc_addr(c0) + enc_addr(c1) + enc_uint(fee)
                        + enc_uint(ts) + enc_addr(hooks))
    return "0x" + keccak256(enc).hex()


def scan_pools(blocks_back: int = 4_000_000, step: int = 500_000) -> list[dict]:
    """枚举已初始化的池。只保留 sqrtPriceX96 != 0 的 —— 未初始化的池
    存在但不可交易，把它们算进流动性正是 DexScreener 的错法。

    公共 RPC 的 getLogs 有 10,000 条结果上限；区间取大了会报错而不是
    截断，取小了会撞 429。失败的区间必须报出来，不能静默跳过。"""
    head_r, err = rpc("eth_blockNumber", [])
    if err:
        raise RuntimeError(f"取区块高度失败: {err}")
    head = int(head_r, 16)
    out, lo = [], max(0, head - blocks_back)
    while lo < head:
        hi = min(head, lo + step)
        lg, err = rpc("eth_getLogs", [{"address": POOL_MANAGER, "topics": [_INIT_TOPIC],
                                       "fromBlock": hex(lo), "toBlock": hex(hi)}],
                      timeout=45)
        if err:
            raise RuntimeError(f"区间 {lo}-{hi} 扫描失败: {err} "
                               f"—— 半截池表比没有池表更糟")
        if isinstance(lg, list):
            for e in lg:
                d = e["data"][2:]
                if int(d[192:256], 16) == 0:
                    continue                      # 未初始化
                out.append({"id": e["topics"][1],
                            "c0": "0x" + e["topics"][2][-40:],
                            "c1": "0x" + e["topics"][3][-40:],
                            "fee": int(d[0:64], 16), "ts": int(d[64:128], 16),
                            "hooks": "0x" + d[128:192][-40:]})
        lo = hi + 1
    return out


# NotEnoughLiquidity(bytes32) 的错误选择子 —— 池子明确说「吃不下」
_NOT_ENOUGH = "7a5ed734"


def quote(p: dict, token_in: str, amount_in: int, block: str = "latest"):
    """吃掉 amount_in 能拿到多少。返回 (数量或 None, 状态)。

    **三种结果必须分开**（2026-09-03 差点混在一起写进历史）：
       ok            拿到报价
       no_liquidity  合约回滚 NotEnoughLiquidity —— 这是【数据】，
                     和 pmfeed 的 no_liquidity、dexfeed 的「拒绝报价」同源
       rpc_error     429 / 超时 / 结果集超限 —— 这是【故障】，
                     绝不能记成「吃不下」，否则时间序列里会出现
                     由我们自己的限流造成的假流动性枯竭"""
    zfo = token_in.lower() == p["c0"].lower()
    data = (_QSEL + enc_uint(0x20)
            + enc_addr(p["c0"]) + enc_addr(p["c1"]) + enc_uint(p["fee"])
            + enc_uint(p["ts"]) + enc_addr(p["hooks"])
            + enc_uint(1 if zfo else 0) + enc_uint(amount_in)
            + enc_uint(0x100) + enc_uint(0))
    # block 参数是「可复核」的前提：第三方必须能在【当时那个区块】
    #    重放同一次调用。写死 latest 的话，谁都验证不了历史轮次。
    r, err = rpc("eth_call", [{"to": V4_QUOTER, "data": "0x" + data,
                               "gas": "0x2000000"}, block])
    if isinstance(r, str) and r.startswith("0x") and len(r) > 66:
        return int(r[2:66], 16), "ok"
    if err and err.get("code") == 3:
        d = str(err.get("data") or "")
        return None, "no_liquidity" if _NOT_ENOUGH in d else "revert_other"
    return None, "rpc_error"


def best_quote(pools: list[dict], token_in: str, amount_in: int,
               block: str = "latest"):
    """多个池子里取最好的 —— 和 dexfeed 对多聚合器取最优是同一个原则。

    返回 (最优数量或 None, 池, 状态)。只要有【任何一个池】是 rpc_error，
    整条结果就标记成 rpc_error —— 因为那个没问成的池可能恰好是最好的，
    把它当成「不存在」会低估深度。宁可丢一个采样点，不可写一个假的。"""
    best, bp, saw_err = None, None, False
    for p in pools:
        o, st = quote(p, token_in, amount_in, block)
        if st == "rpc_error":
            saw_err = True
        elif o and (best is None or o > best):
            best, bp = o, p
    if best is None:
        return None, None, ("rpc_error" if saw_err else "no_liquidity")
    return best, bp, ("ok_partial" if saw_err else "ok")
