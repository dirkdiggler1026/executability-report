#!/usr/bin/env python3
"""Read the per-asset accrual multiplier that tokenised stocks emit inside their transfer logs.

MEASURED (2026-09-28/29): a transfer of a tokenised stock on Robinhood Chain (chainId 4663) is
accompanied by a second log from the same contract, carrying the same sender and recipient:
    topics[0] = 0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802
    topics[1], topics[2] = from, to
    data = (w0, w1)    w0 = the transferred amount,   w1 = floor(w0 x k)
so the multiplier k is the RATIO of the two words. Nothing in the log is k by itself: there is no
getter we could find and no event names it, so k is visible only by dividing the two words. (An
earlier note in this file's history described k as a stored fixed-point word; that was wrong and
this is the reading the ratio_report below actually establishes.)

The script does not assume which word holds what. It groups logs by word count and, per word
position, prints how many distinct values it took inside the window -- which is how the ratio was
found in the first place (no single position is constant). k itself comes from ratio_report().

Usage:
    python read_accrual_index.py                # all nine assets, ~20k-block window
    python read_accrual_index.py --blocks 60000 --assets SPY,AMC
    python read_accrual_index.py --samples 5    # show 5 raw logs per asset

Nothing is written. The RPC is $RH_RPC, else RPC_MAINNET from ../.env, else the public endpoint.
Failures are reported, never skipped silently.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOPIC0 = "0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
SCALE = 10 ** 18
PUBLIC_RPC = "https://rpc.mainnet.chain.robinhood.com"
ENV = Path(__file__).resolve().parents[1] / ".env"

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


def rpc_url() -> str:
    """$RH_RPC, else RPC_MAINNET from ../.env, else the public endpoint.

    The public endpoint is enough for everything here; the .env lookup exists for the private
    tree, and the script must still run for someone who cloned only the public repository.
    """
    if os.environ.get("RH_RPC"):
        return os.environ["RH_RPC"]
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("RPC_MAINNET="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return PUBLIC_RPC


def rpc(url: str, method: str, params: list, timeout: int = 45, tries: int = 4):
    """Returns (result, error). Rate limits are retried; everything else is reported."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    last = None
    for attempt in range(tries):
        # The public RPC sits behind Cloudflare and answers 403 "error code: 1010" to
        # urllib's default User-Agent; any explicit UA is accepted.
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "read-accrual-index/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in (429, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            return None, last
        except Exception as exc:                      # noqa: BLE001
            last = type(exc).__name__ + ": " + str(exc)[:120]
            time.sleep(1.0 * (attempt + 1))
            continue
        if "error" in payload:
            msg = str(payload["error"])[:200]
            if "429" in msg or "Too Many Requests" in msg or "rate" in msg.lower():
                last = msg
                time.sleep(1.5 * (attempt + 1))
                continue
            return None, msg
        return payload.get("result"), None
    return None, (last or "unknown error")


def words(data_hex: str) -> list[str]:
    d = data_hex[2:]
    return [d[i:i + 64] for i in range(0, len(d) - len(d) % 64, 64)]


def as_float(word: str) -> float:
    return int(word, 16) / SCALE


def ratio_report(sym: str, logs: list[dict]) -> None:
    """The index is the ratio of the two words in each log: w1 / w0.

    MEASURED 2026-09-28: for SPY the ratio is 1.001717991 and for TSLA exactly 1 -- and it is
    the *ratio*, not a stored word, so nothing in the log is an index by itself. This prints
    how constant that ratio is inside the window: an index is constant between accrual events
    while the amounts themselves vary with every trade.
    """
    from decimal import Decimal, getcontext
    from fractions import Fraction
    getcontext().prec = 40

    pairs = []
    zero = 0
    for lg in logs:
        w = words(lg["data"])
        if len(w) != 2:
            continue
        a, b = int(w[0], 16), int(w[1], 16)
        if a == 0:
            zero += 1
            continue
        pairs.append((Fraction(b, a), int(lg["blockNumber"], 16)))
    if not pairs:
        print(f"    ratio: no usable (non-zero) pair in {len(logs)} logs")
        return
    lo = min(pairs, key=lambda p: p[0])
    hi = max(pairs, key=lambda p: p[0])
    uniq = len({p[0] for p in pairs})
    d = lambda f: Decimal(f.numerator) / Decimal(f.denominator)      # noqa: E731
    first, last = pairs[0], pairs[-1]
    print(f"    ratio w1/w0 over {len(pairs)} logs ({zero} zero-amount logs dropped):")
    print(f"      distinct values  {uniq}")
    print(f"      min {d(lo[0]):.18f}  at block {lo[1]:,}")
    print(f"      max {d(hi[0]):.18f}  at block {hi[1]:,}")
    print(f"      first {d(first[0]):.18f}  last {d(last[0]):.18f}"
          f"  {'(CONSTANT)' if uniq == 1 else '(VARIES in window)'}")
    if uniq > 1:
        span = d(hi[0]) - d(lo[0])
        print(f"      spread {span:.18f}")


def count_transfers(url: str, addr: str, lo: int, hi: int):
    logs, err = rpc(url, "eth_getLogs", [{"address": addr, "topics": [TRANSFER_TOPIC],
                                          "fromBlock": hex(lo), "toBlock": hex(hi)}])
    if err:
        return None, err
    return len(logs), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=20_000)
    ap.add_argument("--assets", default=",".join(STOCKS))
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--ratio", action="store_true", default=True)
    ap.add_argument("--no-ratio", dest="ratio", action="store_false")
    ap.add_argument("--transfer-count", action="store_true",
                    help="also count ERC-20 Transfer logs in the same window (1:1 check)")
    args = ap.parse_args()

    url = rpc_url()
    head_r, err = rpc(url, "eth_blockNumber", [])
    if err:
        print("FATAL eth_blockNumber:", err)
        return 2
    head = int(head_r, 16)
    # 🔴 This line used to convert blocks to days at "~267k blocks/day" and was wrong by 3.2x: that
    # figure came from reading block 69,196,861 as the start of the 2026-09-04 series, when it is
    # the END of a backfill (2026-09-21ish). Measured over 2026-09-01 00:00Z -> 2026-09-29 11:58Z
    # (blocks 51,274,668 -> 75,638,069) this chain produces about 855,000 blocks/day, ~9.9/s.
    # It is the same class as error 6 in the archive: a block count is not a duration until
    # someone converts it, and the conversion is a measurement, not a memory.
    print(f"head {head:,}  window {args.blocks:,} blocks "
          f"(~{args.blocks / 855_000 * 24:.1f} h at the measured ~855k blocks/day)")

    failures: list[str] = []
    for sym in [s.strip().upper() for s in args.assets.split(",") if s.strip()]:
        addr = STOCKS.get(sym)
        if not addr:
            failures.append(f"{sym}: unknown symbol")
            continue
        lo, hi = max(0, head - args.blocks), head
        logs, err = rpc(url, "eth_getLogs", [{"address": addr, "topics": [TOPIC0],
                                             "fromBlock": hex(lo), "toBlock": hex(hi)}])
        if err:
            failures.append(f"{sym}: eth_getLogs {lo}-{hi} FAILED: {err}")
            continue
        if not logs:
            failures.append(f"{sym}: no index log in {lo}-{hi} (window too short, "
                            f"or the token did not transfer) -- widen --blocks")
            continue

        shapes: dict[int, list[dict]] = {}
        for lg in logs:
            shapes.setdefault(len(words(lg["data"])), []).append(lg)

        print(f"\n{sym}  {addr}  {len(logs)} logs in {lo:,}-{hi:,}")
        for nwords, group in sorted(shapes.items(), key=lambda kv: -len(kv[1])):
            tail = group[-1]
            block = int(tail["blockNumber"], 16)
            print(f"  layout {nwords} words x{len(group)}"
                  f"   last at block {block:,}")
            cols = [words(lg["data"]) for lg in group]
            for i in range(nwords):
                values = {c[i] for c in cols}
                v = as_float(cols[-1][i])
                flag = ""
                if 1.0 <= v <= 1.01 and len(values) == 1:
                    flag = "  <-- index candidate (constant in window, in [1,1.01])"
                elif 1.0 <= v <= 1.01:
                    flag = f"  (in [1,1.01], {len(values)} distinct)"
                print(f"    w{i:<2} distinct={len(values):<6} last={v:.18f}{flag}")
            for lg in group[-args.samples:] if args.samples else []:
                print(f"    sample block {int(lg['blockNumber'], 16):,} "
                      f"tx {lg['transactionHash']}")
                for i, w in enumerate(words(lg["data"])):
                    print(f"      w{i:<2} {w}  {as_float(w):.18f}")

        if args.ratio:
            ratio_report(sym, logs)
        if args.transfer_count:
            n, err = count_transfers(url, addr, lo, hi)
            if err:
                failures.append(f"{sym}: Transfer-log count FAILED: {err}")
            else:
                print(f"    ERC-20 Transfer logs in the same window: {n}  "
                      f"(index logs: {len(logs)})")

    if failures:
        print("\nFAILURES / GAPS (not skipped):")
        for f in failures:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
