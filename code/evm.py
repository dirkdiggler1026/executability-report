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


def _is_public(url: str) -> bool:
    """Whether THIS endpoint is one of the rate-limited public ones.

    Asked of the URL a request is going to, not of the primary endpoint. The two differ here:
    getLogs is routed to LOGS_RPC while everything else goes to RPC, so a budget chosen from RPC
    was being spent on whichever endpoint the method actually used (2026-09-15).
    """
    return "alchemy" not in url and "quicknode" not in url


def _cap_for(url: str) -> float:
    """CU/s ceiling for one endpoint, leaving about a third of headroom."""
    return 60.0 if _is_public(url) else 200.0


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
#
# **节流状态必须按端点分开**（2026-09-15）：此前只有一份 `_CU_BUDGET` 和一个桶，
#    而预算按【主端点】判。于是 `RHCHAIN_RPC` 设为 Alchemy 时预算是 200 CU/s，
#    而 `eth_getLogs` 实际发往公共的 `LOGS_RPC` —— 对公共端点的许可放宽了 3.33 倍，
#    正是 2026-09-03 那次事故的场景。四种耦合，必须一起改：
#      ① 预算按 url 选      ② 桶按 url 分
#      ③ 惩罚/恢复按 url 分  ④ 恢复的上限也按 url 算
#    ④ 是反向的一层：`_recover` 每次成功都把预算 ×1.05 抬回上限，
#    所以采集器自己成功的 Alchemy 调用，会不断把扫描在公共端点上的许可抬回去。
#    ⇒ 干扰是双向的；只把桶分开、不把惩罚和恢复分开，堵不住。
_CU = {"eth_getLogs": 75, "eth_call": 26, "eth_getCode": 19,
       "eth_getBalance": 19, "eth_blockNumber": 10, "eth_getStorageAt": 17,
       "alchemy_getAssetTransfers": 150}
_CU_DEFAULT = 26

# One token bucket and one budget PER URL. See the note above for why one is not enough.
_state: dict[str, list] = {}


def _state_for(url: str) -> list:
    st = _state.get(url)
    if st is None:
        st = [0.0, 0.0, _cap_for(url)]      # last timestamp, tokens, budget
        _state[url] = st
    return st


def _throttle(method: str = "", url: str = ""):
    """令牌桶，按方法的 CU 成本扣额，**只对本端点**扣。"""
    import time as _t
    st = _state_for(url)
    budget = st[2]
    cost = _CU.get(method, _CU_DEFAULT)
    now = _t.monotonic()
    if st[0] == 0.0:
        st[0], st[1] = now, budget
    st[1] = min(budget, st[1] + (now - st[0]) * budget)
    st[0] = now
    if st[1] < cost:
        _t.sleep((cost - st[1]) / budget)
        st[1], st[0] = 0.0, _t.monotonic()
    else:
        st[1] -= cost


def _penalize(url: str = ""):
    """本端点撞限流 ⇒ 只砍【本端点】的预算（下限 20 CU/s）。"""
    st = _state_for(url)
    st[2] = max(20.0, st[2] / 2)


def _recover(url: str = ""):
    """本端点成功一次 ⇒ 只恢复本端点的预算，回到【本端点】的上限。"""
    st = _state_for(url)
    st[2] = min(_cap_for(url), st[2] * 1.05)



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
        _throttle(method, url)
        try:
            r = subprocess.run(["curl", "-sS", "-m", str(timeout), "-X", "POST",
                                "-H", "Content-Type: application/json",
                                "-d", body, url],
                               capture_output=True, timeout=timeout + 5)
            d = json.loads(r.stdout or "{}")
        except Exception as e:
            # 🔴 `repr(e)` 对 subprocess.TimeoutExpired 会展开整条 argv —— 里面有
            #    带 key 的 url。而这个 message 会被 verify.py 的 preflight 原样印在
            #    屏幕上(第三方跑、录屏演示都会看到)。
            #
            #    今天它印不出来。2026-09-19 两边各量了一次(0-based 索引):
            #        现状 url 在 -d body 之后   url@174  key@217  截断 120 ⇒ 余量 54 / 97
            #        调序 url 挪到 -d 之前      url@ 98  key@141  ⇒ key 仍不进前 120
            #        极端 url 挪到 argv 最前    url@ 25  key@ 68  ⇒ 【只有这一种会印出 key】
            #    key 在 url 内的偏移是 43(`https://…/v2/` 那一段),
            #    所以对现实的调序,冗余来自这个偏移,**不是**来自 argv 顺序 ——
            #    这一行防的是最后那种极端情况。
            #
            #    ⚠️ 复核时【不要】用 `url in message` 当判据:url@98 那种情形下
            #       url 被从中间截断,判出来是 False,而主机名其实已经进画面 ——
            #       假阴性。要查就查 key 本身:`key in message[:120]`。
            #
            #    删掉这一行是静默的 —— 这段注释是它目前唯一的守卫。
            #    (这个仓库没有 CI、没有 selftest;补测试运行器是提交之后的事。)
            d = {"error": {"code": -1, "message": repr(e).replace(url, "<rpc>")[:120]}}
        if "result" in d:
            _recover(url)
            return d["result"], None
        err = d.get("error") or {"code": -2, "message": "empty response from the RPC"}
        if err.get("code") == 3:            # execution reverted = 数据
            return None, err
        if err.get("code") in (429, -32000) or "limit" in str(err.get("message","")).lower():
            _penalize(url)
            if attempt < retries - 1:
                _t.sleep(2 ** attempt)
                continue
        return None, err
    return None, {"code": 429, "message": "still rate-limited after retries"}


def call(to: str, data_hex: str, url: str = RPC):
    """eth_call。返回 (十六进制串或 None, err)。"""
    out, err = rpc("eth_call", [{"to": to, "data": "0x" + data_hex}, "latest"], url)
    if isinstance(out, str) and out.startswith("0x"):
        return out[2:], None
    return None, err


def words(hexstr: str) -> list[int]:
    return [int(hexstr[i:i + 64], 16) for i in range(0, len(hexstr or ""), 64)]
