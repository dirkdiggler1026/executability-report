#!/usr/bin/env python3
"""Does the market price the dividend index? Test registered in
PREREG-tsv-volume-cap-2026-09-28 addendum 2 §4, as amended by addendum 3 §3.

    python3 index_priced_test.py --asset QQQ --control TSLA --step-lo <blk> --step-hi <blk>

Reads pool slot0 and the chain's Chainlink feed at each published pinned block either side
of the step, and reports three series -- pool mid, oracle answer, and their ratio R -- for
the subject and for a control whose index is exactly 1.000000000 and therefore cannot move
for this reason.

🔴 The five readings are in addendum 3 §3.2 and are NOT restated here as conclusions; this
   program prints the numbers and which reading they select, and it prints the numbers even
   when they select "inconclusive" or "the test failed".
🔴 The threshold is the data's own noise (addendum 3 §3.3): the step's change in log R,
   against the standard deviation of that change between adjacent rounds in the same window.
🔴 The falsifier (addendum 3 §3.4, made attributable in addendum 4 §2): if the control steps
   comparably, the method is wrong and the output names which of the three series moved.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evm import keccak256                                        # noqa: E402

Q96 = 1 << 96
LATEST_ROUND_DATA = "0xfeaf968c"
ORACLE = {
    "QQQ":  "0x80901d846d5D7B030F26B480776EE3b29374C2ae",
    "SPY":  "0x319724394D3A0e3669269846abE664Cd621f9f6A",
    "TSLA": "0x4A1166a659A55625345e9515b32adECea5547C38",
    "AAPL": "0x6B22A786bAa607d76728168703a39Ea9C99f2cD0",
}


def rpc_url() -> str:
    for line in open("/etc/rhchain.env"):
        if line.startswith("RHCHAIN_RPC="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no RHCHAIN_RPC")


URL = rpc_url()          # archive: this reads historical state, so it needs the key


def call(to, data, blk):
    p = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
         "params": [{"to": to, "data": data}, hex(blk)]}
    r = subprocess.run(["curl", "-sS", "-m", "40", "-X", "POST", "-H",
                        "content-type: application/json", "-d", json.dumps(p), URL],
                       capture_output=True, timeout=60)
    j = json.loads(r.stdout.decode())
    return j.get("result"), str((j.get("error") or {}).get("message", ""))[:80]


def pool_mid(pool, stock_is_token0, quote_decimals, blk):
    s0, e = call(pool, "0x" + keccak256(b"slot0()").hex()[:8], blk)
    if not s0 or len(s0) < 66:
        return None, e or "slot0 unreadable"
    raw = (int(s0[2:66], 16) / Q96) ** 2
    mid = (raw * 10 ** (18 - quote_decimals)) if stock_is_token0 \
        else (1 / (raw * 10 ** (quote_decimals - 18)))
    return (mid if mid > 0 else None), ("" if mid > 0 else "mid<=0")


def oracle_answer(feed, blk):
    r, e = call(feed, LATEST_ROUND_DATA, blk)
    if not r or len(r) < 322:
        return None, None, e or "short"
    w = r[2:]
    answer = int(w[64:128], 16)
    updated = int(w[192:256], 16)
    d, _ = call(feed, "0x" + keccak256(b"decimals()").hex()[:8], blk)
    dec = int(d, 16) if d and d != "0x" else 8
    return answer / 10 ** dec, updated, ""


def series_stats(xs):
    """Δlog between adjacent points: (list, stdev)."""
    d = [math.log(xs[i] / xs[i - 1]) for i in range(1, len(xs)) if xs[i - 1] and xs[i]]
    return d, (statistics.pstdev(d) if len(d) > 1 else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--control", default="TSLA")
    ap.add_argument("--step-lo", type=int, required=True)
    ap.add_argument("--step-hi", type=int, required=True)
    ap.add_argument("--index-subject", type=float, required=True,
                    help="the measured index after the step, e.g. 1.000700791")
    ap.add_argument("--rounds", default="/opt/rh-report/data")
    ap.add_argument("--days", nargs="+", required=True)
    ap.add_argument("--each-side", type=int, default=12)
    ap.add_argument("--pools", required=True,
                    help="json: {asset: [pool, stock_is_token0, quote_decimals]}")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pools = json.loads(a.pools)

    blocks = []
    for d in a.days:
        for line in open(os.path.join(a.rounds, d, "rounds.jsonl")):
            if line.strip():
                r = json.loads(line)
                blocks.append((r["block"], r["ts"]))
    blocks = sorted(set(blocks))
    pre = [b for b in blocks if b[0] <= a.step_lo][-a.each_side:]
    post = [b for b in blocks if b[0] >= a.step_hi][:a.each_side]
    print(f"  step bracketed by {a.step_lo:,} .. {a.step_hi:,}; "
          f"{len(pre)} rounds before, {len(post)} after", flush=True)

    out = {"registered_in": ["PREREG-tsv-volume-cap-2026-09-28-addendum-2.md §4",
                             "PREREG-tsv-volume-cap-2026-09-28-addendum-3.md §3"],
           "subject": a.asset, "control": a.control,
           "step": {"lo": a.step_lo, "hi": a.step_hi},
           "index_after_step": a.index_subject, "series": {}}

    for name in (a.asset, a.control):
        pool, is0, qdec = pools[name]
        rows = []
        for blk, ts in pre + post:
            m, me = pool_mid(pool, is0, qdec, blk)
            o, upd, oe = oracle_answer(ORACLE[name], blk)
            rows.append({"block": blk, "ts": ts, "side": "pre" if blk <= a.step_lo else "post",
                         "pool_mid": m, "oracle": o, "oracle_updated_at": upd,
                         "R": (m / o) if (m and o) else None,
                         "err": (me or oe) or None})
            print(f"    {name:5} {blk:,}  mid {('%.6f'%m) if m else '—':>12}  "
                  f"oracle {('%.6f'%o) if o else '—':>12}  "
                  f"R {('%.8f'%(m/o)) if (m and o) else '—'}", flush=True)
        out["series"][name] = rows

    # the measurement: Δlog across the step, against adjacent-round noise
    for name in (a.asset, a.control):
        rows = [r for r in out["series"][name] if r["R"]]
        pre_r = [r for r in rows if r["side"] == "pre"]
        post_r = [r for r in rows if r["side"] == "post"]
        res = {}
        for label, key in (("R", "R"), ("pool_mid", "pool_mid"), ("oracle", "oracle")):
            p0 = [r[key] for r in pre_r if r[key]]
            p1 = [r[key] for r in post_r if r[key]]
            if len(p0) < 2 or len(p1) < 2:
                res[label] = {"insufficient": True}; continue
            d0, s0 = series_stats(p0)
            d1, s1 = series_stats(p1)
            noise = statistics.pstdev(d0 + d1) if len(d0 + d1) > 1 else 0.0
            step = math.log(p1[0] / p0[-1])
            res[label] = {
                "step_bp": step * 1e4,
                "adjacent_noise_bp": noise * 1e4,
                "signal_over_noise": (step / noise) if noise else None,
                "n_pre": len(p0), "n_post": len(p1),
            }
        out["series"][name + "_stats"] = res
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"  wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
