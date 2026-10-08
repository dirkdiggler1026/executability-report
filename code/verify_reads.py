#!/usr/bin/env python3
"""Check one measurement's read archive: one digest over the read list, one per response.

    python3 code/verify_reads.py measurements/base-depth/<record>.json
    python3 code/verify_reads.py --selftest

Exit 0 clean, 1 on any mismatch, 3 when the check could not be carried out at all --
the same convention as check_published.py, and for the same reason: "we did not look"
and "we looked and it was fine" must not arrive at the same exit code.

What it proves, and what it does not. It proves the two files are the ones the record
digests, and that every shipped response is the one the read list records: that the
archive has not been altered since the record was written, anchored in git history.
It does NOT re-read the chain, so it is silent on whether the reads were right the first
time. The weaker claim is the one stated, because it is the one this file can establish.

The read list and the responses are checked against each other by position, so a response
swapped with another is caught even though both files are individually intact.

Standard library only, no network: a reader on another machine can run exactly this.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import tempfile

PASS, FAIL, NOT_EXERCISED = 0, 1, 3


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(rec_path: str, quiet: bool = False) -> int:
    """Verify one record. Returns one of PASS / FAIL / NOT_EXERCISED."""
    fails: list[str] = []
    d = os.path.dirname(rec_path) or "."
    try:
        rec = json.load(open(rec_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"NOT EXERCISED  {rec_path}: unreadable as JSON ({exc})", file=sys.stderr)
        return NOT_EXERCISED

    needed = ("index_file", "index_sha256", "responses_file", "responses_sha256_uncompressed")
    missing = [k for k in needed if k not in rec]
    if missing:
        # A record that carries no archive cannot be checked. Reported, never passed.
        print(f"NOT EXERCISED  {rec_path}: no archive to check, missing {missing}",
              file=sys.stderr)
        return NOT_EXERCISED

    idx_path = os.path.join(d, rec["index_file"])
    rsp_path = os.path.join(d, rec["responses_file"])
    for p in (idx_path, rsp_path):
        if not os.path.isfile(p):
            print(f"NOT EXERCISED  {p}: recorded but not on disk", file=sys.stderr)
            return NOT_EXERCISED

    # 1. the read list, over the file's exact bytes
    idx_bytes = open(idx_path, "rb").read()
    got = hashlib.sha256(idx_bytes).hexdigest()
    if got != rec["index_sha256"]:
        fails.append(f"read list sha256 {got[:16]}… != the recorded {rec['index_sha256'][:16]}…")
    try:
        entries = json.loads(idx_bytes.decode("utf-8"))
    except ValueError as exc:
        fails.append(f"read list is not JSON ({exc})")
        entries = []
    if not isinstance(entries, list):
        fails.append("read list is not a list of entries")
        entries = []

    # 2. the responses, over the uncompressed bytes
    try:
        with gzip.open(rsp_path, "rb") as fh:
            rsp_bytes = fh.read()
    except (OSError, EOFError) as exc:
        print(f"NOT EXERCISED  {rsp_path}: will not decompress ({exc})", file=sys.stderr)
        return NOT_EXERCISED
    got = hashlib.sha256(rsp_bytes).hexdigest()
    if got != rec["responses_sha256_uncompressed"]:
        fails.append(f"responses sha256 {got[:16]}… != the recorded "
                     f"{rec['responses_sha256_uncompressed'][:16]}…")
    lines = rsp_bytes.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    # 3. the counts close, and each response is the one its entry records
    calls, stated = rec.get("calls"), rec.get("entries")
    if not (len(entries) == len(lines) == calls == stated):
        fails.append(f"counts do not close: read list {len(entries)} · responses {len(lines)}"
                     f" · calls {calls} · entries {stated}")
    else:
        # Every entry is checked, and the first mismatch of each kind is reported with its
        # index and its nature -- not just "a response is wrong somewhere".
        bad_resp, bad_order = [], []
        for n, (e, body) in enumerate(zip(entries, lines)):
            if "full_resp_sha256" not in e:
                bad_resp.append((n, "the entry records no full_resp_sha256"))
                continue
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != e["full_resp_sha256"]:
                bad_resp.append((n, f"entry label {e.get('label')!r} leg {e.get('leg')!r} "
                                    f"sel {e.get('sel')!r}"))
            pos = e.get("i")
            if pos != n:
                # Entries carry their own index; if that index is not the position, the
                # pairing above is not the pairing the record describes.
                bad_order.append((n, pos))
        if bad_resp:
            n, detail = bad_resp[0]
            fails.append(f"response {n} does not match the sha256 its entry records ({detail})"
                         + (f"; {len(bad_resp) - 1} further response(s) likewise" if len(bad_resp) > 1 else ""))
        if bad_order:
            n, pos = bad_order[0]
            fails.append(f"read list entry {n} says it is i={pos!r} -- the list is not in the "
                         f"order the responses are")

    if fails:
        print(f"FAILED  {rec_path}", file=sys.stderr)
        for f in fails:
            print(f"  {f}", file=sys.stderr)
        return FAIL

    if not quiet:
        print(f"ok -- {len(entries)} reads, both digests match, counts close "
              f"(block {rec.get('block_number')}, {str(rec.get('block_hash'))[:18]}…)")
        print("    this shows the archive is unaltered; it does not re-read the chain")
    return PASS


# ── self-test ────────────────────────────────────────────────────────────────────────
# Four arms over a synthetic archive built here. The point of running them together is
# that their outcomes must DIFFER: a check whose clean arm and broken arms all return the
# same thing cannot tell a good archive from a bad one.
#
# NOTE, and it is a real limit: the fixture below re-implements the collector's
# serialisation (sorted keys, compact separators, gzip mtime=0). If the collector drifts
# from that shape, this self-test still passes, because both sides drifted together.
# Catching that needs the collector in the loop, which a public tree cannot require.

def _blob(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _fixture(d: str) -> str:
    """Write a small intact archive into d; return the record path."""
    bodies = ["0x" + "00" * 32, "0x", None, "0x" + "ab" * 32]
    raw, full = [], []
    for n, body in enumerate(bodies):
        text = "" if body is None else body
        ok = body is not None and body != "0x" and len(text) >= 66
        raw.append({"i": n, "label": f"0xpool{n}|AAPLc/USDC|100|fee500|ts10",
                    "leg": "leg1", "sel": "0x5339c296", "method": "eth_call",
                    "params": [{"to": "0x" + "11" * 20, "data": "0x5339c29600"},
                               {"blockHash": "0x" + "ab" * 32, "requireCanonical": True}],
                    "ok": ok, "why": None if ok else "stub failure",
                    "resp_len": len(text),
                    "full_resp_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
        full.append(text)

    idx_name, rsp_name = "reads-abc123abc123.index.json", "reads-abc123abc123.responses.jsonl.gz"
    idx_bytes = _blob(raw)
    with open(os.path.join(d, idx_name), "wb") as fh:
        fh.write(idx_bytes)
    rsp_bytes = ("\n".join(full) + "\n").encode("utf-8")
    with open(os.path.join(d, rsp_name), "wb") as raw_fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_fh, mtime=0) as gz_fh:
            gz_fh.write(rsp_bytes)

    rec = {"block_hash": "0x" + "ab" * 32, "block_number": 52171860, "calls": len(raw),
           "entries": len(raw), "failure_count": 1, "aborted": None,
           "index_file": idx_name, "index_sha256": hashlib.sha256(idx_bytes).hexdigest(),
           "responses_file": rsp_name,
           "responses_sha256_uncompressed": hashlib.sha256(rsp_bytes).hexdigest()}
    path = os.path.join(d, "reads-STUB.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
    return path


def _arm(mutate=None) -> tuple:
    """Run one arm in its own directory. Returns (code, captured stderr text)."""
    with tempfile.TemporaryDirectory() as td:
        rec_path = _fixture(td)
        if mutate:
            mutate(td, rec_path)
        import io
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = check(rec_path, quiet=True)
        return code, err.getvalue()


def selftest() -> int:
    def corrupt_response(td, rec_path):
        rec = json.load(open(rec_path, encoding="utf-8"))
        p = os.path.join(td, rec["responses_file"])
        with gzip.open(p, "rb") as fh:
            body = fh.read()
        n = body.index(b"0x00") + 3
        body = body[:n] + (b"1" if body[n:n + 1] == b"0" else b"0") + body[n + 1:]
        # Recompressed rather than bit-flipped: a flipped byte in the stream is a CRC
        # error, which is "could not run" (3) -- and this arm exists to produce a
        # MISMATCH (1), so the two outcomes must not be conflated.
        with open(p, "wb") as raw_fh:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_fh, mtime=0) as gz_fh:
                gz_fh.write(body)

    def corrupt_manifest(td, rec_path):
        rec = json.load(open(rec_path, encoding="utf-8"))
        p = os.path.join(td, rec["index_file"])
        b = bytearray(open(p, "rb").read())
        i = b.index(b'"i":0') + len('"i":')     # a value, never a structural character
        b[i] = ord("1")
        open(p, "wb").write(bytes(b))

    def drop_responses(td, rec_path):
        rec = json.load(open(rec_path, encoding="utf-8"))
        os.remove(os.path.join(td, rec["responses_file"]))

    arms = {
        "clean": (_arm(), PASS, "clean"),
        "one_response_byte_changed": (_arm(corrupt_response), FAIL, "mismatch"),
        "one_manifest_byte_changed": (_arm(corrupt_manifest), FAIL, "mismatch"),
        "responses_missing": (_arm(drop_responses), NOT_EXERCISED, "not-exercised"),
    }

    ok = True
    for name, ((code, err), want, _label) in arms.items():
        first = next((ln.strip() for ln in reversed(err.splitlines()) if ln.strip()), "")
        good = code == want
        ok = ok and good
        print(f"  arm {name}: exit {code} (want {want}) {'✓' if good else '✗'}"
              f"{(' -- ' + first) if first else ''}")

    # Discrimination: the arms must not all be the same outcome, and the two broken arms
    # must name different things -- otherwise the check reports "something is wrong"
    # without saying what, and a broken read list would look like a broken response.
    codes = {label: code for _n, ((code, _e), _w, label) in arms.items()}
    resp_err = arms["one_response_byte_changed"][0][1]
    idx_err = arms["one_manifest_byte_changed"][0][1]
    distinct_codes = len({c for (c, _e), _w, _l in arms.values()}) == 3
    named_differently = ("read list sha256" in idx_err and "read list sha256" not in resp_err
                         and "does not match the sha256 its entry records" in resp_err)
    ok = ok and distinct_codes and named_differently
    print(f"  three distinct exit codes (0/1/3): {'✓' if distinct_codes else '✗'}"
          f"  ({codes})")
    print(f"  the two failing arms name different things: {'✓' if named_differently else '✗'}")
    print(f"selftest: {'passed' if ok else 'FAILED'} -- the arms differ, so the check "
          f"discriminates")
    return PASS if ok else FAIL


def main() -> int:
    quiet = "--quiet" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--selftest" in sys.argv:
        return selftest()
    if len(args) != 1:
        print(__doc__)
        return NOT_EXERCISED
    return check(args[0], quiet=quiet)


if __name__ == "__main__":
    sys.exit(main())
