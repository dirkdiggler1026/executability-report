#!/usr/bin/env python3
"""How long a Chainlink feed on Robinhood Chain went without publishing, from events.

Why events and not state. The public endpoint on this chain prunes state within roughly
ten to fourteen minutes (measured by code/measure_retention.py, recorded in
measurements/rh-retention/), so latestRoundData() cannot answer a question about a day
in the past. AnswerUpdated logs are a different retention class on the same endpoint and
are served tens of millions of blocks back, measured by rows actually returned. A figure
can therefore be computable at the head and still not be verifiable later, and only the
second property survives into an archive. This script is the second kind.

What it establishes: the wall-clock interval between consecutive published answers for
one feed, as recorded by the chain's own logs, at a block range a reader can re-query.

What it does not establish:
  - that any position was unliquidatable, or that anything was or was not liquidated.
    A feed that has not moved is an input to a decision, not the decision.
  - that the published answer was wrong. Only that it did not change.
  - anything about a feed it did not query. Two of the tokens priced on this chain have
    no feed on it at all; for those this exits NOT_EXERCISED, because the absence of a
    feed and a feed with no gap are different facts and must not share an exit code.
  - that the gap was the feed's fault rather than the chain's. That is what the
    sequencer control below is for, and it is reported, not assumed.

Three controls, each for a way this number can be wrong:

  contiguous roundIds   A log query can return fewer rows than exist: this endpoint caps
                        a response at ten thousand matched rows and a span at ten million
                        blocks. Both refusals are errors rather than short answers, but a
                        chunking mistake would be silent. An interval measured across a
                        hole in the data is a fabrication, so the recovered roundIds must
                        form an unbroken run or this exits NOT_EXERCISED.

  window edge           A statistic taken BETWEEN returned rows cannot see a gap that
                        straddles the start of the window. Found by this script printing
                        a wrong number on 2026-10-23: for one feed the first returned row
                        was the instant every feed resumed, so the days of silence before
                        it fell outside the row set and the worst gap printed as the
                        smallest in the set when it was in fact the largest of any feed.
                        The window is therefore extended backwards until one update
                        precedes the requested start, the straddling gap is flagged, and
                        if no earlier update can be found this exits NOT_EXERCISED rather
                        than reporting the largest gap it happens to see.

  sequencer             A halt produces an identical-looking gap. The block rate across
                        the gap is measured and reported; a rate that does not rule a
                        halt out is said so in the record rather than quietly dropped.

Usage:
    python3 code/verify_feed_staleness.py --symbol AAPL \
        --from-utc 2026-09-04T12:00:00Z --to-utc 2026-09-08T12:00:00Z

Exit: 0 measured, 1 a check failed, 3 not exercised.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evm import keccak256, rpc                                      # noqa: E402

PASS, FAIL, NOT_EXERCISED = 0, 1, 3

# The directory behind Chainlink's docs page for this chain. The docs table itself is
# rendered client-side and cannot be scraped, so the data source it reads is used.
DIRECTORY = "https://reference-data-directory.vercel.app/feeds-robinhood-mainnet.json"
EVENT = b"AnswerUpdated(int256,uint256,uint256)"
CHUNK = 1_000_000          # well inside the endpoint's ten-million-block span cap
UA = {"user-agent": "executability-report/1.0"}


def gmt(stamp: str) -> int:
    return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))


def iso(epoch: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def header_ts(block: int):
    """Timestamp of a block header. Headers outlive state on this endpoint; that is the
    only reason a range in the past can be located at all."""
    res, err = rpc("eth_getBlockByNumber", [hex(block), False])
    if err or res is None:
        return None, err or {"message": "null header"}
    return int(res["timestamp"], 16), None


def block_at(target: int, hi: int):
    """Lowest block whose timestamp is at or after target."""
    lo = 1
    while lo < hi:
        mid = (lo + hi) // 2
        ts, err = header_ts(mid)
        if ts is None:
            return None, err
        if ts < target:
            lo = mid + 1
        else:
            hi = mid
    return lo, None


def logs(address: str, topic0: str, lo: int, hi: int):
    """Returns (rows, None) or (None, (lo, hi, err)).

    A refused read is not an empty range. Keeping those apart is the whole reason this
    returns an error rather than an empty list -- the opposite has produced a published
    wrong number in this project before.
    """
    got = []
    while lo <= hi:
        top = min(lo + CHUNK - 1, hi)
        res, err = rpc("eth_getLogs", [{"address": address, "topics": [topic0],
                                        "fromBlock": hex(lo), "toBlock": hex(top)}])
        if err:
            return None, (lo, top, err)
        got.extend(res or [])
        lo = top + 1
    return got, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--from-utc", required=True)
    ap.add_argument("--to-utc", required=True)
    ap.add_argument("--out-dir", default="measurements/rh-feed-staleness")
    ap.add_argument("--lookback-chunks", type=int, default=12,
                    help="how many CHUNK windows to search backwards for the last update "
                         "preceding --from-utc; see 'window edge' in the module docstring")
    a = ap.parse_args()

    topic0 = "0x" + keccak256(EVENT).hex()

    req = urllib.request.Request(DIRECTORY, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as fh:
        feeds = json.load(fh)
    match = [f for f in feeds
             if (f.get("name") or "").startswith("Robinhood %s " % a.symbol)]
    if not match:
        print("%s: no feed on this chain. Absence of a feed is not a feed without a gap."
              % a.symbol)
        return NOT_EXERCISED
    feed = match[0]
    # AnswerUpdated is emitted by the aggregator, not by the proxy a consumer calls.
    # Querying the proxy returns nothing, which would read as "no staleness".
    agg, proxy = feed["contractAddress"], feed["proxyAddress"]

    head, err = rpc("eth_blockNumber", [])
    if err:
        print("could not read the head: %s" % str(err)[:200]); return NOT_EXERCISED
    head = int(head, 16)

    b0, e0 = block_at(gmt(a.from_utc), head)
    b1, e1 = block_at(gmt(a.to_utc), head)
    if b0 is None or b1 is None:
        print("could not locate the range from headers: %s" % str(e0 or e1)[:200])
        return NOT_EXERCISED

    rows, err = logs(agg, topic0, b0, b1)
    if err:
        print("eth_getLogs refused %d-%d: %s" % (err[0], err[1], str(err[2])[:200]))
        return NOT_EXERCISED

    preceding, lo_edge = [], b0
    for _ in range(a.lookback_chunks):
        if preceding:
            break
        hi_edge = lo_edge - 1
        if hi_edge < 1:
            break
        lo_edge = max(1, hi_edge - CHUNK + 1)
        got, err = logs(agg, topic0, lo_edge, hi_edge)
        if err:
            print("eth_getLogs refused %d-%d looking back: %s"
                  % (err[0], err[1], str(err[2])[:200]))
            return NOT_EXERCISED
        preceding = got or []
    if not preceding:
        print("no update in the %d blocks before the window: a gap straddling the start "
              "would be invisible here, so this is not measurable"
              % (a.lookback_chunks * CHUNK))
        return NOT_EXERCISED

    upd = []
    for log in preceding + rows:
        upd.append({"block": int(log["blockNumber"], 16),
                    "roundId": int(log["topics"][2], 16),
                    "answer": int(log["topics"][1], 16) / 10 ** feed["decimals"],
                    "updatedAt": int(log["data"][2:][:64], 16)})
    upd.sort(key=lambda u: u["block"])
    if len(upd) < 2:
        print("fewer than two updates: nothing to measure"); return NOT_EXERCISED

    ids = [u["roundId"] for u in upd]
    if ids != list(range(ids[0], ids[0] + len(ids))):
        print("roundIds %d..%d over %d rows are not contiguous: an interval measured "
              "across a hole in the data would be a fabrication"
              % (ids[0], ids[-1], len(ids)))
        return NOT_EXERCISED

    worst, i = max((upd[k + 1]["updatedAt"] - upd[k]["updatedAt"], k)
                   for k in range(len(upd) - 1))
    t0, _ = header_ts(upd[i]["block"])
    t1, _ = header_ts(upd[i + 1]["block"])
    blocks = upd[i + 1]["block"] - upd[i]["block"]
    rate = blocks / (t1 - t0) if t0 and t1 and t1 > t0 else None

    out = {
        "canon": "rh-feed-staleness-v1",
        "measured_utc": iso(int(time.time())),
        "symbol": a.symbol,
        "feed_name": feed["name"],
        "aggregator": agg,
        "proxy": proxy,
        "directory_source": DIRECTORY,
        "documented_heartbeat_s": feed.get("heartbeat"),
        "requested_range": {"from_utc": a.from_utc, "to_utc": a.to_utc,
                            "from_block": b0, "to_block": b1},
        "lookback_blocks": a.lookback_chunks * CHUNK,
        "head_at_measurement": head,
        "blocks_back_at_measurement": head - upd[i]["block"],
        "updates_used": len(upd),
        "roundIds": {"first": ids[0], "last": ids[-1], "contiguous": True},
        "longest_gap": {
            "seconds": worst,
            "hours": round(worst / 3600.0, 2),
            "from_utc": iso(upd[i]["updatedAt"]),
            "to_utc": iso(upd[i + 1]["updatedAt"]),
            "from_round": upd[i]["roundId"],
            "to_round": upd[i + 1]["roundId"],
            "answer_held_throughout": upd[i]["answer"],
            "multiple_of_documented_heartbeat":
                round(worst / feed["heartbeat"], 2) if feed.get("heartbeat") else None,
            "spans_requested_window_start": upd[i]["block"] < b0 <= upd[i + 1]["block"],
        },
        "sequencer_control": {
            "blocks_between_the_two_updates": blocks,
            "seconds_between": (t1 - t0) if t0 and t1 else None,
            "blocks_per_second_mean": round(rate, 3) if rate else None,
            "verdict": ("the chain produced blocks throughout, so the gap is the feed's "
                        "and not a halt") if rate and rate > 5 else
                       "INCONCLUSIVE: the block rate does not rule a halt out",
        },
        "what_this_does_not_establish": [
            "that any position was unliquidatable, or that anything was liquidated",
            "that the published answer was wrong, only that it did not change",
            "anything about a feed this run did not query",
        ],
        "updates": upd,
    }

    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "staleness-%s-%s.json" % (a.symbol, a.from_utc[:10]))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    g = out["longest_gap"]
    print("%s: longest gap %.2f h (%s -> %s, rounds %d -> %d), held %s"
          % (a.symbol, g["hours"], g["from_utc"], g["to_utc"],
             g["from_round"], g["to_round"], g["answer_held_throughout"]))
    print("  %s x documented heartbeat; %d blocks back; roundIds contiguous%s"
          % (g["multiple_of_documented_heartbeat"], out["blocks_back_at_measurement"],
             "; gap straddles the window start" if g["spans_requested_window_start"] else ""))
    print("  control: %s" % out["sequencer_control"]["verdict"])
    print("  wrote %s" % path)
    return PASS


if __name__ == "__main__":
    sys.exit(main())
