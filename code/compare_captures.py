#!/usr/bin/env python3
"""Two captures of the same pinned block must agree, field for field.

    python3 code/compare_captures.py --a <capture>.json --b <capture>.json
    python3 code/compare_captures.py --a … --b … --out-dir <dir>
    python3 code/compare_captures.py --selftest

Exit 0 when they agree, 1 when they do not, 3 when the comparison could not be made.

## Why this exists, and what "two runs" can mean here

The Base work gates a figure on two runs agreeing bit-for-bit. That gate does not transfer
to this market unchanged, and saying why matters more than the gate itself.

On Base, a row is produced by walking the pool: many reads, in order, and two runs agreeing
means the reads were reproducible. Here the exit curve is **closed-form arithmetic over one
state**. Running the arithmetic twice proves nothing at all -- it is a pure function of its
input, so of course it agrees. A "two runs agreed" line computed that way would be the purest
kind of vacuous criterion: green every time, by construction.

So the thing that can be run twice is the **read**, not the sum. This compares two captures
pinned to the same block hash and requires every raw field to be identical. What that
establishes:

  The endpoint returned the same state for the same pinned block on two separate calls. Not a
  large claim, but the right one: it rules out a transient wrong answer from the endpoint, and
  it is the only part of this measurement that *can* be checked by repetition.

What it does not establish, and the artifact says so beside the figure:

  Nothing about whether the state is correct -- two identical reads of a wrong answer agree.
  Nothing about the curve: that is what the four self-checks in pendle_pt_exit_curve.py are
  for, and none of those establishes agreement with Pendle's deployed contract either.
  Nothing about execution: this market has had no event since 2026-10-08, so no quote here has
  been checked against a trade anybody actually made.

## The retention trap this is built around

State survives roughly ten to fourteen minutes on this endpoint (measured: served 6,000 blocks
back, already pruned by 8,000). So the second capture must follow the first within minutes. A
second capture taken later does not disagree -- it comes back empty, and an empty capture that
still writes a record would read as agreement on nothing. read_orbio_state.py therefore exits
non-zero when its pinned block yields no state words, and this file refuses a capture whose
fields are missing rather than treating absent == absent as a match.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

PASS, FAIL, NOT_EXERCISED = 0, 1, 3
# The fields that carry the state. Deliberately not block_timestamp-adjacent metadata or
# anything this project writes about itself: those differ between runs by design and
# comparing them would make the check fail for reasons that are not about the chain.
RAW_GROUPS = ("readState_words_raw", "readTokens_raw", "pricing_inputs_raw")
IDENTITY = ("market", "block_number", "block_hash", "block_timestamp", "readState_arg")


def load(path: str):
    try:
        return json.load(open(path, encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, f"{path}: {exc}"


def compare(a: dict, b: dict) -> tuple[list, list, int]:
    """Return (disagreements, missing, fields_compared)."""
    bad, missing, n = [], [], 0
    for k in IDENTITY:
        if k not in a or k not in b:
            missing.append(f"identity field {k} absent from one of the captures")
            continue
        n += 1
        if a[k] != b[k]:
            bad.append(f"{k}: {a[k]!r} vs {b[k]!r}")
    for g in RAW_GROUPS:
        ga, gb = a.get(g), b.get(g)
        if not isinstance(ga, dict) or not isinstance(gb, dict):
            missing.append(f"{g} is absent or not a mapping in one of the captures")
            continue
        keys = sorted(set(ga) | set(gb))
        for k in keys:
            if k not in ga or k not in gb:
                missing.append(f"{g}.{k} present in only one capture")
                continue
            # 🔴 Two empty strings are not a match. An empty value is a read that failed,
            #    and two failed reads agreeing is the shape this whole file exists to refuse.
            if not ga[k] or not gb[k]:
                missing.append(f"{g}.{k} is empty in {'a' if not ga[k] else ''}"
                               f"{'b' if not gb[k] else ''} -- an empty value is a failed "
                               f"read, and two failed reads are not agreement")
                continue
            n += 1
            if ga[k] != gb[k]:
                bad.append(f"{g}.{k}: {ga[k]} vs {gb[k]}")
    return bad, missing, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--selftest", action="store_true")
    g = ap.parse_args()
    if g.selftest:
        return selftest()
    if not (g.a and g.b):
        print("--a and --b are required (or --selftest)", file=sys.stderr)
        return NOT_EXERCISED
    A, ea = load(g.a)
    B, eb = load(g.b)
    if ea or eb:
        print(f"NOT EXERCISED  {ea or eb}", file=sys.stderr)
        return NOT_EXERCISED
    # 🔴 A capture that says it is unusable must not be compared. Two unusable captures of
    #    the same expired block agree on nothing and would otherwise read as agreement --
    #    the same failure the empty-value rule below refuses, caught one level earlier and
    #    by the capture's own declaration rather than by inspecting its fields.
    for name, rec in (("a", A), ("b", B)):
        if rec.get("usable") is False:
            print(f"NOT EXERCISED  capture {name} declares usable=false "
                  f"({rec.get('why_unusable')}) -- there is nothing to agree about",
                  file=sys.stderr)
            return NOT_EXERCISED
    older = [n for n, r in (("a", A), ("b", B)) if "usable" not in r]
    if older:
        print(f"  note: capture(s) {older} predate the usable field, so that declaration "
              f"was not available; the field-by-field comparison below still applies")

    if A.get("block_hash") != B.get("block_hash"):
        print(f"NOT EXERCISED  these are different blocks "
              f"({str(A.get('block_hash'))[:18]}… vs {str(B.get('block_hash'))[:18]}…) -- "
              f"two captures of different blocks are expected to differ, so comparing them "
              f"says nothing. Pin the second run with --at-block.", file=sys.stderr)
        return NOT_EXERCISED

    bad, missing, n = compare(A, B)
    print(f"block {A.get('block_number'):,} · {A.get('block_hash')}")
    print(f"  {n} field(s) compared · {len(bad)} disagreement(s) · "
          f"{len(missing)} field(s) not comparable")
    for x in bad:
        print(f"  DISAGREES  {x}", file=sys.stderr)
    for x in missing:
        print(f"  NOT COMPARABLE  {x}", file=sys.stderr)

    if g.out_dir and not bad and not missing:
        rec = {
            "_what": "Two captures of one pinned block, compared field for field.",
            "_establishes": "the endpoint returned the same state for this pinned block on "
                            "two separate calls, so the read is reproducible",
            "_does_not_establish":
                "that the state is correct -- two identical reads of a wrong answer agree; "
                "anything about the exit curve, whose own four self-checks are separate and "
                "none of which establishes agreement with Pendle's deployed contract; and "
                "anything about execution -- this market has had no event since "
                "2026-10-08T16:36:11Z, so no quote here has been checked against a trade "
                "anybody made",
            "_why_not_two_runs_of_the_curve":
                "the curve is closed-form arithmetic over one state, so running it twice "
                "agrees by construction. The repeatable part is the read, not the sum.",
            "block_number": A.get("block_number"), "block_hash": A.get("block_hash"),
            "block_timestamp": A.get("block_timestamp"),
            "capture_a": os.path.basename(g.a), "capture_b": os.path.basename(g.b),
            "fields_compared": n, "disagreements": 0,
            "compared_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "field_groups": list(RAW_GROUPS) + list(IDENTITY),
        }
        out = os.path.abspath(g.out_dir)
        os.makedirs(out, exist_ok=True)
        name = f"tworun-{A.get('block_number')}.json"
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rec, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"  wrote {os.path.join(g.out_dir, name)}")

    if bad:
        return FAIL
    if missing:
        print("NOT EXERCISED  some fields could not be compared, so this is not an "
              "agreement", file=sys.stderr)
        return NOT_EXERCISED
    print("  agreed -- every compared field is identical")
    print("    this shows the read is reproducible; it shows nothing about whether the "
          "state is right")
    return PASS


# ── drill ───────────────────────────────────────────────────────────────────────────────
def selftest() -> int:
    w = lambda x: "0x" + f"{x:064x}"
    base = {"market": "0xm", "block_number": 1, "block_hash": "0xh",
            "block_timestamp": 10, "readState_arg": "0x0",
            "readState_words_raw": {"totalPt": w(5), "totalSy": w(7)},
            "readTokens_raw": {"SY": "0xsy"},
            "pricing_inputs_raw": {"yt_pyIndexCurrent": w(10 ** 18)}}
    import copy
    arms = {}
    arms["identical"] = compare(base, copy.deepcopy(base))
    d = copy.deepcopy(base); d["readState_words_raw"]["totalPt"] = w(6)
    arms["one_state_word_differs"] = compare(base, d)
    d = copy.deepcopy(base); d["block_hash"] = "0xother"
    arms["identity_field_differs"] = compare(base, d)
    d = copy.deepcopy(base); d["pricing_inputs_raw"]["yt_pyIndexCurrent"] = ""
    arms["one_side_empty"] = compare(base, d)
    e1 = copy.deepcopy(base); e1["pricing_inputs_raw"]["yt_pyIndexCurrent"] = ""
    e2 = copy.deepcopy(e1)
    arms["both_sides_empty"] = compare(e1, e2)
    d = copy.deepcopy(base); del d["readState_words_raw"]["totalSy"]
    arms["field_only_on_one_side"] = compare(base, d)
    # the usable gate lives in main(), so it is exercised here against the same shape
    import io, contextlib, tempfile
    def _via_main(ra, rb):
        with tempfile.TemporaryDirectory() as d2:
            pa, pb = os.path.join(d2, "a.json"), os.path.join(d2, "b.json")
            json.dump(ra, open(pa, "w")); json.dump(rb, open(pb, "w"))
            argv = sys.argv
            sys.argv = ["x", "--a", pa, "--b", pb]
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    return main()
            finally:
                sys.argv = argv
    u = copy.deepcopy(base); u["usable"] = False; u["why_unusable"] = ["pruned"]
    ok = copy.deepcopy(base); ok["usable"] = True
    rc_unusable = _via_main(ok, u)
    rc_both_ok = _via_main(ok, copy.deepcopy(ok))
    print(f"  arm {'declared_unusable':<26} exit {rc_unusable} (want {NOT_EXERCISED})")
    print(f"  arm {'both_declared_usable':<26} exit {rc_both_ok} (want {PASS})")

    bad = []
    for name, (dis, mis, n) in arms.items():
        print(f"  arm {name:<26} disagreements {len(dis)} · not comparable {len(mis)} · "
              f"compared {n}")
    if arms["identical"][0] or arms["identical"][1]:
        bad.append("identical captures did not compare clean")
    if not arms["one_state_word_differs"][0]:
        bad.append("a differing state word was not caught")
    if not arms["identity_field_differs"][0]:
        bad.append("a differing identity field was not caught")
    if not arms["one_side_empty"][1]:
        bad.append("an empty value on one side was not flagged as not comparable")
    # 🔴 the decisive arm: two failed reads must NOT count as agreement.
    if not arms["both_sides_empty"][1]:
        bad.append("two empty values compared as agreement -- that is the exact failure this "
                   "file exists to refuse: an expired pinned block makes both captures empty")
    if not arms["field_only_on_one_side"][1]:
        bad.append("a field present on only one side was not flagged")
    if rc_unusable != NOT_EXERCISED:
        bad.append(f"a capture declaring usable=false was compared anyway "
                   f"(exit {rc_unusable})")
    if rc_both_ok != PASS:
        bad.append(f"two usable identical captures did not pass (exit {rc_both_ok})")
    if bad:
        print("\nselftest FAILED", file=sys.stderr)
        for x in bad:
            print(f"  {x}", file=sys.stderr)
        return FAIL
    print("\nselftest: passed -- differences are caught, and two empty reads are refused "
          "rather than counted as agreement")
    return PASS


if __name__ == "__main__":
    sys.exit(main())
