#!/usr/bin/env python3
"""Measure what a public endpoint still serves: state, and events, separately.

    python3 code/measure_retention.py --out-dir measurements/rh-retention
    python3 code/measure_retention.py --dry-run

Why this exists. Every issue of the weekly feed carried the sentence "no rolling provable
window exists on this chain". That is true of *state* and false of *events*: a state call a few
hundred thousand blocks back returns "historical state is not available", while a log query
over the same range returns hundreds of events. A reader pointed this out, which is the first
of this project's errors caught from outside it.

The lesson is narrower than "we were wrong": a retention claim has to name **which retention
class** it is about. State and events are pruned on different schedules, and a sentence about
the chain is almost always a sentence about one of them.

## What the second pass of this file fixed, which is the same mistake one level up

The first version answered "how deep are logs served" with the deepest rung of a ladder that
came back. On 2026-10-09 that was 20,000,000 blocks, because the 50,000,000 rung **timed out**
-- and the artifact's field was called `deepest_logs_served_blocks_back`, which reads as a
boundary. It was not one. The deeper rung timed out on an *unfiltered* query returning
hundreds of rows per 50 blocks, so the limit it found was the cost of the query. An
address-filtered query at a comparable depth answers in two tenths of a second, and logs for
an address are served down to block 0 on this endpoint.

So this version separates three things that the one number was mixing:

  **Proven.** A query that came back with at least one row. The node had those logs, at that
  depth, and that is the only positive retention claim made here.

  **Answered.** A query that returned without error, possibly empty. Weaker on purpose: a node
  that has dropped its log index can answer empty rather than erroring, so an empty answer is
  not evidence of retention. This is recorded under its own name so it cannot be read as the
  one above.

  **Refused, and why.** A timeout is a cost limit. A span error is a limit on how many blocks
  one query may cover, and the node names its own number, so that number is parsed from the
  refusal rather than hardcoded here. Neither is retention, and a rung that hits one is
  retried with a narrower span and a longer timeout before anything is concluded from it.

State gets the same treatment in the other direction: the old ladder started at 200,000 blocks
back, which was already pruned, so it bracketed nothing. This one starts shallow and reports
the bracket -- deepest served and shallowest pruned -- because "state is gone by N" and "state
survives to N" are different claims and the published sentence should be the one that was
measured.

## And it carries its own clock

The artifact records this chain's block time, measured over three spans in the same run. A
depth in blocks is the only thing an endpoint answers in, and converting it to hours needs a
block time -- which is where this project has already gone wrong once, by assuming two seconds
per block on a chain that produces one about every tenth of a second. A conversion is only as
good as its unit, so the unit ships with the measurement.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ZERO = "0x0000000000000000000000000000000000000000"
# Shallow enough at the top to bracket state retention rather than start past it.
# 🔴 Rungs between 5,000 and 20,000 exist because of what was already on record: an
#    addendum from September brackets state retention at 3,100-5,900 blocks, measured
#    2026-09-11 to 09-15. A ladder that jumps 5,000 -> 20,000 produces a wider bracket than
#    that and would read as a correction of it while being merely coarser. A later
#    measurement is only allowed to supersede an earlier one if it is at least as fine.
STATE_LADDER = [10, 50, 100, 500, 1_000, 2_000, 3_000, 4_000, 5_000, 6_000, 8_000, 10_000,
                15_000, 20_000, 50_000, 100_000, 200_000, 1_000_000]
# Kept comparable with the earlier series, which is why the old rungs are still here.
LOG_LADDER = [200_000, 1_000_000, 5_000_000, 20_000_000, 50_000_000]
# Escalation for a rung that times out: narrower span, longer patience. A rung is only
# reported as refused after the cheapest form of the question has also failed.
LOG_ATTEMPTS = ((50, 30), (5, 90), (1, 120))
# 🔴 This endpoint rate-limits. A 429 came back on six of eight state rungs the first time
#    this ladder ran and was filed as "error", which reads as the chain refusing to answer
#    when it was us asking too fast -- a self-inflicted absence, and the ladder bracketed
#    nothing. Every probe now backs off and retries, and a rung that never resolves is
#    reported as unresolved rather than as a verdict about the chain.
BACKOFF = (2, 5, 12)
PACE = 1.2
BLOCK_TIME_SPANS = [1_000, 100_000, 1_000_000]
# 🔴 The measurement this one would supersede, and the rule that it must not be coarser.
#    A later measurement is only allowed to replace an earlier one if its bracket is at
#    least as tight: a wider interval produced later reads as a correction while being
#    nothing but a coarser ladder, and it would retire a finer number. Declared here, with
#    its source, and enforced below -- this exits 1 rather than writing an artifact that
#    would quietly widen what is on record.
PRIOR_STATE_BRACKET = {
    "source": "PREREG-oneside-depth-2026-09-25-addendum-4.md",
    "measured": "2026-09-11 to 2026-09-15",
    "served_through_blocks_back": 3_100,
    "pruned_by_blocks_back": 5_900,
}
UA = {"content-type": "application/json", "user-agent": "executability-report/1.0"}
CAP_RE = re.compile(r"only\s+(\d+)\s+are allowed")
ROW_CAP_RE = re.compile(r"exceeds limit of\s+(\d+)")
RATE_RE = re.compile(r"\bhttp 429\b|too many requests|rate ?limit")
# An address with few logs, so the whole-chain query it is used in is refused for its block
# span rather than for the number of rows it would match. This is the expired Pendle market
# measured in measurements/pendle-market-logs/: 82 logs over the chain's whole history.
SPARSE_ADDRESS = "0x752057e7a63d0a7f15b740d41ef484fdec459ead"


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
    """Return (verdict, detail). A timeout is not an absence, and neither is a span error."""
    if "error" in resp:
        msg = str(resp["error"].get("message") or resp["error"].get("transport")
                  or resp["error"])
        low = msg.lower()
        # 🔴 Matched as a whole token, not as a substring. `"429" in low` classified a
        #    genuinely pruned rung as rate-limited, because the state root in the node's
        #    message -- "historical state 602f...3c429 is not available" -- happens to end in
        #    429. The rung was then dropped from the retention bracket, silently. Never
        #    substring-match a code against a message that carries an opaque identifier.
        if RATE_RE.search(low):
            return "rate_limited", msg
        if "timed out" in low or "timeout" in low:
            return "timeout", msg
        if "are allowed for this request" in low or "block range" in low:
            return "span_refused", msg
        if "exceeds limit" in low or "matched by query" in low:
            return "result_cap", msg
        if "not available" in low or "missing trie" in low or "pruned" in low:
            return "pruned", msg
        return "error", msg
    return "served", ""


def patient(url: str, method: str, params: list, timeout: int = 30) -> tuple[dict, int]:
    """One call, retried through this endpoint's rate limiter. Returns (response, attempts).
    Only a rate limit is retried: a timeout and a pruned state are answers."""
    for n, wait in enumerate((0,) + BACKOFF):
        if wait:
            time.sleep(wait)
        r = rpc(url, method, params, timeout)
        if classify(r)[0] != "rate_limited":
            return r, n + 1
    return r, len(BACKOFF) + 1


def block_time(url: str, head: int) -> dict:
    """Seconds per block, over several spans in one run. Three spans rather than one because
    a single span cannot show whether the figure is stable, and a block time that is only
    stable over one window is not a unit."""
    def ts(n: int):
        r, _ = patient(url, "eth_getBlockByNumber", [hex(n), False])
        if "result" not in r or not r["result"]:
            return None
        return int(r["result"]["timestamp"], 16)
    head_ts, spans = ts(head), []
    for span in BLOCK_TIME_SPANS:
        lo = head - span
        if lo < 1 or head_ts is None:
            continue
        lo_ts = ts(lo)
        if lo_ts is None:
            spans.append({"span_blocks": span, "seconds_per_block": None,
                          "detail": f"block {lo} would not read"})
            continue
        spans.append({"span_blocks": span, "elapsed_seconds": head_ts - lo_ts,
                      "seconds_per_block": round((head_ts - lo_ts) / span, 6)})
    got = [s["seconds_per_block"] for s in spans if s.get("seconds_per_block")]
    agree = bool(got) and (max(got) - min(got)) / max(got) < 0.05
    return {"spans": spans, "seconds_per_block": (sum(got) / len(got)) if got else None,
            "spans_agree_within_5pct": agree,
            "note": ("the mean of the spans above, which is only usable as a unit because "
                     "they agree; if spans_agree_within_5pct is false, no single block time "
                     "describes this chain over this window and a conversion to hours should "
                     "not be made from it")}


def probe_logs(url: str, block: int) -> dict:
    """One log rung, escalating. Returns the first attempt that answered, with all attempts."""
    attempts = []
    for span, timeout in LOG_ATTEMPTS:
        t0 = time.time()
        r, tries = patient(url, "eth_getLogs",
                           [{"fromBlock": hex(block), "toBlock": hex(block + span)}], timeout)
        v, d = classify(r)
        n = len(r.get("result") or []) if v == "served" else None
        attempts.append({"span_blocks": span, "timeout_s": timeout, "verdict": v,
                         "count": n, "elapsed_s": round(time.time() - t0, 2),
                         "rpc_tries": tries, "detail": d[:160]})
        if v == "served":
            break
        time.sleep(PACE)
    last = attempts[-1]
    return {"verdict": last["verdict"], "count": last["count"],
            "detail": last["detail"], "attempts": attempts,
            "escalated": len(attempts) > 1}


# ── drill on the classifier ──────────────────────────────────────────────────────────────
# Every arm is a message this endpoint has actually returned, and the arms must land in
# different buckets. The third one is why this drill exists: it is a pruned rung whose state
# root ends in 429, and a substring test for "429" filed it as our own rate limit and took it
# out of the retention bracket.
CLASSIFY_ARMS = (
    ({"result": "0x0"}, "served"),
    ({"error": {"transport": "HTTP 429"}}, "rate_limited"),
    ({"error": {"message": "historical state 602f3b495c6ccb49e5e7c9ee23b5142d36d5a32640133"
                           "65e719a601d8bb3c429 is not available"}}, "pruned"),
    ({"error": {"message": "log query timed out"}}, "timeout"),
    ({"error": {"message": "query spans 85128115 blocks (0 to 85128114), but only 10000000 "
                           "are allowed for this request; narrow the block range"}},
     "span_refused"),
    ({"error": {"message": "logs matched by query exceeds limit of 10000"}}, "result_cap"),
    ({"error": {"message": "something nobody has seen before"}}, "error"),
)


def selftest() -> int:
    bad, seen = [], {}
    for resp, want in CLASSIFY_ARMS:
        got = classify(resp)[0]
        seen.setdefault(got, []).append(want)
        mark = "ok " if got == want else "FAIL"
        print(f"  {mark} want {want:<13} got {got:<13} "
              f"{str(resp)[:72]}")
        if got != want:
            bad.append(f"{want} -> {got}")
    if len(seen) != len({w for _, w in CLASSIFY_ARMS}):
        bad.append(f"the arms do not land in distinct buckets: {seen}")
    if bad:
        print("\nselftest FAILED", file=sys.stderr)
        for b in bad:
            print(f"  {b}", file=sys.stderr)
        return 1
    print(f"\nselftest: passed -- {len(CLASSIFY_ARMS)} arms, "
          f"{len(seen)} distinct verdicts, so the classifier discriminates")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://rpc.mainnet.chain.robinhood.com")
    ap.add_argument("--chain", default="robinhood-4663")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tag", default="", help="keep this run under its own name instead of "
                                              "overwriting the day's file")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    h = rpc(a.url, "eth_blockNumber", [])
    if "result" not in h:
        print(f"could not read head: {json.dumps(h)[:160]}", file=sys.stderr)
        return 3
    head = int(h["result"], 16)
    print(f"head {head:,}")

    bt = block_time(a.url, head)
    print(f"  block time {bt['seconds_per_block']} s/block over "
          f"{[s['span_blocks'] for s in bt['spans']]} "
          f"({'agree' if bt['spans_agree_within_5pct'] else 'DO NOT AGREE'})")

    # 🔴 Two different limits, and the first pass of this file conflated them. An
    #    address-filtered query over the whole chain is refused for its *block span*; an
    #    unfiltered one is refused earlier for the number of rows it would *match*. Both are
    #    limits on the query and neither is retention, so each gets its own probe, its own
    #    regex and its own field -- and a null with the node's words beside it if the number
    #    cannot be parsed, never a hardcoded fallback.
    sp, _ = patient(a.url, "eth_getLogs",
                    [{"address": SPARSE_ADDRESS, "fromBlock": "0x0", "toBlock": hex(head)}], 60)
    span_v, span_d = classify(sp)
    m = CAP_RE.search(span_d)
    span_cap = int(m.group(1)) if m else None
    rc, _ = patient(a.url, "eth_getLogs", [{"fromBlock": "0x0", "toBlock": hex(head)}], 60)
    res_v, res_d = classify(rc)
    m2 = ROW_CAP_RE.search(res_d)
    row_cap = int(m2.group(1)) if m2 else None
    print(f"  span cap {span_cap if span_cap else 'not stated'} blocks ({span_v}) · "
          f"row cap {row_cap if row_cap else 'not stated'} rows ({res_v})")

    state_rows, log_rows = [], []
    for back in STATE_LADDER:
        b = max(1, head - back)
        r, tries = patient(a.url, "eth_getBalance", [ZERO, hex(b)])
        v, d = classify(r)
        state_rows.append({"blocks_back": back, "block": b, "verdict": v,
                           "rpc_tries": tries, "detail": d[:160]})
        print(f"  state  back {back:>12,}  block {b:>12,}  {v}"
              f"{'' if tries == 1 else f'  [{tries} tries]'}")
        time.sleep(PACE)
    for back in LOG_LADDER:
        b = max(1, head - back)
        r = probe_logs(a.url, b)
        log_rows.append({"blocks_back": back, "block": b, **r})
        rows_txt = "" if r["count"] is None else f" ({r['count']} rows)"
        print(f"  logs   back {back:>12,}  block {b:>12,}  {r['verdict']}{rows_txt}"
              f"{'  [escalated]' if r['escalated'] else ''}")
        time.sleep(PACE)

    unresolved = [{"kind": "state", "blocks_back": r["blocks_back"], "verdict": r["verdict"],
                   "detail": r["detail"]} for r in state_rows
                  if r["verdict"] in ("rate_limited", "error")]
    unresolved += [{"kind": "logs", "blocks_back": r["blocks_back"], "verdict": r["verdict"],
                    "detail": r["detail"]} for r in log_rows
                   if r["verdict"] in ("rate_limited", "error")]
    # 🔴 The head moves while the ladder runs, and every rung is computed from the single
    #    head read at the start. So a rung probed late in the run sits deeper than its label
    #    by however far the chain advanced -- which matters exactly at the bracket, where the
    #    rungs are a couple of thousand blocks apart. Recorded rather than corrected for:
    #    correcting it would need a per-rung head read, and the drift is the honest width.
    h2 = rpc(a.url, "eth_blockNumber", [])
    head_after = int(h2["result"], 16) if "result" in h2 else None
    drift = (head_after - head) if head_after else None
    print(f"  head drift during the run: {drift if drift is not None else 'unread'} blocks")

    served_state = [r["blocks_back"] for r in state_rows if r["verdict"] == "served"]
    pruned_state = [r["blocks_back"] for r in state_rows if r["verdict"] == "pruned"]
    proven_logs = [r["blocks_back"] for r in log_rows
                   if r["verdict"] == "served" and (r["count"] or 0) >= 1]
    answered_logs = [r["blocks_back"] for r in log_rows if r["verdict"] == "served"]
    refused_logs = [{"blocks_back": r["blocks_back"], "verdict": r["verdict"],
                     "detail": r["detail"]} for r in log_rows if r["verdict"] != "served"]

    def hours(blocks):
        spb = bt["seconds_per_block"]
        if blocks is None or not spb or not bt["spans_agree_within_5pct"]:
            return None
        return round(blocks * spb / 3600, 3)

    deepest_state = max(served_state) if served_state else None
    shallowest_pruned = min(pruned_state) if pruned_state else None

    # The rule, applied. Width is the only thing compared: where the bracket sits may move
    # for real reasons -- pruning is a node's housekeeping schedule -- but how tightly it is
    # pinned is a property of the ladder, and that may only improve.
    prior = PRIOR_STATE_BRACKET
    prior_width = prior["pruned_by_blocks_back"] - prior["served_through_blocks_back"]
    our_width = (shallowest_pruned - deepest_state
                 if (deepest_state is not None and shallowest_pruned is not None) else None)
    resolution = {
        "prior": prior, "prior_bracket_width_blocks": prior_width,
        "this_bracket_width_blocks": our_width,
        "at_least_as_fine_as_prior": (our_width is not None and our_width <= prior_width),
        "rule": ("a later measurement may only supersede an earlier one if its bracket is at "
                 "least as tight. Where the bracket sits may move for real reasons; how "
                 "tightly it is pinned is a property of the ladder and may only improve. "
                 "measure_retention.py exits 1 rather than write an artifact that violates "
                 "this, because a wider interval produced later reads as a correction while "
                 "being merely a coarser ladder."),
    }
    if our_width is None or our_width > prior_width:
        print(f"REFUSED: this ladder brackets state at "
              f"{deepest_state}..{shallowest_pruned} blocks back (width "
              f"{our_width}), and {prior['source']} already brackets it at "
              f"{prior['served_through_blocks_back']}..{prior['pruned_by_blocks_back']} "
              f"(width {prior_width}). A later measurement may not be coarser than the one "
              f"it would supersede -- add rungs between the two that bracket, then re-run. "
              f"Nothing was written.", file=sys.stderr)
        return 1
    rec = {
        "chain": a.chain,
        "endpoint": a.url,
        "head_at_measurement": head,
        "head_after_measurement": head_after,
        "head_drift_blocks_during_run": drift,
        "head_drift_note": ("every rung's block number is head_at_measurement minus its "
                            "label, so a rung probed late in the run is deeper than its "
                            "label by up to this drift. At the state bracket the rungs are "
                            "2,000 blocks apart, so a drift of this size is a real part of "
                            "the bracket's width and is not corrected for here."),
        "measured_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        # 🔴 The filename carries only the date, so a second run on the same day overwrites
        #    the first -- the same collision that overwrote an archive once before, when two
        #    runs keyed on a block hash. Here the overwrite is the intended behaviour (one
        #    current measurement per day), so the convention is written down instead of being
        #    left to be discovered, and the full timestamp distinguishes runs in git history.
        #    --tag keeps a run under its own name when a run is worth keeping beside another.
        "measured_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_naming_note": ("this file is named by date only, so it is the LAST run of that "
                             "date; earlier runs of the same date were overwritten and are "
                             "not retained. measured_at_utc says which run this is. Pass "
                             "--tag to keep a run under its own name instead."),
        "state_bracket_resolution": resolution,
        "method": ("one eth_getBalance of the zero address at (head - N) for each N in the "
                   "state ladder; one eth_getLogs over a small span at (head - N) for each N "
                   "in the log ladder, escalated to a narrower span and a longer timeout if "
                   "it does not answer. A timeout is recorded as a timeout, a span refusal as "
                   "a span refusal, and neither as an absence. The log queries carry no "
                   "address filter, so their cost grows with how busy the chain was"),
        "block_time": bt,
        "logs_query_span_cap_blocks": span_cap,
        "logs_query_span_cap_evidence": span_d[:200] or f"verdict {span_v}",
        "logs_query_row_cap": row_cap,
        "logs_query_row_cap_evidence": res_d[:200] or f"verdict {res_v}",
        "query_limits_note": ("two separate limits, measured separately because the first "
                              "version of this probe hit whichever came first and reported "
                              "one number: a cap on how many blocks one query may span, and "
                              "a cap on how many rows one query may match. Neither is a "
                              "statement about retention."),
        "unresolved_rungs": unresolved,
        "unresolved_note": ("a rung here never got an answer from the chain -- a rate limit "
                            "that survived the backoff, or an error this file does not "
                            "recognise. It is excluded from every bracket and every claim "
                            "below. The first run of this ladder filed rate limits as "
                            "errors and the brackets were computed over them, which made our "
                            "own request rate look like the chain's retention."),
        "state_ladder": state_rows,
        "log_ladder": log_rows,

        "state_served_at_deepest_blocks_back": deepest_state,
        "state_served_at_deepest_hours": hours(deepest_state),
        "state_pruned_at_shallowest_blocks_back": shallowest_pruned,
        "state_pruned_at_shallowest_hours": hours(shallowest_pruned),
        "state_retention_prior_measurement":
            ("PREREG-oneside-depth-2026-09-25-addendum-4.md records 3,100-5,900 blocks, "
             "measured 2026-09-11 to 09-15. This ladder is spaced to be comparable with "
             "that rather than coarser than it. State pruning is a node's housekeeping "
             "schedule, so the two brackets differing is not by itself an error in either; "
             "what would be an error is letting a coarser ladder read as a correction."),
        "state_retention_bracket_note":
            ("state retention lies between state_served_at_deepest_blocks_back and "
             "state_pruned_at_shallowest_blocks_back. Either bound may be null: null for the "
             "served bound means even the shallowest rung was already pruned and this ladder "
             "brackets nothing from below, which is what the first version of this probe did "
             "without saying so."),

        "logs_proven_at_deepest_blocks_back": max(proven_logs) if proven_logs else None,
        "logs_proven_at_deepest_hours": hours(max(proven_logs) if proven_logs else None),
        "logs_answered_at_deepest_blocks_back": max(answered_logs) if answered_logs else None,
        "logs_refused": refused_logs,
        "logs_claim_note":
            ("logs_proven_at_deepest_blocks_back is the deepest rung that came back with at "
             "least one row: the node had those logs at that depth, and it is the only "
             "positive retention claim in this file. logs_answered_at_deepest_blocks_back "
             "counts a query that returned without error even if it returned nothing, and is "
             "NOT evidence of retention -- a node that has dropped its log index can answer "
             "empty rather than erroring. A rung in logs_refused hit a timeout or a span "
             "limit after escalation; both are limits on the query and neither is a statement "
             "about retention. An earlier artifact reported the deepest answered rung under a "
             "name that read as a boundary, and the rung below it had merely timed out on an "
             "unfiltered query; an address-filtered query at a comparable depth answers "
             "immediately."),
        "note": ("state and events are pruned on different schedules on this endpoint, so a "
                 "retention claim has to name which of the two it is about. Where events are "
                 "served, realised execution is publicly recheckable; where state is not, a "
                 "counterfactual figure at a past block can only be rechecked against an "
                 "archive kept at the time, which is why this project archives its reads."),
    }
    if a.dry_run:
        print(json.dumps({k: v for k, v in rec.items()
                          if k not in ("state_ladder", "log_ladder")}, indent=2)[:2200])
        return 0
    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    tag = f"-{a.tag}" if a.tag else ""
    path = os.path.join(out, f"retention-{rec['measured_utc']}{tag}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
