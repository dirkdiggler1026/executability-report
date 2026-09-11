"""最小 EVM 读侧工具 —— 零依赖。

**不装 web3。** 这台机器只剩约 400MB 可用内存，而采集进程还在长。
读侧只需要三样：keccak256、静态类型的 ABI 编码、eth_call。
全部手写不到 150 行，比拖进一整套依赖树可靠得多。
"""
from __future__ import annotations

import json
import subprocess

# ── keccak-f[1600] ────────────────────────────────────────────────
# hashlib.sha3_256 是 NIST SHA3，**不是** Keccak（padding 不同）。
#    以太坊用的是原始 Keccak256，必须自己实现。
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
       0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
       0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
       0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
       0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
       0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
        [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def _rol(x, n):
    return ((x << n) | (x >> (64 - n))) & _M


def _f(A):
    for rnd in range(24):
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                A[x][y] ^= D[x]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], _ROT[x][y])
        for x in range(5):
            for y in range(5):
                A[x][y] = B[x][y] ^ ((~B[(x + 1) % 5][y]) & _M & B[(x + 2) % 5][y])
        A[0][0] ^= _RC[rnd]
    return A


def keccak256(data: bytes) -> bytes:
    rate = 136                       # 1088 bits，keccak256 的 rate
    A = [[0] * 5 for _ in range(5)]
    # padding 是 0x01（Keccak），不是 0x06（NIST SHA3）—— 差这一个字节
    #    就会算出完全不同的哈希，而且不会报错。
    p = bytearray(data) + b"\x01"
    while len(p) % rate != 0:
        p += b"\x00"
    p = bytearray(p)
    p[-1] |= 0x80
    for off in range(0, len(p), rate):
        blk = p[off:off + rate]
        for i in range(rate // 8):
            w = int.from_bytes(blk[i * 8:i * 8 + 8], "little")
            A[i % 5][i // 5] ^= w
        A = _f(A)
    out = b""
    for i in range(4):
        out += A[i % 5][i // 5].to_bytes(8, "little")
    return out[:32]


def selector(sig: str) -> str:
    return keccak256(sig.encode()).hex()[:8]


# ── 静态类型 ABI 编码（只需要定长 32 字节字） ────────────────────
def enc_addr(a: str) -> str:
    return a.lower().replace("0x", "").rjust(64, "0")


def enc_uint(v: int) -> str:
    return f"{v & ((1 << 256) - 1):064x}"


def enc_int(v: int) -> str:
    return enc_uint(v)          # 二补码，负数由掩码处理


def enc_b32(b: bytes) -> str:
    return b.hex().rjust(64, "0")


# ── RPC ───────────────────────────────────────────────────────────
# 端点从环境读，**不写进代码**（/etc/rhchain.env，chmod 600）。
#    公共端点实测扛不住分析型负载：getLogs 有 10,000 条结果上限，
#    收窄区间又会 `log query timed out` 或 429（2026-09-03 实测）。
#    未配置时降级到公共端点 —— 采集能继续，但分析型扫描会失败。
import os as _os

RPC = (_os.environ.get("RHCHAIN_RPC")
       or _os.environ.get("RHCHAIN_RPC_FALLBACK")
       or "https://rpc.mainnet.chain.robinhood.com")

# **按方法分流端点**（2026-09-04）：两边的限制正好互补。
#    Alchemy 免费档把 eth_getLogs 限到【10 个区块】，全链扫描不可能；
#    公共端点的 getLogs 能吃 200 万区块，但没有归档能力，
#    历史区块上的 eth_call 会失败。
#    所以：日志扫描走公共端点，历史状态查询走 Alchemy。
LOGS_RPC = (_os.environ.get("RHCHAIN_LOGS_RPC")
            or "https://rpc.mainnet.chain.robinhood.com")
_IS_PUBLIC = "alchemy" not in RPC and "quicknode" not in RPC


# **限速器。** 2026-09-03：一次全链 getLogs 扫描把这个公共 RPC 打到
# 429，而当时采集器正在同一台机器上跑 —— 如果不区分错误，429 会被记成
# 「吃不下」写进历史。研究性扫描和采集共用这个节流器。
# **按 Compute Unit 限速，不是按请求数**（2026-09-03 踩过）：
#    Alchemy 免费档是 300 CU/s，而不同方法的 CU 相差 7 倍 ——
#    按 25 次/秒发 eth_getLogs 就是 1,875 CU/s，超限六倍。
#    「一秒几次」这个直觉在按 CU 计费的服务上是错的。
#
# **失败必须收窄整体节奏，不能只收窄查询窗口**：
#    同日实测，撞限流后只把 getLogs 的区间对半砍、却继续全速重试，
#    产生了 2,325 个失败区间、零收获的重试风暴。
#    退避要作用在【发送速率】上。
_CU = {"eth_getLogs": 75, "eth_call": 26, "eth_getCode": 19,
       "eth_getBalance": 19, "eth_blockNumber": 10, "eth_getStorageAt": 17,
       "alchemy_getAssetTransfers": 150}
_CU_DEFAULT = 26
_CU_BUDGET = [60.0 if _IS_PUBLIC else 200.0]     # 留 1/3 余量
_bucket = [0.0, 0.0]


def _throttle(method: str = ""):
    """令牌桶，按方法的 CU 成本扣额。"""
    import time as _t
    cost = _CU.get(method, _CU_DEFAULT)
    now = _t.monotonic()
    if _bucket[0] == 0.0:
        _bucket[0], _bucket[1] = now, _CU_BUDGET[0]
    _bucket[1] = min(_CU_BUDGET[0], _bucket[1] + (now - _bucket[0]) * _CU_BUDGET[0])
    _bucket[0] = now
    if _bucket[1] < cost:
        _t.sleep((cost - _bucket[1]) / _CU_BUDGET[0])
        _bucket[1], _bucket[0] = 0.0, _t.monotonic()
    else:
        _bucket[1] -= cost


def _penalize():
    """撞限流 ⇒ 把预算砍半（下限 20 CU/s），成功一次恢复一点。"""
    _CU_BUDGET[0] = max(20.0, _CU_BUDGET[0] / 2)


def _recover():
    cap = 60.0 if _IS_PUBLIC else 200.0
    _CU_BUDGET[0] = min(cap, _CU_BUDGET[0] * 1.05)


def rpc(method: str, params: list, url: str = None, timeout: int = 25,
        retries: int = 3):
    """返回 (result, err)。

    **err 非 None 表示【调用没成功】，绝不能当成「查到了空」。**
    2026-09-03 踩过两次：429 和 "exceeds limit of 10000" 都被当成
    「没有数据」，一次算出了错误的持仓表，一次差点把 RPC 故障
    写成 no_liquidity 存进时间序列。

    execution reverted 是**例外**：那是合约在说话，属于数据，
    原样返回给调用方判断（见 rhchain.quote）。

    用 curl 不用 urllib —— 与项目其他部分一致（本机 Python 的
    TLS 指纹被多个 CDN 拦过）。"""
    import time as _t
    if url is None:
        url = LOGS_RPC if method == "eth_getLogs" else RPC
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params})
    for attempt in range(retries):
        _throttle(method)
        try:
            r = subprocess.run(["curl", "-sS", "-m", str(timeout), "-X", "POST",
                                "-H", "Content-Type: application/json",
                                "-d", body, url],
                               capture_output=True, timeout=timeout + 5)
            d = json.loads(r.stdout or "{}")
        except Exception as e:
            d = {"error": {"code": -1, "message": repr(e)[:120]}}
        if "result" in d:
            _recover()
            return d["result"], None
        err = d.get("error") or {"code": -2, "message": "空响应"}
        if err.get("code") == 3:            # execution reverted = 数据
            return None, err
        if err.get("code") in (429, -32000) or "limit" in str(err.get("message","")).lower():
            _penalize()
            if attempt < retries - 1:
                _t.sleep(2 ** attempt)
                continue
        return None, err
    return None, {"code": 429, "message": "重试后仍被限流"}


def call(to: str, data_hex: str, url: str = RPC):
    """eth_call。返回 (十六进制串或 None, err)。"""
    out, err = rpc("eth_call", [{"to": to, "data": "0x" + data_hex}, "latest"], url)
    if isinstance(out, str) and out.startswith("0x"):
        return out[2:], None
    return None, err


def words(hexstr: str) -> list[int]:
    return [int(hexstr[i:i + 64], 16) for i in range(0, len(hexstr or ""), 64)]
