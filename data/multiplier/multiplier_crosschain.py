#!/usr/bin/env python3
"""同一小时、两条链、两个发行方:读同一 underlying 的 wrapper 乘数。

**为什么这是 Base 线上第一个该做的测量**:它不需要池表、不需要 quoter、不需要归档端点
—— 8 次 getter 调用 ⇒ 却给出一个没人发表过的事实:
  同一 underlying,被两个发行方包装,累积的乘数不同。
而它正是"同 ticker ≠ 同资产"那条红线的【证据】,不再只是措辞纪律。

🔴 必须【同一次运行里读两条链】。乘数随时间累积 ⇒ 两个日期的数字相减是日期差异,
   不是 wrapper 差异。这是本脚本存在的全部理由,所以:
     · 两条链在同一次运行里读,并各自记录 block 与 UTC
     · 若两次读的 UTC 相差超过 --max-skew 秒 ⇒ 标记 skew_exceeded,结论降级为"不可比"
🔴 控制组:先验选择器(与公开常数比对)+ 先读一个【已知 =1.0】的代币
   (若连恰好 1.0 的那几个都读不出 10**18,是我们的链路坏了,不是对方没这个函数)
🔴 身份:地址由调用者给出,且必须附来源。vanity 前缀(0xb2…)只是启发式,不是身份判据。

用法
  python3 multiplier_crosschain.py --selftest
  python3 multiplier_crosschain.py --out mult-$(date -u +%Y%m%dT%H%MZ).json
"""
from __future__ import annotations

import argparse, json, os, sys, time, urllib.error, urllib.request
from decimal import Decimal, getcontext

getcontext().prec = 40
# evm.py (keccak256) and rhchain.py (the RH address list) both live in code/ at the
# repository root. This file is published under data/multiplier/, so the repo-relative
# candidate is ../../code — that one is the reason this script runs from where it is
# published. Set EVM_PATH to override.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _c in ([os.environ["EVM_PATH"]] if os.environ.get("EVM_PATH") else []) + [
        _HERE,
        os.path.join(_HERE, "code"),
        os.path.join(_HERE, "..", "code"),
        os.path.join(_HERE, "..", "..", "code"),
]:
    if os.path.exists(os.path.join(_c, "evm.py")):
        sys.path.insert(0, _c)
        break
try:
    from evm import keccak256
except ImportError:
    sys.exit("evm.py not found (keccak256 needed). It lives in code/ at the repository "
             "root; run from the repo, or set EVM_PATH.")

ONE = Decimal(10) ** 18
UA = "multiplier-crosschain/1.0"

# 🔴 两组地址都带来源。Base 那七个由 2026-10-02 的两步交叉核准;
#    RH 链那九个来自 dexfeed/chain/rhchain.py 的 STOCKS(本仓库自己维护的清单)。
CHAINS = {
    "base-8453": {
        "rpc": "https://mainnet.base.org",
        "issuer": "Coinbase-issued wrapper (cToken naming)",
        "source": "on-chain index + token0() of a derived pool, cross-checked 2026-10-02",
        "tokens": {
            "AAPL":  "0xb200000000000000000000C2e324d24d7eEcd1fb",
            "AMZN":  "0xb200000000000000000000d9192b6b456483c2e8",
            "GOOGL": "0xb2000000000000000000002D0BA3164cc74f58B7",
            "META":  "0xb2000000000000000000008bC8786B856E61707C",
            "MSFT":  "0xB200000000000000000000Ab99cFa739E253872B",
            "NVDA":  "0xb20000000000000000000078ee7ce2fE4908108C",
            "TSLA":  "0xb2000000000000000000001e800a7f5189430cD0",
        },
    },
    "robinhood-4663": {
        "rpc": os.environ.get("RH_RPC", ""),       # 需要能读 RH 链的端点;留空则只跑 Base
        "issuer": "Robinhood Assets (Jersey) Ltd wrapper",
        "source": "dexfeed/chain/rhchain.py STOCKS",
        "tokens": {},                              # 运行时从 rhchain.STOCKS 填,见 load_rh()
    },
}
SEL_CANDIDATES = ["uiMultiplier()", "multiplier()"]
KNOWN_SELECTORS = {"totalSupply()": "18160ddd", "balanceOf(address)": "70a08231"}


def sel(sig): return keccak256(sig.encode()).hex()[:8]


def rpc(url, method, params, tries=3, timeout=25):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for a in range(tries):
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                p = json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"; time.sleep(0.6 * (a + 1)); continue
        except Exception as e:                                        # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:60]}"; time.sleep(0.6 * (a + 1)); continue
        if "error" in p:
            return None, str(p["error"])[:140]
        return p.get("result"), None
    return None, last or "unknown"


def load_rh():
    """RH 链那九个地址从本仓库自己的清单读,不硬编码第二份。"""
    try:
        from rhchain import STOCKS
    except ImportError:
        return {}
    return dict(STOCKS)


def read_multiplier(url, addr, blk):
    """按候选逐个试;返回 (sig, raw_uint, Decimal) 或 (None, None, None)。"""
    for sig in SEL_CANDIDATES:
        raw, err = rpc(url, "eth_call", [{"to": addr, "data": "0x" + sel(sig)}, blk])
        if raw and raw != "0x":
            n = int(raw, 16)
            return sig, n, Decimal(n) / ONE
        time.sleep(0.2)
    return None, None, None


def selftest() -> int:
    ok = True
    print("离线自测 ① 选择器(公开常数,控制组):")
    for sig, want in KNOWN_SELECTORS.items():
        got = sel(sig); good = got == want
        print(f"  {'✓' if good else '✗'} {sig:26} {got} / {want}"); ok &= good
    print("\n离线自测 ② 乘数换算(已知值):")
    cases = [("0x0de0b6b3a7640000", Decimal(1)),
             ("0x0de29ff478c03149", Decimal("1.000537939576369481"))]
    for h, want in cases:
        got = Decimal(int(h, 16)) / ONE
        good = got == want
        print(f"  {'✓' if good else '✗'} {h} → {got}"); ok &= good
    print("\n离线自测 ③ skew 判定:")
    good = _skew_verdict(10, 60) == "comparable" and _skew_verdict(600, 60) == "skew_exceeded"
    print(f"  {'✓' if good else '✗'} 10s 可比 / 600s 超限"); ok &= good
    print("\n⚠️ 联网那一半本机跑不了(出网 403)⇒ 本地侧跑。")
    return 0 if ok else 1


def _skew_verdict(skew_s, max_skew):
    return "comparable" if abs(skew_s) <= max_skew else "skew_exceeded"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-skew", type=int, default=120,
                    help="两条链读取时间差上限(秒);超过即判不可比")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if selftest() != 0:
        print("🔴 自测不过,停止"); return 1

    CHAINS["robinhood-4663"]["tokens"] = load_rh()
    out = {"measured_purpose": ("same underlying, two issuers' wrappers, read in one run so the "
                               "difference is wrapper accrual and not a difference of dates"),
           "max_skew_s": a.max_skew, "chains": {}}
    for cid, cfg in CHAINS.items():
        if not cfg["rpc"] or not cfg["tokens"]:
            print(f"\n=== {cid} 跳过(rpc 或 token 清单为空)")
            continue
        head_r, err = rpc(cfg["rpc"], "eth_blockNumber", [])
        if err:
            print(f"\n=== {cid} 连不上:{err}"); continue
        head = int(head_r, 16)
        t0 = time.time()
        print(f"\n=== {cid} · head {head:,} · {cfg['issuer']}")
        rows = {}
        for tick, addr in sorted(cfg["tokens"].items()):
            sig, n, m = read_multiplier(cfg["rpc"], addr, hex(head))
            rows[tick] = {"address": addr, "getter": sig, "raw": n,
                          "multiplier": (f"{m:.18f}" if m is not None else None),
                          "bp_from_one": (float((m - 1) * 10000) if m is not None else None)}
            print(f"  {tick:6} {addr}  {sig or '—':16} "
                  f"{(f'{m:.18f}' if m is not None else 'no getter'):22}"
                  f"{'' if m is None else f'  {float((m-1)*10000):+.2f} bp'}")
        ones = [t for t, r in rows.items() if r["raw"] == 10**18]
        if not ones:
            print("  ⚠️ 控制组:没有任何一个读出恰好 1.0 —— 可能是链路问题,先别信这一组")
        out["chains"][cid] = {"head": head, "read_started_utc":
                              time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
                              "read_finished_utc":
                              time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "issuer": cfg["issuer"], "address_source": cfg["source"],
                              "tokens": rows,
                              "control_exactly_one": ones}

    cs = list(out["chains"].values())
    if len(cs) == 2:
        import calendar
        def ep(s): return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
        skew = abs(ep(cs[0]["read_started_utc"]) - ep(cs[1]["read_started_utc"]))
        out["skew_s"] = skew
        out["verdict"] = _skew_verdict(skew, a.max_skew)
        print(f"\n两条链读取时间差 {skew}s ⇒ {out['verdict']}")
        ks = set(cs[0]["tokens"]) & set(cs[1]["tokens"])
        print("\n重叠 ticker(同 underlying,两个 wrapper):")
        for t in sorted(ks):
            x, y = cs[0]["tokens"][t], cs[1]["tokens"][t]
            print(f"  {t:6} {x['multiplier']}  vs  {y['multiplier']}")
        out["overlap"] = sorted(ks)
    else:
        out["verdict"] = "single_chain_only"
        print("\n只读到一条链 ⇒ 不构成跨链对照(需要 RH_RPC 环境变量)")

    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
        print(f"\n写入 {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
