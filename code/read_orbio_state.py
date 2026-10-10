#!/usr/bin/env python3
"""Capture the raw state of a Pendle PT market at a pinned block, and archive the reads.

    python3 code/read_orbio_state.py --out-dir measurements/orbio-pendle
    python3 code/read_orbio_state.py --dry-run          # print, write nothing

Why this exists and why it is urgent rather than careful. The pre-expiry exit on a PT market
stops existing at expiry: before it, an exit is a trade against the curve; after it, PT
redeems and the question becomes the redemption path. Those are two different questions and
they must not be published under one label. This market expires 2026-10-22 00:00:00 UTC.

And on this chain the public endpoint keeps only minutes of *state* -- events are served far
deeper, which is how a historical trade can still be reconstructed, but a counterfactual
ladder needs the state as it was. So a day not read is a day that cannot be recovered. This
script therefore captures state now and leaves every interpretation for later: it writes the
raw words and nothing derived.

**It records raw fields only.** `lastLnImpliedRate` is a logarithm, not an annualised
percentage, and any figure quoted as a rate has already been through a conversion somebody
else chose. Converting here would bake that choice into the archive, so the conversion belongs
in the analysis and the archive holds what the chain returned.

Reads are pinned by block hash with requireCanonical, which this endpoint honours -- a forged
hash returns "header not found" rather than an answer. The read list and the full responses
are archived in the shape code/verify_reads.py checks, so a capture can be shown later to be
what it says it is, which matters more here than anywhere else: after expiry nobody can go
back and look.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import urllib.request

RPC = "https://rpc.mainnet.chain.robinhood.com"
MARKET = "0x25ee3232421a08f390ef25a34b1d2ccc8394bd05"
UA = {"content-type": "application/json", "user-agent": "executability-report/1.0"}

# selector -> (signature, calldata suffix). readState takes a router address; the zero
# address is passed because the fields read here do not depend on it, and that choice is
# recorded rather than hidden.
# 🔴 2026-10-10: the market contract alone is not enough to price. Pendle's market maths
#    takes a PY index -- the SY exchange rate -- and readState does not return it, so a
#    reader holding only the market's nine words cannot recompute a quote. Found while
#    writing the caliber rather than while writing the code, which is the argument for
#    settling the caliber first. The two captures taken before this line existed are short
#    these reads and say so; they cannot be repaired, because the state they would have
#    read is already gone.
#    (to, selector, signature, calldata suffix)
TOKENS = {
    "SY": "0x346ae4fc5134f13655c65abb6dfd8728a6eb1235",
    "PT": "0xe1652479358a5968bcc8a36274a616422a2d357d",
    "YT": "0x4aec7f5ce469ff4717eceacb67a333fda09aacf0",
}
EXTRA_CALLS = [
    ("SY", "0x3ba0b9a9", "exchangeRate()", ""),
    ("YT", "0x1d52edc4", "pyIndexCurrent()", ""),
    ("YT", "0xd2a3584e", "pyIndexStored()", ""),
    ("PT", "0x18160ddd", "totalSupply()", ""),
    ("PT", "0xe184c9be", "expiry()", ""),
]

CALLS = [
    ("0xe184c9be", "expiry()", ""),
    ("0x2f13b60c", "isExpired()", ""),
    ("0x2c8ce6bc", "readTokens()", ""),
    ("0x794052f3", "readState(address)", "0" * 64),
    ("0x18160ddd", "totalSupply()", ""),
    ("0x72069264", "totalActiveSupply()", ""),
    ("0xe4f8b2e9", "getNonOverrideLnFeeRateRoot()", ""),
]
# readState's nine words, in order, named but not interpreted.
STATE_WORDS = ("totalPt", "totalSy", "totalLp", "treasury", "scalarRoot", "expiry",
               "lnFeeRateRoot", "reserveFeePercent", "lastLnImpliedRate")


def rpc(method: str, params: list, timeout: int = 30) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    try:
        req = urllib.request.Request(RPC, data=body, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:                                        # noqa: BLE001
        return {"error": {"transport": f"{type(exc).__name__}: {exc}"}}


def blob(obj) -> bytes:
    """One serialisation, used both for the digest and for what is written."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default=MARKET)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--tag", default="", help="run label, e.g. run1; keeps two captures at "
                                              "the same block from overwriting each other")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    h = rpc("eth_blockNumber", [])
    if "result" not in h:
        print(f"could not read head: {json.dumps(h)[:140]}", file=sys.stderr)
        return 3
    head = int(h["result"], 16)
    blk = rpc("eth_getBlockByNumber", [hex(head), False])
    if "result" not in blk or not blk["result"]:
        print(f"could not read block {head}: {json.dumps(blk)[:140]}", file=sys.stderr)
        return 3
    bh = blk["result"]["hash"]
    btime = int(blk["result"]["timestamp"], 16)
    pin = {"blockHash": bh, "requireCanonical": True}
    print(f"head {head:,} · {bh} · block time "
          f"{dt.datetime.utcfromtimestamp(btime).isoformat()}Z")

    # (target address, selector, signature, suffix) for every read in one list, so the
    # archive's order is the order they were issued and nothing is grouped after the fact.
    plan = [(a.market, sel, sig, suf) for sel, sig, suf in CALLS]
    plan += [(TOKENS[who], sel, f"{who}.{sig}", suf) for who, sel, sig, suf in EXTRA_CALLS]

    raw, full, failures = [], [], []
    for to, sel, sig, suffix in plan:
        r = rpc("eth_call", [{"to": to, "data": sel + suffix}, pin])
        ok = "result" in r
        body = r["result"] if ok else ""
        why = None if ok else str(r.get("error"))[:200]
        if not ok:
            failures.append({"to": to, "sel": sel, "sig": sig, "why": why})
        raw.append({"i": len(raw), "to": to, "sel": sel, "sig": sig,
                    "params": [{"to": to, "data": sel + suffix}, pin],
                    "ok": ok, "why": why, "resp_len": len(body),
                    "full_resp_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()})
        full.append(body)
        print(f"  {sig:<32} {'ok ' if ok else 'ERR'} {len(body):>5} hex")

    # The captured state, as raw hex words. Nothing is converted: the analysis converts.
    by_sel = {(e["to"], e["sel"]): full[e["i"]] for e in raw if e["ok"]}
    def got(to, sel): return by_sel.get((to, sel), "")
    def hexwords(h: str) -> list:
        h = h[2:] if h.startswith("0x") else h
        return ["0x" + h[i:i + 64] for i in range(0, len(h), 64)]

    state_raw = hexwords(got(a.market, "0x794052f3"))
    tokens_raw = hexwords(got(a.market, "0x2c8ce6bc"))
    captured = {
        "market": a.market,
        "block_number": head,
        "block_hash": bh,
        "block_timestamp": btime,
        "pinned_by": "blockHash with requireCanonical; a forged hash returns 'header not "
                     "found' on this endpoint, which was checked",
        "readState_arg": "0x" + "0" * 40,
        "readState_words_raw": dict(zip(STATE_WORDS, state_raw)) if len(state_raw) == 9
                               else {"_unexpected_word_count": len(state_raw),
                                     "words": state_raw},
        "readTokens_raw": {k: ("0x" + w[-40:]) for k, w in
                           zip(("SY", "PT", "YT"), tokens_raw)} if len(tokens_raw) == 3
                          else {"_unexpected_word_count": len(tokens_raw)},
        "pricing_inputs_raw": {
            "sy_exchangeRate": got(TOKENS["SY"], "0x3ba0b9a9"),
            "yt_pyIndexCurrent": got(TOKENS["YT"], "0x1d52edc4"),
            "yt_pyIndexStored": got(TOKENS["YT"], "0xd2a3584e"),
            "pt_totalSupply": got(TOKENS["PT"], "0x18160ddd"),
            "pt_expiry": got(TOKENS["PT"], "0xe184c9be"),
        },
        "pricing_inputs_note": "Pendle's market maths takes a PY index, which readState does "
                               "not return, so these are captured alongside it. Without them "
                               "the market's nine words cannot produce a quote. Captures "
                               "before 2026-10-10T14:10Z lack this block and cannot be "
                               "repaired: the state they would have read no longer exists.",
        "raw_only_note": "every value here is the hex the chain returned. lastLnImpliedRate "
                         "is a logarithm and not an annualised rate; no conversion is applied "
                         "in this file, because a converted figure carries whoever converted "
                         "it. Conversions belong in the analysis.",
    }

    if a.dry_run:
        print("\n" + json.dumps(captured, indent=2)[:1200])
        print(f"\n(--dry-run: nothing written; {len(failures)} read failure(s))")
        return 0

    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    tag = f"-{a.tag}" if a.tag else ""
    stem = f"orbio-{head}{tag}"
    idx_name, rsp_name = f"{stem}.index.json", f"{stem}.responses.jsonl.gz"

    idx_bytes = blob(raw)
    with open(os.path.join(out, idx_name), "wb") as fh:
        fh.write(idx_bytes)
    rsp_bytes = ("\n".join(full) + "\n").encode("utf-8")
    with gzip.GzipFile(filename=os.path.join(out, rsp_name), mode="wb", mtime=0) as fh:
        fh.write(rsp_bytes)

    if not (len(raw) == len(full) == len(plan)):
        print(f"archive does not close: {len(raw)} entries, {len(full)} responses, "
              f"{len(plan)} calls", file=sys.stderr)
        return 1

    rec = dict(captured)
    rec.update({
        "calls": len(raw), "entries": len(raw),
        "failure_count": len(failures), "failures": failures,
        "index_file": idx_name, "index_sha256": hashlib.sha256(idx_bytes).hexdigest(),
        "responses_file": rsp_name,
        "responses_sha256_uncompressed": hashlib.sha256(rsp_bytes).hexdigest(),
        "archive_note": "index_file is the complete read list for this capture, one entry per "
                        "eth_call in order, failures included, each carrying the request as "
                        "sent and the sha256 of the full response. responses_file holds the "
                        "full responses in the same order. Verified by code/verify_reads.py "
                        "(path relative to the repository root).",
    })
    recname = f"{stem}.json"
    with open(os.path.join(out, recname), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {recname}, {idx_name}, {rsp_name} in {out}")
    if failures:
        print(f"{len(failures)} read failure(s) recorded, not dropped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
