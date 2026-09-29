#!/usr/bin/env python3
"""Sampled trajectory of the per-asset accrual multiplier, to count its changes over a month.

For each grid point the script reads a short, exhaustive window ending there and intersects the
intervals [w1/w0, (w1+1)/w0) of every log in it (see read_accrual_index.py for the model). The
intersection is the multiplier and its exact bounds. Where two consecutive samples' intersections
are disjoint, the multiplier changed somewhere in the gap between them -- the gap is the
resolution, and the two bounding logs are the honest bound on when.

Two things this cannot do, stated up front:
  * A change that steps up and back down inside one gap is invisible. Accrual multipliers are not
    expected to do that; this script does not claim they cannot.
  * A sample with no log at all (thin token, long gap) is reported as NO OBSERVATION, never as
    "unchanged".

🔴 Fixed 2026-09-29, ~40 minutes after this file was first published: the comparison between two
samples tested only whether the previous interval sat *above* the next one, so a multiplier that
rose -- the normal direction -- produced no change line at all. The symptom was a printout reading
"2 distinct sampled value(s), 0 change(s)". Detection is now symmetric and names the direction.
Two distinct values in one asset's samples must never coexist with "0 changes" again; if they do,
the detector is wrong, not the chain.

Usage:
    python accrual_index_samples.py --since 2026-09-01T00:00:00Z --stride-blocks 133500
    python accrual_index_samples.py --assets QQQ --stride-blocks 20000 --json out.json
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


def dec(n: int, d: int, places: int = 18) -> str:
    return f"{Decimal(n) / Decimal(d):.{places}f}"


def block_time(url: str, block: int):
    blk, err = rpc(url, "eth_getBlockByNumber", [hex(block), False])
    return int(blk["timestamp"], 16) if not err else None


def fmt(t) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(t)) if t else "?"


def bisect_block_by_time(url: str, target_ts: int, head: int) -> int:
    lo, hi = 1, head
    while lo < hi:
        mid = (lo + hi) // 2
        blk, err = rpc(url, "eth_getBlockByNumber", [hex(mid), False])
        if err:
            raise RuntimeError(f"block {mid}: {err}")
        if int(blk["timestamp"], 16) >= target_ts:
            hi = mid
        else:
            lo = mid + 1
    return lo


def window_value(url: str, addr: str, end: int, floor_block: int, win: int, max_win: int):
    """Exhaustive intersection over [end-win, end]. Returns (dict|None, err|None)."""
    while True:
        lo = max(floor_block, end - win)
        logs, err = rpc(url, "eth_getLogs", [{"address": addr, "topics": [TOPIC0],
                                             "fromBlock": hex(lo), "toBlock": hex(end)}])
        if err:
            if win > 20_000:
                win //= 2
                continue
            return None, err
        if logs or win >= max_win or lo == floor_block:
            break
        win *= 4
    if not logs:
        return None, None
    lo_n = lo_d = hi_n = hi_d = None
    first = last = None
    for lg in logs:
        d = lg["data"][2:]
        if len(d) < 128:
            continue
        w0, w1 = int(d[0:64], 16), int(d[64:128], 16)
        if w0 == 0:
            continue
        b = int(lg["blockNumber"], 16)
        if lo_d is None:
            lo_n, lo_d, hi_n, hi_d = w1, w0, w1 + 1, w0
            first = last = b
            continue
        if w1 * lo_d > lo_n * w0:
            lo_n, lo_d = w1, w0
        if (w1 + 1) * hi_d < hi_n * w0:
            hi_n, hi_d = w1 + 1, w0
        last = b
    if lo_d is None:
        return None, None
    return {"lo_n": lo_n, "lo_d": lo_d, "hi_n": hi_n, "hi_d": hi_d,
            "first_log_block": first, "last_log_block": last, "logs": len(logs),
            "window": [lo, end]}, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01T00:00:00Z")
    ap.add_argument("--until", default="")
    ap.add_argument("--assets", default=",".join(STOCKS))
    ap.add_argument("--stride-blocks", type=int, default=133_500)
    ap.add_argument("--window", type=int, default=2_000)
    ap.add_argument("--max-window", type=int, default=200_000)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    url = rpc_url()
    head_r, err = rpc(url, "eth_blockNumber", [])
    if err:
        print("FATAL:", err)
        return 2
    head = int(head_r, 16)
    start = bisect_block_by_time(
        url, calendar.timegm(time.strptime(args.since, "%Y-%m-%dT%H:%M:%SZ")), head)
    end = bisect_block_by_time(
        url, calendar.timegm(time.strptime(args.until, "%Y-%m-%dT%H:%M:%SZ")), head) \
        if args.until else head
    print(f"head {head:,} ({fmt(block_time(url, head))})   "
          f"scan {start:,} -> {end:,} ({fmt(block_time(url, start))} .. {fmt(block_time(url, end))})"
          f"   stride {args.stride_blocks:,} blocks")

    result = {"topic0": TOPIC0, "start_block": start, "end_block": end, "head": head,
              "stride_blocks": args.stride_blocks, "window": args.window, "assets": {}}
    notes: list[str] = []

    for sym in [s.strip().upper() for s in args.assets.split(",") if s.strip()]:
        addr = STOCKS[sym]
        samples = []
        b = start
        while b <= end:
            s, werr = window_value(url, addr, b, start, args.window, args.max_window)
            if werr:
                notes.append(f"{sym}: sample at {b:,} FAILED ({werr}) -- gap, not 'unchanged'")
            samples.append({"grid_block": b, "value": s})
            b += args.stride_blocks
        if samples and samples[-1]["grid_block"] != end:
            s, werr = window_value(url, addr, end, start, args.window, args.max_window)
            if werr:
                notes.append(f"{sym}: final sample at {end:,} FAILED ({werr})")
            samples.append({"grid_block": end, "value": s})

        observed = [x for x in samples if x["value"]]
        gaps = len(samples) - len(observed)
        changes = []
        for prev, cur in zip(observed, observed[1:]):
            p, c = prev["value"], cur["value"]
            # Disjoint intervals mean the multiplier changed in the gap. The previous interval
            # lying entirely below the next one is a rise; entirely above it is a fall. Both are
            # changes, and testing only one of the two is the bug this file shipped with.
            rose = p["hi_n"] * c["lo_d"] <= c["lo_n"] * p["hi_d"]
            fell = c["hi_n"] * p["lo_d"] <= p["lo_n"] * c["hi_d"]
            if fell or rose:
                changes.append({
                    "after_block": p["last_log_block"], "before_block": c["first_log_block"],
                    "direction": "rise" if rose else "fall",
                    "k_before": dec(p["lo_n"], p["lo_d"]), "k_after": dec(c["hi_n"], c["hi_d"]),
                    "blocks": c["first_log_block"] - p["last_log_block"],
                })
        if observed:
            vals = {dec(x["value"]["lo_n"], x["value"]["lo_d"], 12) for x in observed}
            print(f"\n{sym}: {len(observed)}/{len(samples)} samples had a log "
                  f"({gaps} no-observation), {len(vals)} distinct sampled value(s) to 12 decimals, "
                  f"{len(changes)} change(s) between consecutive samples")
            for v in sorted(vals):
                print(f"    value {v}")
            print("    (the intervals decide whether two samples differ, not these rounded "
                  "strings; full precision is in the JSON)")
        else:
            print(f"\n{sym}: NO OBSERVATION in any sample -- nothing claimed")
        for ch in changes:
            ta, tb = block_time(url, ch["after_block"]), block_time(url, ch["before_block"])
            ch["after_block_time"], ch["before_block_time"] = fmt(ta), fmt(tb)
            print(f"    change ({ch['direction']}): {ch['k_before'][:20]} -> "
                  f"{ch['k_after'][:20]}  between block "
                  f"{ch['after_block']:,} ({fmt(ta)}) and {ch['before_block']:,} ({fmt(tb)})")
        result["assets"][sym] = {"samples": samples, "changes": changes,
                                 "no_observation_gaps": gaps}

    if notes:
        result["notes"] = notes
        print("\nNOTES / GAPS (not hidden):")
        for n in notes:
            print("  -", n)
    if args.json:
        p = Path(args.json)
        p.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"\nwrote {p} ({p.stat().st_size:,} bytes)")
    return 1 if notes else 0


if __name__ == "__main__":
    sys.exit(main())
