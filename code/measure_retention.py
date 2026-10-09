#!/usr/bin/env python3
"""Measure what a public endpoint still serves: state, and events, separately.

    python3 code/measure_retention.py --out-dir measurements/rh-retention

Why this exists. Every issue of the weekly feed carried the sentence "no rolling provable
window exists on this chain". That is true of *state* and false of *events*: at 200,000 blocks
back a state call returns "historical state is not available", while a log query over the same
range returns thousands of events, and events are still served 20,000,000 blocks back. A reader
pointed this out, which is the first of this project's errors caught from outside it.

The lesson is narrower than "we were wrong": a retention claim has to name **which retention
class** it is about. State and events are pruned on different schedules, and a sentence about
the chain is almost always a sentence about one of them.

What this records is what the endpoint answered, at a ladder of depths, with the method beside
it. A timeout is recorded as a timeout and never as "not available" -- the two are different
findings and only one of them is about retention.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

ZERO = "0x0000000000000000000000000000000000000000"
LADDER = [200_000, 1_000_000, 5_000_000, 20_000_000, 50_000_000]
LOG_SPAN = 50          # blocks per log query; small on purpose, so a timeout means depth
UA = {"content-type": "application/json", "user-agent": "executability-report/1.0"}


def rpc(url: str, method: str, params: list, timeout: int = 30) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    try:
        req = urllib.request.Request(url, data=body, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"transport": f"HTTP {e.code}"}}
    except Exception as exc:                                        # noqa: BLE001
        return {"error": {"transport": f"{type(exc).__name__}: {exc}"}}


def classify(resp: dict) -> tuple[str, str]:
    """Return (verdict, detail). A timeout is not an absence."""
    if "error" in resp:
        msg = str(resp["error"].get("message") or resp["error"].get("transport") or resp["error"])
        low = msg.lower()
        if "timed out" in low or "timeout" in low:
            return "timeout", msg
        if "not available" in low or "missing trie" in low or "pruned" in low:
            return "pruned", msg
        return "error", msg
    return "served", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://rpc.mainnet.chain.robinhood.com")
    ap.add_argument("--chain", default="robinhood-4663")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    h = rpc(a.url, "eth_blockNumber", [])
    if "result" not in h:
        print(f"could not read head: {json.dumps(h)[:160]}", file=sys.stderr)
        return 3
    head = int(h["result"], 16)
    print(f"head {head:,}")

    rows = []
    for back in LADDER:
        b = max(1, head - back)
        st = rpc(a.url, "eth_getBalance", [ZERO, hex(b)])
        sv, sd = classify(st)
        time.sleep(0.5)
        lg = rpc(a.url, "eth_getLogs", [{"fromBlock": hex(b), "toBlock": hex(b + LOG_SPAN)}])
        lv, ld = classify(lg)
        n = len(lg.get("result") or []) if lv == "served" else None
        rows.append({"blocks_back": back, "block": b,
                     "state": {"verdict": sv, "detail": sd[:160]},
                     "logs": {"verdict": lv, "count": n, "detail": ld[:160]}})
        print(f"  back {back:>12,}  block {b:>12,}  state {sv:<8}  "
              f"logs {lv}{'' if n is None else f' ({n})'}")
        time.sleep(0.5)

    def deepest(kind: str):
        ok = [r["blocks_back"] for r in rows if r[kind]["verdict"] == "served"]
        return max(ok) if ok else None

    rec = {
        "chain": a.chain,
        "endpoint": a.url,
        "head_at_measurement": head,
        "measured_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "method": (f"one eth_getBalance of the zero address at (head - N), and one eth_getLogs "
                   f"over [head - N, head - N + {LOG_SPAN}], for each N in the ladder; a timeout "
                   f"is recorded as a timeout and not as an absence"),
        "log_span_blocks": LOG_SPAN,
        "ladder": rows,
        "deepest_state_served_blocks_back": deepest("state"),
        "deepest_logs_served_blocks_back": deepest("logs"),
        "note": ("state and events are pruned on different schedules on this endpoint, so a "
                 "retention claim has to name which of the two it is about. Where events are "
                 "served, realised execution is publicly recheckable; where state is not, a "
                 "counterfactual figure at a past block can only be rechecked against an "
                 "archive kept at the time, which is why this project archives its reads."),
    }
    if a.dry_run:
        print(json.dumps(rec, indent=2)[:900])
        return 0
    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"retention-{rec['measured_utc']}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
