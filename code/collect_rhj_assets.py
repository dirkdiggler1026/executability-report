#!/usr/bin/env python3
"""Snapshot the issuer's own public asset feed, for one question it can answer and we cannot.

    python3 collect_rhj_assets.py [--out DIR]

🔴 Why this exists, and why it started on 2026-09-29 rather than later.
   GET https://api.robinhood.com/rhj/assets returns, per asset, `currentMultiplier`
   and `pendingMultiplier`. On 2026-09-29 `currentMultiplier` matched uiMultiplier()
   on chain to the last digit for all nine assets we track, and `pendingMultiplier`
   was **empty for all 195 assets**. A field that announces the next value exists in
   the schema and carries nothing at that moment.

   Whether it is populated AHEAD of a change cannot be answered from one snapshot,
   and it cannot be answered afterwards either: the feed has no history and the
   issuer publishes none. It can only be answered by watching. Two dividend process
   dates are days away -- NVDA 2026-10-01 and QQQ 2026-10-08 -- so the window to
   observe it opens now and does not reopen.

   The same reason the whole project records rather than reconstructs.

Writes one file per run under <out>/<YYYY-MM-DD>/, append-only, no overwriting.
Records the HTTP status and the raw body length even on failure, so a gap in the
series is distinguishable from a quiet day.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

URL = "https://api.robinhood.com/rhj/assets"
CORP = "https://api.robinhood.com/rhj/corporate-actions"
DEV = "https://api.robinhood.com/rhj/price-deviations"
TRACKED = ("AAPL", "AMC", "GME", "GOOGL", "NVDA", "QQQ", "RDDT", "SPY", "TSLA")


def get(url):
    r = subprocess.run(["curl", "-sSL", "-m", "40", "-A", "Mozilla/5.0",
                        "-w", "\n%{http_code}", url], capture_output=True, timeout=70)
    body = r.stdout.decode("utf-8", "replace")
    code, body = (body.rsplit("\n", 1)[1], body.rsplit("\n", 1)[0]) if "\n" in body else ("?", body)
    return code, body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/root/predict-data/dexfeed_data/rhj_assets")
    a = ap.parse_args()
    now = time.gmtime()
    day = time.strftime("%Y-%m-%d", now)
    stamp = time.strftime("%Y-%m-%dT%H%M%SZ", now)
    d = os.path.join(a.out, day)
    os.makedirs(d, exist_ok=True)

    out = {"canon": "rhj-issuer-feed-v1",
           "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", now),
           "source": {"assets": URL, "corporate_actions": CORP, "price_deviations": DEV},
           "endpoints": {}}

    for name, url in (("assets", URL), ("corporate_actions", CORP),
                      ("price_deviations", DEV)):
        code, body = get(url)
        rec = {"http": code, "bytes": len(body),
               "sha256": hashlib.sha256(body.encode()).hexdigest()}
        try:
            rec["body"] = json.loads(body)
        except Exception as e:
            # 🔴 拿不到就明写拿不到，绝不写成空列表 —— 空列表读起来像"当天没有"
            rec["parse_error"] = repr(e)[:200]
            rec["raw_head"] = body[:400]
        out["endpoints"][name] = rec

    # 一个便于人读的摘要，原始 body 仍然全量保留在上面
    aj = out["endpoints"]["assets"].get("body") or {}
    rows = aj.get("assets") or []
    pend = [r["tokenSymbol"] for r in rows
            if r.get("pendingMultiplier") not in (None, "", "0")]
    out["summary"] = {
        "assets_total": len(rows),
        "pending_multiplier_nonempty": pend,
        "pending_multiplier_count": len(pend),
        "tracked": {r["tokenSymbol"]: {"current": r.get("currentMultiplier"),
                                       "pending": r.get("pendingMultiplier")}
                    for r in rows if r.get("tokenSymbol") in TRACKED},
    }
    p = os.path.join(d, f"rhj-{stamp}.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"  {p}  assets={len(rows)}  pending非空={len(pend)} {pend or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
