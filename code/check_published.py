#!/usr/bin/env python3
"""Check that the published tree is internally consistent. Exit 0 clean, 1 on any failure.

Run from the repository root:

    python3 code/check_published.py            # full report
    python3 code/check_published.py --quiet    # only failures

This is the *same file* the publishing script on the collecting machine runs before it
commits, and the same file CI runs on every push. That is deliberate. Two copies of a
rule drift, and when they disagree there is no way to say which one is the rule --
this repository has already published one number twice and watched the copies diverge.

What it does NOT check. It reads the published tree only. It cannot see the collector,
the chain, or the publishing script's own behaviour, so a green result here means
"what is published is self-consistent", never "the publishing process is sound".
The process guards live in sync.sh, which runs on one machine; this file is what a
reader can run without that machine.

The checks, and the failure each exists for:

  A  day-directory naming        Withdrawn data lives in suffixed directories
                                 (2026-09-03.rhdepth-v1-defective). A strict
                                 YYYY-MM-DD whitelist is what keeps a withdrawn
                                 directory from being read as a live one.
  B  every listed file verifies  A checksum nobody recomputes is decoration.
  C  no unlisted files           A file in a data directory that no MANIFEST covers
                                 is published without a checksum, and looks identical
                                 to one that has been checked.
  D  canon per tree              data/ is rhdepth-v2; data-oneside/ is
                                 rhdepth-oneside-v1; rhdepth-v1 appears only inside
                                 quarantined directories. A series that leaks into the
                                 other tree's directory would be counted as that series.
  E  quarantine is declared      A suffixed directory must carry QUARANTINED.json.
                                 The suffix is for humans; the file is for programs.
  F  enumerated_at_block resolves Registered in addendum 2 section 2a: a round names the
                                 venue list it used, and that name has to point at a file
                                 that still exists -- or at an explicit record that it
                                 does not (MISSING-<block>.json).
  G  the weekly feed is generated weekly/latest.json is the subscribed URL, so it is the
                                 file most worth writing by hand under time pressure --
                                 and a hand-written feed is indistinguishable from a
                                 generated one by eye. Three sub-checks make it
                                 distinguishable by machine:
                                 G1 latest.json is byte-identical to one of the archived
                                    weekly/<ISO-week>.json files. A file typed into the
                                    stable name, matching no archive, fails here.
                                 G2 exactly one of: a window with rounds, or a reason.
                                    The specification requires that a week with no data
                                    still publish the file, carrying the reason -- silence
                                    is never the same as health.
                                 G3 a non-empty window ends no more than STALE_DAYS ago,
                                    or the file says why. The cadence is one issue per UTC
                                    week; this is what notices that it stopped.
                                 What G cannot see: whether generation is scheduled at
                                 all. That is a fact about a host, not about this tree.
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import hashlib
import json
import os
import re
import sys

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CANON = {"data": "rhdepth-v2", "data-oneside": "rhdepth-oneside-v1"}
WEEKLY = "weekly"           # root-level: data/ holds only YYYY-MM-DD directories
STALE_DAYS = 10             # one issue per UTC week leaves the window at most 7 days
                            # behind just before the next run; 10 is that plus slack,
                            # so this fires on a cadence that stopped, not on a late run.

fails: list[str] = []
notes: list[str] = []


def fail(check: str, msg: str) -> None:
    fails.append(f"{check}  {msg}")


def note(msg: str) -> None:
    notes.append(msg)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_manifest(d: str) -> None:
    """B and C, for one directory."""
    m = os.path.join(d, "MANIFEST.sha256")
    if not os.path.exists(m):
        fail("B", f"{d}: no MANIFEST.sha256")
        return
    listed = {}
    for line in open(m):
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            fail("B", f"{m}: unparseable line {line!r}")
            continue
        listed[parts[1].strip()] = parts[0]
    if not listed:
        fail("B", f"{m}: empty manifest")
        return
    for name, want in sorted(listed.items()):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            fail("B", f"{d}: {name} is in the manifest and not on disk")
            continue
        got = sha256(p)
        if got != want:
            fail("B", f"{d}: {name} sha256 {got[:16]}… != manifest {want[:16]}…")
    on_disk = {f for f in os.listdir(d)
               if os.path.isfile(os.path.join(d, f)) and f != "MANIFEST.sha256"}
    for extra in sorted(on_disk - set(listed)):
        fail("C", f"{d}: {extra} is present and not in the manifest")


def rounds_of(path: str):
    for line in open(path):
        if line.strip():
            yield json.loads(line)


def check_weekly() -> None:
    """Check G. See the module docstring for what each sub-check exists for."""
    latest = os.path.join(WEEKLY, "latest.json")
    if not os.path.isdir(WEEKLY) or not os.path.exists(latest):
        note(f"{WEEKLY}/latest.json not present, G skipped")
        return

    # G1 -- the stable name must be a copy of an archive, not a file someone typed.
    want = sha256(latest)
    archives = sorted(p for p in glob.glob(os.path.join(WEEKLY, "*.json"))
                      if os.path.basename(p) != "latest.json")
    match = [p for p in archives if sha256(p) == want]
    if not archives:
        fail("G1", f"{latest}: no archived weekly/<ISO-week>.json to be a copy of")
    elif not match:
        fail("G1", f"{latest}: byte-identical to none of the {len(archives)} archived "
                   f"week file(s) -- a feed under the stable name that no generator "
                   f"produced")
    else:
        note(f"G  latest.json == {os.path.basename(match[0])}")

    try:
        feed = json.load(open(latest, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail("G2", f"{latest}: unreadable as JSON ({exc})")
        return

    win = feed.get("window") or {}
    rounds = win.get("rounds") or 0
    reason = (feed.get("reason") or "").strip()

    # G2 -- exactly one. Both means the file contradicts itself about whether it has
    # data; neither means an empty week was published without saying why.
    if bool(rounds) == bool(reason):
        fail("G2", f"{latest}: window rounds={rounds!r} and reason={'set' if reason else 'absent'}"
                   f" -- exactly one of the two is required")

    # G3 -- a window that stopped moving. Measured against today, because that is what
    # a reader checking the feed has; the generator stamps generated_utc separately.
    through = win.get("through")
    if rounds and through:
        try:
            age = (dt.date.today() - dt.date.fromisoformat(through)).days
        except ValueError:
            fail("G3", f"{latest}: window.through {through!r} is not a date")
        else:
            # A window ending in the future is not staleness, it is a wrong clock or a
            # --through passed by hand. Found by a test that forced a future window and
            # watched the staleness check pass it without comment.
            if age < 0:
                fail("G3", f"{latest}: window ends {through}, {-age} days in the future")
            elif age > STALE_DAYS and not reason:
                fail("G3", f"{latest}: window ends {through}, {age} days ago "
                           f"(limit {STALE_DAYS}) and the file gives no reason")
            else:
                note(f"G  window ends {through}, {age} days ago (limit {STALE_DAYS})")


def main() -> int:
    quiet = "--quiet" in sys.argv
    if not os.path.isdir("data"):
        print("FAIL: run this from the repository root (no data/ here)", file=sys.stderr)
        return 1

    day_dirs, quarantined = {}, []
    for root in CANON:
        if not os.path.isdir(root):
            note(f"{root}/ not present, skipped")
            continue
        day_dirs[root] = []
        for p in sorted(glob.glob(os.path.join(root, "*"))):
            if not os.path.isdir(p):
                continue
            name = os.path.basename(p)
            if DAY.match(name):
                day_dirs[root].append(p)
            elif name == "enumerations":
                check_manifest(p)
            else:
                # A: anything that is not a strict day is data that is not live data.
                quarantined.append(p)
                check_manifest(p)
                if not os.path.exists(os.path.join(p, "QUARANTINED.json")):
                    # snapshot-v18-12r is a published snapshot, not a withdrawal; it is
                    # named in README.md. Anything else must declare itself.
                    if name != "snapshot-v18-12r":
                        fail("E", f"{p}: not a YYYY-MM-DD directory and no QUARANTINED.json")

        for d in day_dirs[root]:
            check_manifest(d)
            rp = os.path.join(d, "rounds.jsonl")
            if not os.path.exists(rp):
                fail("D", f"{d}: no rounds.jsonl")
                continue
            for r in rounds_of(rp):
                c = r.get("canon")
                if c != CANON[root]:
                    fail("D", f"{d}: a round declares canon {c!r}, expected "
                              f"{CANON[root]!r} in {root}/")

    # D, the other direction: a withdrawn canon must not appear in a live day directory.
    for p in quarantined:
        rp = os.path.join(p, "rounds.jsonl")
        if os.path.exists(rp):
            cs = {r.get("canon") for r in rounds_of(rp)}
            note(f"{p}: {sorted(c for c in cs if c)} ({sum(1 for _ in rounds_of(rp))} rounds)")

    # F: every enumerated_at_block resolves, per round, not per total.
    if os.path.isdir("data-oneside"):
        have = {int(os.path.basename(p).split("-")[1].split(".")[0])
                for p in glob.glob("data-oneside/enumerations/pools-*.json")}
        noted = {int(os.path.basename(p).split("-")[1].split(".")[0])
                 for p in glob.glob("data-oneside/enumerations/MISSING-*.json")}
        seen: dict[int, int] = {}
        for rp in sorted(glob.glob("data-oneside/*/rounds.jsonl")):
            for r in rounds_of(rp):
                eb = (r.get("pools_source") or {}).get("enumerated_at_block")
                if eb is None:
                    fail("F", f"{rp}: a round has no enumerated_at_block")
                    continue
                seen[eb] = seen.get(eb, 0) + 1
        for eb, n in sorted(seen.items()):
            if eb in have:
                note(f"F  enumerated_at_block {eb:,} -> archived list ({n} rounds)")
            elif eb in noted:
                note(f"F  enumerated_at_block {eb:,} -> explicit MISSING record ({n} rounds)")
            else:
                fail("F", f"enumerated_at_block {eb:,} resolves to nothing "
                          f"({n} rounds claim it)")

    check_weekly()

    if not quiet:
        for n in notes:
            print(f"  {n}")
        counts = {k: len(v) for k, v in day_dirs.items()}
        print(f"  day directories: {counts}, quarantined/other: {len(quarantined)}")
    if fails:
        print(f"\nFAILED: {len(fails)} problem(s)", file=sys.stderr)
        for f in fails:
            print(f"  {f}", file=sys.stderr)
        return 1
    if not quiet:
        print("\nok -- published tree is self-consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
