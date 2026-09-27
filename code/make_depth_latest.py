#!/usr/bin/env python3
"""Build depth-latest.json: the newest published round of rhdepth-oneside-v1, as one file.

    python3 code/make_depth_latest.py            # write depth-latest.json
    python3 code/make_depth_latest.py --check    # rebuild and compare; exit 1 if it differs

Why this file exists. The series is published as one gzipped file of quote rows per day,
which is the right shape for an archive and the wrong shape for someone who wants today's
number. This is the second shape. It adds no measurement: every figure here is derived
from `data-oneside/<day>/quotes.jsonl.gz`, and `--check` runs in CI, so the published file
is provably what this code produces from the published rows. If they ever disagree, CI
fails rather than the file quietly becoming its own source.

🔴 The winner of a cell is a DERIVED quantity and is not stored in the series --
   registered that way in PREREG-oneside-depth-2026-09-25, because two written copies of
   one fact drift. This file is a derivation, not a second copy: it carries the code that
   produced it and a check that re-runs it. That distinction is the whole reason `--check`
   exists, and removing the check would turn this file into the second copy.

🔴 It is built from the PUBLISHED tree, never from the collector's working directory.
   A convenience file that points at a round nobody can download is worse than none.

🔴 "latest" means the newest round in the published series, and the series is published
   once a day for whole days only. So this file lags -- it is between about 7 and 31 hours
   behind the chain, depending on when you read it. The file states its own block and
   timestamp so a reader can compute that rather than trust an adjective; `staleness` says
   the same thing in words. This paragraph exists because a page in this repository once
   claimed "regenerated daily" while being generated before the day's sync.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import sys
from datetime import datetime, timezone

OUT = "depth-latest.json"
SIZES = [100, 1_000, 10_000, 100_000]

# The stable half of the citation block: what a reader should quote. These values change
# only when the registration changes, which is what makes them quotable -- a citation that
# embeds today's block number is a citation of one reading, and fifty of them do not add up.
STABLE = {
    "series": "rhdepth-oneside-v1",
    "registered": "2026-09-25",
    "forward_window_opened": "2026-09-26T00:00:00Z",
    "method": [
        "PREREG-oneside-depth-2026-09-25.md",
        "PREREG-oneside-depth-2026-09-25-addendum.md",
        "PREREG-oneside-depth-2026-09-25-addendum-2.md",
        "PREREG-oneside-depth-2026-09-25-addendum-3.md",
        "PREREG-oneside-depth-2026-09-25-addendum-4.md",
    ],
    "source": "https://github.com/dirkdiggler1026/executability-report",
    "chain": {"name": "Robinhood Chain", "chainId": 4663},
    # 🔴 Say what is anchored and what is not. The EvidenceLedger holds rhdepth-v2.
    #    This series is NOT anchored: every one of its blocks sits above the ledger's
    #    watermark (69,196,861), which only moves forward, so none of its rounds can be
    #    committed. Claiming the anchor covers this series would be the easiest and
    #    worst sentence in this file.
    "anchor": {
        "contract": "0x7f5446b920e09531f443ce951076cbaed09dfab6",
        "chainId": 4663,
        "anchors_series": "rhdepth-v2",
        "anchors_this_series": False,
        "note": ("The ledger's watermark is 69,196,861 and only moves forward; every block "
                 "in rhdepth-oneside-v1 is above it, so no round of this series is "
                 "committed on chain. Its integrity rests on the published checksums and "
                 "on git history, not on the ledger."),
    },
}


def rows_of(path):
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def build() -> dict:
    days = sorted(glob.glob("data-oneside/20??-??-??"))
    if not days:
        raise SystemExit("FAIL: no published day of data-oneside/")
    last_day = days[-1]
    rounds = [json.loads(l) for l in open(os.path.join(last_day, "rounds.jsonl")) if l.strip()]
    if not rounds:
        raise SystemExit(f"FAIL: {last_day}/rounds.jsonl is empty")
    rnd = rounds[-1]
    block = rnd["block"]

    rows = [r for r in rows_of(os.path.join(last_day, "quotes.jsonl.gz"))
            if r["block"] == block]
    if not rows:
        raise SystemExit(f"FAIL: no quote rows at block {block}")

    assets: dict[str, dict] = {}
    for r in rows:
        a = assets.setdefault(r["asset"], {
            "reference_mid_usd_per_share": r["reference_mid_usd_per_share"],
            "rungs": {},
        })
        # argmax over absolute proceeds for an identical share count -- registered in
        # addendum 2 section 1. A partial fill sells fewer shares and so loses the cell,
        # and the remainder is not routed anywhere else, which makes the winner a LOWER
        # BOUND on realisable proceeds rather than an optimal route.
        cur = a["rungs"].get(r["size_usd"])
        if cur is None or r["amount_out_usd"] > cur["_out"]:
            a["rungs"][r["size_usd"]] = {"_out": r["amount_out_usd"], "_r": r}

    out_assets = {}
    for name in sorted(assets):
        a = assets[name]
        ladder = []
        for s in SIZES:
            cell = a["rungs"].get(s)
            if cell is None:
                ladder.append({"size_usd": s, "status": "not measured"})
                continue
            r = cell["_r"]
            consumed = int(r["shares_consumed_raw"])
            offered = int(r["shares_offered_raw"])
            own_base = (consumed / 1e18) * r["pool_mid_usd_per_share"]
            ladder.append({
                "size_usd": s,
                "proceeds_usd": r["amount_out_usd"],
                # addendum 1: renamed from "one-sided loss". It CAN be negative -- that is
                # cross-pool price dispersion, not a profit. The spread across the ladder
                # is the depth reading; the level carries a dispersion offset.
                "shortfall_vs_median_notional_pct": 100.0 * (1 - r["amount_out_usd"] / s),
                # addendum 1 section 4: non-negative by construction.
                "own_mid_slippage_pct": (100.0 * (1 - r["amount_out_usd"] / own_base)
                                         if own_base > 0 else None),
                "pool": r["pool"],
                "quote": r["quote"],
                "fee_at_block": r["pool_fee_at_block"],
                "pool_mid_usd_per_share": r["pool_mid_usd_per_share"],
                "shares_offered_raw": r["shares_offered_raw"],
                "shares_consumed_raw": r["shares_consumed_raw"],
                "filled_fraction": (consumed / offered) if offered else None,
                "status": r["status"],
            })
        out_assets[name] = {
            "reference_mid_usd_per_share": a["reference_mid_usd_per_share"],
            "rungs": ladder,
        }

    src = rnd.get("pools_source") or {}
    return {
        "_read_this_first": (
            "Every number here is derived from data-oneside/{}/quotes.jsonl.gz by "
            "code/make_depth_latest.py. Nothing here is a new measurement, and the winner "
            "of each rung is derived rather than stored -- CI re-runs the derivation and "
            "fails if this file does not match it.".format(os.path.basename(last_day))),
        "citation": STABLE,
        "as_of": {
            "block": block,
            "block_hash": rnd["block_hash"],
            "round_utc": rnd["ts_utc"],
            "roundKeccak": rnd["roundKeccak"],
            "published_day": os.path.basename(last_day),
            "verify": f"python3 code/verify.py {block}",
            "staleness": ("Whole days only, published once a day at 06:01 UTC, so this is "
                          "between about 7 and 31 hours behind the chain. Compare round_utc "
                          "to now rather than relying on the file name."),
        },
        "statistic": {
            "what": ("For each asset and each notional rung, the sale is quoted into every "
                     "enumerated pool at one pinned block and the cell is won by the largest "
                     "absolute USD proceeds for an identical share count. One side of the "
                     "trade -- the sell -- because a forced seller walks one side."),
            "shortfall_vs_median_notional_pct": (
                "1 - proceeds / (shares x median pool mid). Can be negative when the "
                "best-paying pool is priced above the median of the enumerated pools; that "
                "is dispersion, not profit. The spread across the ladder is the depth "
                "reading, the level carries the dispersion offset (addendum 1)."),
            "own_mid_slippage_pct": (
                "1 - proceeds / (shares consumed x that pool's own mid). Non-negative by "
                "construction (addendum 1 section 4)."),
            "winner_is_a_lower_bound": (
                "A pool that fills only part of the order loses the cell on total proceeds, "
                "and the remainder is not routed elsewhere. So the winner is a lower bound "
                "on realisable proceeds, not an optimal route (addendum 2 section 1)."),
            "venue_list_not_claimed_complete": (
                "Venues are found by enumerating each token's Transfer counterparty flow, "
                "ranked per asset and capped. The cap and the unclassified count are "
                "recorded in the enumeration, not hidden (addendum 2 section 2.1)."),
        },
        "venue_list": {
            "enumerated_at_block": src.get("enumerated_at_block"),
            "age_blocks": src.get("age_blocks"),
            "method": src.get("method"),
            "present_not_quoted": src.get("present_not_quoted"),
            "unclassified": src.get("unclassified"),
            "archive": ("data-oneside/enumerations/pools-{}.json"
                        .format(src.get("enumerated_at_block"))),
        },
        "quote_rows_in_round": rnd.get("quote_rows"),
        "cells": rnd.get("cells"),
        "assets": out_assets,
    }


def main() -> int:
    if not os.path.isdir("data-oneside"):
        print("FAIL: run from the repository root", file=sys.stderr)
        return 1
    built = build()
    text = json.dumps(built, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    if "--check" in sys.argv:
        if not os.path.exists(OUT):
            print(f"FAIL: {OUT} is missing", file=sys.stderr)
            return 1
        have = open(OUT, encoding="utf-8").read()
        if have != text:
            print(f"FAIL: {OUT} is not what code/make_depth_latest.py produces from the "
                  f"published rows", file=sys.stderr)
            return 1
        print(f"  ok -- {OUT} matches the published rows "
              f"(block {built['as_of']['block']:,})")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"  wrote {OUT}: block {built['as_of']['block']:,} · "
          f"{built['cells']} cells · {len(built['assets'])} assets · "
          f"{os.path.getsize(OUT):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
