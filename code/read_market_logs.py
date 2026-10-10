#!/usr/bin/env python3
"""Archive every event log a contract has emitted, and say exactly what the sweep covers.

    python3 code/read_market_logs.py --address 0x… --out-dir measurements/pendle-market-logs
    python3 code/read_market_logs.py --address 0x… --dry-run        # print, write nothing

Why this exists. The two Pendle PT markets on this chain are the only place in this project
where a *real* trade can be recovered: their state is gone minutes after it is written, so a
counterfactual quote can never be checked against what somebody actually paid unless the
trades themselves are held. Event logs are the only surviving record of those trades, so they
are captured as raw material now and interpreted later -- the same order as the state capture,
and for the same reason.

**It converts nothing.** The archive holds the responses as the node returned them: topics and
data as hex. Turning a log into an amount needs an ABI and a decimals convention, and both are
choices that belong in the analysis where they can be argued with, not in the archive where
they would be indistinguishable from what the chain said.

**What the sweep establishes, and what it does not.** This is the part that has to be written
down, because the honest reading is narrower than it looks:

  A range that returns logs proves the node still serves logs at that depth. That is a
  measurement, and it is the only retention claim this file makes.

  A range that returns *nothing* proves nothing. It is equally consistent with the contract
  not existing yet, with no events in that range, and with a node that has dropped its log
  index that far back and answers empty rather than erroring. Those three are not
  distinguished here and must not be reported as if they were. An earlier reading in this
  project treated one timeout as a retention boundary and was wrong by an order of magnitude;
  the rule that came out of it is that an absence is only evidence when the probe could have
  told the difference.

  The node caps how many blocks one query may span. That cap is not hardcoded here: the first
  read is a deliberately over-wide query whose refusal is archived, and the cap is parsed from
  the node's own answer. If it cannot be parsed, this exits 3 rather than guessing -- a guessed
  cap would silently shrink the sweep and the gap would look like an absence of events.

Exit 0 clean, 1 when the archive does not close, 3 when the sweep could not be carried out --
the same three-way convention as the rest of code/, because "we did not look" and "we looked
and it was fine" must never share an exit code.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

RPC = "https://rpc.mainnet.chain.robinhood.com"
UA = {"content-type": "application/json", "user-agent": "executability-report/1.0"}
PASS, FAIL, NOT_EXERCISED = 0, 1, 3
CAP_RE = re.compile(r"only\s+(\d+)\s+are allowed")


def rpc(method: str, params: list, timeout: int = 120) -> tuple[dict, float]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(RPC, data=body, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), time.time() - t0
    except Exception as exc:                                        # noqa: BLE001
        return {"error": {"transport": f"{type(exc).__name__}: {exc}"}}, time.time() - t0


def blob(obj) -> bytes:
    """One serialisation, used both for the digest and for what is written."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def line(obj) -> str:
    """One response, as one line. Compact so no response can contain a newline: the
    archive's responses file is newline-delimited and a wrapped response would shift
    every entry after it."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--from-block", type=int, default=0)
    ap.add_argument("--to-block", type=int, default=0,
                    help="0 = read the head and pin to it; pass a number to reproduce an "
                         "earlier sweep over exactly the same range")
    ap.add_argument("--span", type=int, default=0,
                    help="blocks per query; 0 = take it from the node's own refusal of an "
                         "over-wide query, which is the only value this will act on silently")
    ap.add_argument("--tag", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    addr = a.address.lower()

    if a.to_block:
        top = a.to_block
    else:
        h, _ = rpc("eth_blockNumber", [])
        if "result" not in h:
            print(f"could not read head: {json.dumps(h)[:140]}", file=sys.stderr)
            return NOT_EXERCISED
        top = int(h["result"], 16)
    blk, _ = rpc("eth_getBlockByNumber", [hex(top), False])
    if "result" not in blk or not blk["result"]:
        print(f"could not read block {top}: {json.dumps(blk)[:140]}", file=sys.stderr)
        return NOT_EXERCISED
    top_hash = blk["result"]["hash"]
    top_time = int(blk["result"]["timestamp"], 16)
    print(f"{addr} · sweep {a.from_block:,}..{top:,} · top block {top_hash} · "
          f"{dt.datetime.utcfromtimestamp(top_time).isoformat()}Z")

    raw, full = [], []

    def record(params: list, resp: dict, elapsed: float, purpose: str) -> None:
        body = line(resp)
        raw.append({"i": len(raw), "method": "eth_getLogs", "params": params,
                    "purpose": purpose, "ok": "result" in resp,
                    "why": None if "result" in resp else str(resp.get("error"))[:300],
                    "elapsed_s": round(elapsed, 3), "resp_len": len(body),
                    "full_resp_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()})
        full.append(body)

    # Read 0: the span cap, measured rather than assumed. The refusal is the evidence, so it
    # is archived like any other read -- and counted apart from the failures that are faults.
    probe_params = [{"address": addr, "fromBlock": hex(a.from_block), "toBlock": hex(top)}]
    probe, el = rpc("eth_getLogs", probe_params)
    record(probe_params, probe, el, "span-cap probe: a refusal here is the expected result "
                                    "and is this record's evidence for the cap")
    span_from_node, cap_text = None, None
    if "result" in probe:
        span_from_node = top - a.from_block + 1          # the whole range was answered at once
        cap_note = ("the node answered the whole range in one query, so no cap was exercised "
                    "and the sweep below is a single read")
    else:
        cap_text = str(probe.get("error"))
        m = CAP_RE.search(cap_text)
        span_from_node = int(m.group(1)) if m else None
        cap_note = f"parsed from the node's refusal: {cap_text[:200]}"
    span = a.span or span_from_node
    if not span or span < 1:
        print("could not establish the per-query block span, and will not guess one: a "
              f"guessed span shrinks the sweep and the gap looks like an absence of events. "
              f"Node said: {cap_text!r}. Pass --span to override.", file=sys.stderr)
        return NOT_EXERCISED
    print(f"  span per query: {span:,} blocks ({'--span' if a.span else 'from the node'})")

    logs, served, failed, empty_ranges = [], [], [], []
    lo = a.from_block
    while lo <= top:
        hi = min(lo + span - 1, top)
        params = [{"address": addr, "fromBlock": hex(lo), "toBlock": hex(hi)}]
        r, el = rpc("eth_getLogs", params)
        record(params, r, el, "sweep chunk")
        if "result" in r and isinstance(r["result"], list):
            served.append([lo, hi, len(r["result"])])
            logs += r["result"]
            if not r["result"]:
                empty_ranges.append([lo, hi])
            print(f"  [{lo:>12,}..{hi:>12,}] {el:5.2f}s  {len(r['result']):>5} logs")
        else:
            failed.append([lo, hi, str(r.get("error"))[:200]])
            print(f"  [{lo:>12,}..{hi:>12,}] {el:5.2f}s  FAILED "
                  f"{str(r.get('error'))[:90]}", file=sys.stderr)
        lo = hi + 1

    if not served:
        print("no chunk was answered: nothing was swept, and an empty archive would read "
              "like a contract with no events", file=sys.stderr)
        return NOT_EXERCISED

    blocks = sorted({int(x["blockNumber"], 16) for x in logs})
    topics: dict = {}
    for x in logs:
        t0 = (x.get("topics") or ["<no topics>"])[0]
        topics[t0] = topics.get(t0, 0) + 1

    captured = {
        "address": addr,
        "swept_from_block": a.from_block,
        "swept_to_block": top,
        "top_block_hash": top_hash,
        "top_block_timestamp": top_time,
        "span_per_query": span,
        "span_source": "--span" if a.span else "node",
        "span_evidence": cap_note,
        "chunks_served": len(served),
        "chunks_failed": len(failed),
        "chunk_failures": failed,
        "log_count": len(logs),
        "blocks_with_logs": len(blocks),
        "earliest_log_block": blocks[0] if blocks else None,
        "latest_log_block": blocks[-1] if blocks else None,
        "topic0_counts": topics,
        "retention_proven_to_block": blocks[0] if blocks else None,
        "retention_proven_depth_blocks": (top - blocks[0]) if blocks else None,
        "empty_ranges": empty_ranges,
        "coverage_note":
            "The only retention claim here is retention_proven_to_block: logs came back from "
            "that depth, so the node serves logs at least that deep for this address. "
            "empty_ranges establish nothing. An empty range is equally consistent with the "
            "contract not existing yet, with no events in it, and with a node that has "
            "dropped its log index that far back and answers empty instead of erroring; this "
            "sweep cannot tell those apart. Depths are in blocks and are deliberately not "
            "converted to days: this chain's block time was measured at about a tenth of a "
            "second, an earlier conversion in this project used two seconds and was wrong by "
            "roughly twenty times, and a reader who wants days should divide by a block time "
            "that carries its own measurement.",
        "pinning_note":
            "eth_getLogs takes a block range and cannot be pinned by block hash the way "
            "eth_call is, so the top of this range is not reorg-proof. top_block_hash and "
            "top_block_timestamp are recorded so a re-run can be compared against the same "
            "chain tip, and --to-block reproduces exactly this range.",
        "raw_only_note":
            "every response is archived as the node returned it: topics and data as hex, "
            "nothing decoded. topic0_counts counts identical first topics and does not name "
            "them, because naming an event needs an ABI and that choice belongs in the "
            "analysis.",
    }

    if a.dry_run:
        print("\n" + json.dumps(captured, indent=2)[:1600])
        print(f"\n(--dry-run: nothing written; {len(failed)} chunk failure(s))")
        return PASS

    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    tag = f"-{a.tag}" if a.tag else ""
    stem = f"logs-{addr[2:10]}-{top}{tag}"
    idx_name, rsp_name = f"{stem}.index.json", f"{stem}.responses.jsonl.gz"

    idx_bytes = blob(raw)
    with open(os.path.join(out, idx_name), "wb") as fh:
        fh.write(idx_bytes)
    rsp_bytes = ("\n".join(full) + "\n").encode("utf-8")
    with gzip.GzipFile(filename=os.path.join(out, rsp_name), mode="wb", mtime=0) as fh:
        fh.write(rsp_bytes)

    if not (len(raw) == len(full)):
        print(f"archive does not close: {len(raw)} entries, {len(full)} responses",
              file=sys.stderr)
        return FAIL

    rec = dict(captured)
    rec.update({
        "calls": len(raw), "entries": len(raw),
        "failure_count": len(failed), "expected_failures": 1 if cap_text else 0,
        "index_file": idx_name, "index_sha256": hashlib.sha256(idx_bytes).hexdigest(),
        "responses_file": rsp_name,
        "responses_sha256_uncompressed": hashlib.sha256(rsp_bytes).hexdigest(),
        "archive_note": "index_file is the complete read list for this sweep, one entry per "
                        "eth_getLogs in order, the span-cap probe and any failed chunk "
                        "included, each carrying the request as sent and the sha256 of the "
                        "full response. responses_file holds the full responses in the same "
                        "order, one per line. Verified by code/verify_reads.py (path relative "
                        "to the repository root).",
    })
    recname = f"{stem}.json"
    with open(os.path.join(out, recname), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # 🔴 Re-read what was written and re-digest it. The digest above is over the bytes this
    #    process built; this is over the bytes that are on disk. They can differ -- a short
    #    write, a filesystem that rewrites newlines -- and the archive would then carry a
    #    digest of something nobody can reproduce from the file.
    on_disk_idx = hashlib.sha256(open(os.path.join(out, idx_name), "rb").read()).hexdigest()
    with gzip.open(os.path.join(out, rsp_name), "rb") as fh:
        on_disk_rsp = hashlib.sha256(fh.read()).hexdigest()
    if (on_disk_idx, on_disk_rsp) != (rec["index_sha256"],
                                      rec["responses_sha256_uncompressed"]):
        print("what was written does not digest to what the record claims:\n"
              f"  read list   on disk {on_disk_idx[:16]}… recorded {rec['index_sha256'][:16]}…\n"
              f"  responses   on disk {on_disk_rsp[:16]}… recorded "
              f"{rec['responses_sha256_uncompressed'][:16]}…", file=sys.stderr)
        return FAIL

    print(f"\nwrote {recname}, {idx_name}, {rsp_name} in {out}")
    print(f"  {len(logs)} logs in {len(blocks)} blocks; logs served from block "
          f"{rec['retention_proven_to_block']} "
          f"({rec['retention_proven_depth_blocks']:,} blocks back) -- and the empty ranges "
          f"below that establish nothing")
    if failed:
        print(f"{len(failed)} chunk failure(s) recorded, not dropped", file=sys.stderr)
    return PASS


if __name__ == "__main__":
    sys.exit(main())
