#!/usr/bin/env python3
"""Exact history of the per-asset accrual multiplier on Robinhood Chain tokenised stocks.

Model being tested (MEASURED 2026-09-28, see read_accrual_index.py): every ERC-20 Transfer of a
tokenised stock is accompanied by a log from the same contract, same (from,to), with
    topics[0] = 0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802
    data      = (w0, w1),  w0 = the transferred amount,  w1 = floor(w0 * k_asset)
where k_asset is a per-asset multiplier that is constant between accrual events.

No floating point is used to establish this. Each log gives an interval that k must lie in:
    k in [ w1/w0 , (w1+1)/w0 )
A run of consecutive logs whose intervals have a common point is one multiplier value. Where two
consecutive logs' intervals do not intersect, the multiplier changed *somewhere between those two
transfers* -- that is the honest bound, because a change with no transfer emits nothing.

Output: per asset, the observed multiplier values with the block window each is bounded by, and a
count of observed changes (a lower bound: an unobserved change is invisible).
Writes accrual-index-history.json next to this file's sibling directory when --json is given.
"""
from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from decimal import Decimal, getcontext
from pathlib import Path

from read_accrual_index import STOCKS, TOPIC0, rpc, rpc_url

getcontext().prec = 60


def bisect_block_by_time(url: str, target_ts: int, head: int) -> int:
    """Smallest block whose timestamp >= target_ts (chain has no timestamp index)."""
    lo, hi = 1, head
    while lo < hi:
        mid = (lo + hi) // 2
        blk, err = rpc(url, "eth_getBlockByNumber", [hex(mid), False])
        if err:
            raise RuntimeError(f"block {mid}: {err}")
        ts = int(blk["timestamp"], 16)
        if ts >= target_ts:
            hi = mid
        else:
            lo = mid + 1
    return lo


def block_time(url: str, block: int) -> int | None:
    blk, err = rpc(url, "eth_getBlockByNumber", [hex(block), False])
    return int(blk["timestamp"], 16) if not err else None


def dec(n: int, d: int, places: int = 18) -> str:
    return f"{Decimal(n) / Decimal(d):.{places}f}"


def scan_asset(url: str, sym: str, start: int, head: int, chunk: int, sleep: float):
    """Returns (epochs, calls, failures). epochs = list of dicts."""
    addr = STOCKS[sym]
    epochs: list[dict] = []
    failures: list[str] = []
    calls = 0
    cur: dict | None = None
    pending_start = start

    def open_epoch(b: int, w0: int, w1: int) -> dict:
        return {"lo_n": w1, "lo_d": w0, "hi_n": w1 + 1, "hi_d": w0,
                "first_block": b, "last_block": b, "logs": 0,
                "precision_w0": w0}

    lo = start
    while lo <= head:
        hi = min(head, lo + chunk - 1)
        logs, err = rpc(url, "eth_getLogs", [{"address": addr, "topics": [TOPIC0],
                                             "fromBlock": hex(lo), "toBlock": hex(hi)}])
        calls += 1
        if err:
            if chunk > 20_000:                     # range/cap refusal: halve and retry
                chunk = max(20_000, chunk // 2)
                failures.append(f"{sym}: range {lo}-{hi} refused ({err}); retrying with "
                                f"chunk={chunk}")
                continue
            failures.append(f"{sym}: range {lo}-{hi} FAILED ({err}) -- gap left, not hidden")
            lo = hi + 1
            continue
        for lg in logs:
            d = lg["data"][2:]
            if len(d) < 128:
                continue
            w0, w1 = int(d[0:64], 16), int(d[64:128], 16)
            if w0 == 0:
                continue
            b = int(lg["blockNumber"], 16)
            if cur is None:
                cur = open_epoch(b, w0, w1)
                continue
            nlo_n, nlo_d = cur["lo_n"], cur["lo_d"]
            if w1 * nlo_d > nlo_n * w0:            # max(lo, w1/w0)
                nlo_n, nlo_d = w1, w0
            nhi_n, nhi_d = w1 + 1, w0
            if nhi_n * cur["hi_d"] > cur["hi_n"] * nhi_d:   # min(hi, (w1+1)/w0)
                nhi_n, nhi_d = cur["hi_n"], cur["hi_d"]
            if nlo_n * nhi_d < nhi_n * nlo_d:      # non-empty intersection: same multiplier
                cur.update(lo_n=nlo_n, lo_d=nlo_d, hi_n=nhi_n, hi_d=nhi_d, last_block=b,
                           logs=cur["logs"] + 1)
                if w0 > cur["precision_w0"]:
                    cur["precision_w0"] = w0
            else:
                epochs.append(cur)
                cur = open_epoch(b, w0, w1)
        lo = hi + 1
        if sleep:
            time.sleep(sleep)
    if cur is not None:
        epochs.append(cur)

    out = []
    for e in epochs:
        out.append({
            "k_lo": dec(e["lo_n"], e["lo_d"]),
            "k_hi": dec(e["hi_n"], e["hi_d"]),
            "first_block": e["first_block"], "last_block": e["last_block"],
            "logs": e["logs"],
            "finest_log_w0": e["precision_w0"],
        })
    return out, calls, failures, chunk


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-block", type=int, default=0,
                    help="0 = derive from --since")
    ap.add_argument("--since", default="2026-09-01T00:00:00Z")
    ap.add_argument("--until", default="", help="ISO UTC block-time bound; empty = chain head")
    ap.add_argument("--assets", default=",".join(STOCKS))
    ap.add_argument("--chunk", type=int, default=267_000)
    ap.add_argument("--sleep", type=float, default=0.05)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    url = rpc_url()
    head_r, err = rpc(url, "eth_blockNumber", [])
    if err:
        print("FATAL:", err)
        return 2
    head = int(head_r, 16)

    if args.start_block:
        start = args.start_block
    else:
        ts = calendar.timegm(time.strptime(args.since, "%Y-%m-%dT%H:%M:%SZ"))
        start = bisect_block_by_time(url, ts, head)
    if args.until:
        end = bisect_block_by_time(
            url, calendar.timegm(time.strptime(args.until, "%Y-%m-%dT%H:%M:%SZ")), head)
    else:
        end = head
    head_ts = block_time(url, head)
    start_ts = block_time(url, start)
    print(f"chain head {head:,} ({time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(head_ts))})")
    print(f"scan       {start:,} -> {end:,} "
          f"({time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(start_ts))} .. "
          f"{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(block_time(url, end) or 0))})"
          f"  span {end - start:,} blocks")

    result: dict = {"topic0": TOPIC0, "head": head, "head_time": head_ts,
                    "start_block": start, "start_time": start_ts, "assets": {}}
    all_failures: list[str] = []
    for sym in [s.strip().upper() for s in args.assets.split(",") if s.strip()]:
        t0 = time.time()
        epochs, calls, failures, chunk = scan_asset(url, sym, start, end, args.chunk, args.sleep)
        all_failures += failures
        steps = max(0, len(epochs) - 1)
        print(f"\n{sym}: {len(epochs)} distinct multiplier runs, {steps} observed change(s) "
              f"({calls} calls, chunk now {chunk:,}, {time.time() - t0:.0f}s)")
        for i, e in enumerate(epochs):
            print(f"  run {i}: {e['k_lo'][:22]} … {e['k_hi'][:22]}  "
                  f"blocks {e['first_block']:,}–{e['last_block']:,}  ({e['logs']} logs)")
        for i in range(1, len(epochs)):
            a, b = epochs[i - 1]["last_block"], epochs[i]["first_block"]
            ts_a, ts_b = block_time(url, a), block_time(url, b)
            span = (ts_b - ts_a) if (ts_a and ts_b) else None
            fmt = lambda t: time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(t))  # noqa: E731
            print(f"    change {i}: unobserved between block {a:,} "
                  f"({fmt(ts_a) if ts_a else '?'}) and block {b:,} "
                  f"({fmt(ts_b) if ts_b else '?'})"
                  + (f"  = {span} s, {b - a:,} blocks" if span is not None else ""))
            result["assets"].setdefault(sym, {})["changes"] = result["assets"].get(
                sym, {}).get("changes", [])
            result["assets"][sym]["changes"].append(
                {"after_block": a, "before_block": b, "seconds": span, "blocks": b - a,
                 "after_block_time": fmt(ts_a) if ts_a else None,
                 "before_block_time": fmt(ts_b) if ts_b else None,
                 "k_before": epochs[i - 1]["k_lo"], "k_after": epochs[i]["k_hi"]})
        result["assets"].setdefault(sym, {})["runs"] = epochs

    if all_failures:
        result["failures"] = all_failures
        print("\nFAILURES / GAPS (not skipped):")
        for f in all_failures:
            print("  -", f)
    if args.json:
        p = Path(args.json)
        p.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"\nwrote {p} ({p.stat().st_size:,} bytes)")
    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
