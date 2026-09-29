#!/usr/bin/env python3
"""Call uiMultiplier() on each stock token, and check whether a change is announced.

    python3 read_ui_multiplier.py --out <file.json> [--at <block> ...]

Two questions, kept apart because they have different answers:

  1. Can the multiplier be READ?      Yes. uiMultiplier() (ERC-8056 Scaled UI Amount
     Extension), selector 0xa60bf13d, 1e18 fixed point, and readable at historical
     blocks against an archive endpoint.
  2. Is a CHANGE ANNOUNCED?           No event from the token accompanies it. This
     program scans the token's own logs across a window and reports what it emitted,
     so the answer is a count, not an assertion.

🔴 Why this file exists. This project published "no getter could be found" after probing
   names it had guessed -- index(), sharePrice(), pricePerShare() and six more -- without
   looking up the extension standard. Absence of the guesses was reported as absence of
   the thing. A search that can only fail is not evidence, and the fix is to call the
   documented function and print what comes back.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter

UI_MULTIPLIER = "0xa60bf13d"          # keccak("uiMultiplier()")[:4]

# 🔴 Two endpoints on purpose. Historical eth_call needs archive state, so it needs the key;
#    eth_getLogs on the keyed endpoint is capped at a 10-block range by its plan, and the
#    public endpoint has no such cap. Using the public one for the log scan also makes the
#    "is a change announced" half reproducible by anyone, with no account at all.
PUBLIC_RPC = "https://rpc.mainnet.chain.robinhood.com"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
COMPANION = "0x37e7f0db430edc9dd31bc66f25f8449353aa0818f503b906747dd8f286cd3802"

# 🔴 These are the addresses the published series already uses. Do NOT retype them from
#    memory: three of them were placeholders in the first draft of this file and would have
#    silently read nothing. Cross-check against the token table in the collector before
#    changing any line here.
TOKENS = {
    "AAPL":  "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
    "AMC":   "0x05a3d1cd21d0c88145e82600e62e7e496e0f222b",
    "GME":   "0x1b0e319c6a659f002271b69db8a7df2f911c153e",
    "GOOGL": "0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3",
    "NVDA":  "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
    "QQQ":   "0xd5f3879160bc7c32ebb4dc785f8a4f505888de68",
    "RDDT":  "0x05b37fb53a299a1b874a619e1c4c404d52c36f4c",
    "SPY":   "0x117cc2133c37b721f49de2a7a74833232b3b4c0c",
    "TSLA":  "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
}


def archive_url() -> str:
    for line in open("/etc/rhchain.env"):
        if line.startswith("RHCHAIN_RPC="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no RHCHAIN_RPC")


def rpc(url, method, params, tries=3):
    for i in range(tries):
        p = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        r = subprocess.run(["curl", "-sS", "-m", "60", "-X", "POST", "-H",
                            "content-type: application/json", "-d", json.dumps(p), url],
                           capture_output=True, timeout=90)
        try:
            j = json.loads(r.stdout.decode())
        except Exception:
            time.sleep(1.5 * (i + 1)); continue
        err = str((j.get("error") or {}).get("message", ""))
        if err and ("429" in err or "too many requests" in err.lower()):
            time.sleep(1.5 * (i + 1)); continue
        return j.get("result"), err[:160]
    return None, "retries exhausted"


def read_at(url, addr, blk):
    r, e = rpc(url, "eth_call", [{"to": addr, "data": UI_MULTIPLIER},
                                 blk if isinstance(blk, str) else hex(blk)])
    if not r or r == "0x":
        return None, e or "empty"
    return int(r, 16), ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--at", type=int, nargs="*", default=[],
                    help="extra historical blocks to read QQQ at")
    ap.add_argument("--event-scan", type=int, nargs=2, metavar=("LO", "HI"),
                    help="scan the QQQ token's own logs over [LO,HI]")
    a = ap.parse_args()
    url = archive_url()

    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "function": "uiMultiplier()", "selector": UI_MULTIPLIER,
           "standard": "ERC-8056 Scaled UI Amount Extension",
           "scale": "1e18 fixed point",
           "latest": {}, "historical": {}, "event_scan": None,
           "note": ("Read is not notification. The two sections below answer different "
                    "questions and the second one is the one that constrains a reader.")}

    for sym, addr in sorted(TOKENS.items()):
        v, e = read_at(url, addr, "latest")
        out["latest"][sym] = {"address": addr, "raw": v,
                              "value": (v / 1e18) if v is not None else None,
                              "error": e or None}
        print(f"  {sym:6} {addr}  {(v/1e18) if v is not None else '—'}  {e}")

    for blk in a.at:
        v, e = read_at(url, TOKENS["QQQ"], blk)
        out["historical"][str(blk)] = {"value": (v / 1e18) if v is not None else None,
                                       "error": e or None}
        print(f"  QQQ @ {blk:,}  {(v/1e18) if v is not None else '—'}  {e}")

    if a.event_scan:
        lo, hi = a.event_scan
        r, e = rpc(PUBLIC_RPC, "eth_getLogs", [{"address": TOKENS["QQQ"],
                                                "fromBlock": hex(lo), "toBlock": hex(hi)}])
        if r is None:
            out["event_scan"] = {"from": lo, "to": hi, "error": e}
            print(f"  event scan failed: {e}")
        else:
            c = Counter(l["topics"][0] for l in r if l.get("topics"))
            named = {TRANSFER: "Transfer", COMPANION: "companion-log"}
            out["event_scan"] = {
                "endpoint": "public (no key)",
                "from": lo, "to": hi, "total_logs": len(r),
                "by_topic0": {t: {"count": n, "known_as": named.get(t)}
                              for t, n in c.most_common()},
                "other_than_transfer": sum(n for t, n in c.items()
                                           if t not in (TRANSFER, COMPANION)),
                "reading": ("A multiplier change inside this window produced no event "
                            "from the token beyond transfers."
                            if all(t in (TRANSFER, COMPANION) for t in c) else
                            "Something else was emitted; decode before concluding."),
            }
            print(f"  event scan {lo:,}..{hi:,}: {len(r)} logs, "
                  f"{out['event_scan']['other_than_transfer']} beyond transfers")

    json.dump(out, open(a.out, "w"), indent=1)
    print(f"  wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
