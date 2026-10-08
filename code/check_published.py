#!/usr/bin/env python3
"""Check that the published tree is internally consistent.

Exit 0 clean, 1 on any failure, 3 when a check could not be carried out at all -- that
last one is never folded into either of the others, because "we did not look" and "we
looked and it was fine" must not arrive at the same exit code.

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
  H  a generated file is what    Several files here say in prose that they are generated
     its generator produces      from the artifacts beside them. Prose is not enforced, so
                                 a hand edit survives in a file that claims nobody typed
                                 it. H makes the claim machine-readable and checks it: a
                                 directory declares its generated files in GENERATED.json,
                                 and H re-runs the generator into a temporary directory and
                                 compares byte for byte against what is committed.
                                 Two rules this check lives by:
                                 - it regenerates to a temp path and compares; it never
                                   writes over the committed file. A check that regenerates
                                   in place is a generator, and it hides the thing it was
                                   built to catch.
                                 - if the generator cannot run -- missing dependency, no
                                   network, a crash -- that is `not exercised` and exits 3.
                                   It is never reported as a pass. A failed run and a
                                   clean run must not be the same outcome downstream.
                                 No masking of volatile fields is offered. A generated
                                 artifact that embeds its own generation time cannot be
                                 reproduced by anyone else, which defeats the point of
                                 saying it was generated; if a timestamp is needed it has
                                 to come from the input data, not from the clock.
                                 A directory with no GENERATED.json claims nothing and is
                                 noted, not skipped silently -- the declaration is what
                                 makes the absence of a check visible.
                                 What H establishes is provenance, never correctness: that
                                 the committed file is what the generator produces, and
                                 nothing about whether the generator is right. A generator
                                 printing 61300% because a percentage was multiplied twice
                                 passes H, and did so in draft here. Reading a green H as
                                 "the numbers are right" is the mistake this paragraph
                                 exists to refuse.
  I  a published link with a    The weekly feed publishes corrections_url, the one
     fragment lands on it       machine-readable pointer that says "the corrections are
                                here". It pointed at a fragment while no page in this tree
                                had a single id attribute, so everyone following that
                                pointer landed on the top of the report. The generator
                                already checked that the URL resolves to a real artifact,
                                and it did -- "exists" is not "arrives", and nothing was
                                checking the second one. Off-site links are recorded as not
                                checked, because resolving them needs the network and this
                                file deliberately does not use it.
  J  a declared read archive    A run's record can name an archived read list and carry its
     is present and verifies    digest. Naming it is a claim that it is there, and the usual
                                way the claim breaks is undramatic: the run wrote its
                                archive and the files were never committed, which makes
                                "anchored in git history" false while everything else
                                still looks right. J runs code/verify_reads.py over every
                                record in measurements/*/ and fails on a declaration whose
                                files are absent or whose digests do not match. A record
                                that declares no archive is noted, not failed -- the
                                artifacts published before the archive existed are that
                                shape, and measurements/base-depth/EVIDENCE.json says so.
                                This check exists because the alternative was a line in a
                                checklist, and a checklist is not a criterion.
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CANON = {"data": "rhdepth-v2", "data-oneside": "rhdepth-oneside-v1"}
WEEKLY = "weekly"           # root-level: data/ holds only YYYY-MM-DD directories
STALE_DAYS = 10             # one issue per UTC week leaves the window at most 7 days
                            # behind just before the next run; 10 is that plus slack,
                            # so this fires on a cadence that stopped, not on a late run.
SITE = "https://dirkdiggler1026.github.io/executability-report/"   # the published pages

fails: list[str] = []
notes: list[str] = []
unexercised: list[str] = []


def fail(check: str, msg: str) -> None:
    fails.append(f"{check}  {msg}")


def not_exercised(check: str, msg: str) -> None:
    """The check could not be carried out. Never the same as passing: exit code 3."""
    unexercised.append(f"{check}  {msg}")


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


def check_reads() -> None:
    """Check J. One rule, one place: this calls code/verify_reads.py rather than
    reimplementing its arithmetic, because two copies of a rule drift."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import verify_reads
    except ImportError as exc:
        fail("J", f"code/verify_reads.py could not be imported ({exc}); read archives "
                  f"cannot be checked and that is not a pass")
        return
    declared = ("index_file", "index_sha256", "responses_file",
                "responses_sha256_uncompressed")
    records = sorted(p for p in glob.glob(os.path.join("measurements", "*", "reads-*.json"))
                     if not p.endswith(".index.json"))
    if not records:
        note("J  no read records found in measurements/*/")
        return
    for rec_path in records:
        try:
            rec = json.load(open(rec_path, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fail("J", f"{rec_path}: unreadable as JSON ({exc})")
            continue
        if not any(k in rec for k in declared):
            note(f"J  {rec_path} declares no read archive (pre-archive artifact)")
            continue
        rc = verify_reads.check(rec_path, quiet=True)
        if rc == verify_reads.PASS:
            note(f"J  {rec_path} archive verifies")
        elif rc == verify_reads.FAIL:
            fail("J", f"{rec_path}: declared read archive does not verify -- run "
                      f"python3 code/verify_reads.py {rec_path} for the reason")
        else:
            not_exercised("J", f"{rec_path}: the archive could not be checked; "
                               f"run python3 code/verify_reads.py {rec_path}")


def check_urls() -> None:
    """Check I. A published link carrying a fragment has to land on that fragment.

    The weekly feed carries corrections_url, which is the one machine-readable pointer that
    says "the corrections are here". It pointed at .../#errors while no page in this tree
    held a single id attribute, so every reader following that pointer arrived at the top of
    the report instead. The generator already checks that a published URL resolves to a real
    artifact, and it does: "exists" is not "arrives", and nothing was checking the second.
    """
    with_fragment = 0
    for path in sorted(glob.glob(os.path.join(WEEKLY, "*.json"))):
        try:
            feed = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue                      # G2 already reports a feed that will not parse
        base = os.path.basename(path)
        for key, url in sorted(feed.items()):
            if not key.endswith("_url") or not isinstance(url, str):
                continue
            if not url.startswith(SITE):
                # Off-site. Resolving it needs the network, which this checker does not use,
                # so record that it was not checked rather than implying that it passed.
                note(f"I  {base}:{key} is off-site, not checked here")
                continue
            page, _, frag = url[len(SITE):].partition("#")
            page = page or "index.html"
            if not _safe_rel(page) or not os.path.exists(page):
                fail("I", f"{path}:{key} points at {page} and that file is not in the tree")
            elif not frag:
                note(f"I  {base}:{key} -> {page}, no fragment")
            else:
                body = open(page, encoding="utf-8", errors="replace").read()
                if f'id="{frag}"' in body or f"id='{frag}'" in body:
                    note(f"I  {base}:{key} -> {page}#{frag} lands on an id")
                    with_fragment += 1
                else:
                    fail("I", f"{path}:{key} points at {page}#{frag} and {page} carries no "
                              f'id="{frag}" -- the link resolves to the top of the page, so a '
                              f"reader following it never reaches what it promises")
    if not with_fragment:
        note("I  no on-site link with a fragment was available to check")


def _safe_rel(p: str) -> bool:
    """A declared path must stay inside the tree: relative, no .., no leading slash."""
    if not p or p.startswith(("/", "\\")) or os.path.isabs(p):
        return False
    parts = p.replace("\\", "/").split("/")
    return ".." not in parts and "" not in parts[:-1]


def check_generated_dir(decl_path: str) -> None:
    """Check H for one GENERATED.json. See the module docstring."""
    d = os.path.dirname(decl_path) or "."
    try:
        decl = json.load(open(decl_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail("H", f"{decl_path}: unreadable as JSON ({exc})")
        return

    gen = decl.get("generator")
    outs = decl.get("outputs") or []
    ins = decl.get("inputs") or []
    argv = decl.get("argv") or []
    if not isinstance(gen, str) or not outs:
        fail("H", f"{decl_path}: needs a 'generator' path and a non-empty 'outputs' list")
        return
    for p in [gen, *outs, *ins]:
        if not isinstance(p, str) or not _safe_rel(p):
            fail("H", f"{decl_path}: declared path {p!r} is not a safe relative path")
            return

    # The generator being absent is a failure, not a skip: the declaration says it exists.
    if not os.path.exists(gen):
        fail("H", f"{decl_path}: declares generator {gen} and it is not in the tree")
        return
    for p in ins:
        if not os.path.exists(os.path.join(d, p)):
            fail("H", f"{decl_path}: declared input {p} is not in {d}")
            return
    missing = [p for p in outs if not os.path.exists(os.path.join(d, p))]
    if missing:
        fail("H", f"{decl_path}: declared output(s) {missing} are not in {d}")
        return

    # Regenerate into a temp directory. Never over the committed file: a check that
    # regenerates in place is a generator, and it hides what it was built to catch.
    with tempfile.TemporaryDirectory() as td:
        # The generator path is relative to the repository root; the inputs are relative
        # to the measurement directory. So resolve the generator to an absolute path and
        # run it with the directory as cwd -- without the abspath it is looked for under
        # the measurement directory, every launch fails, and every row of this check
        # degrades to "not exercised" while looking like a transport problem.
        cmd = [sys.executable, os.path.abspath(gen)] + [a.replace("{outdir}", td) for a in argv]
        if not any("{outdir}" in a for a in argv):
            fail("H", f"{decl_path}: argv has no {{outdir}} placeholder, so the regeneration "
                      f"has nowhere to go but over the committed files")
            return
        try:
            p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
        except (OSError, subprocess.SubprocessError) as exc:
            not_exercised("H", f"{decl_path}: generator could not be launched ({exc})")
            return
        if p.returncode != 0:
            tail = (p.stderr or p.stdout or "").strip().splitlines()[-3:]
            not_exercised("H", f"{decl_path}: generator exited {p.returncode} -- cannot tell a "
                               f"broken generator from a missing dependency, so this is not a "
                               f"pass: " + " | ".join(tail))
            return

        for name in outs:
            produced = os.path.join(td, name)
            committed = os.path.join(d, name)
            if not os.path.exists(produced):
                not_exercised("H", f"{decl_path}: generator exited 0 but wrote no {name} into "
                                   f"the temp directory")
                return
            a = open(produced, "rb").read()
            b = open(committed, "rb").read()
            if a != b:
                off = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                           min(len(a), len(b)))
                fail("H", f"{d}/{name}: committed file is not what the generator produces "
                          f"(first difference at byte {off}; committed {len(b)} bytes, "
                          f"regenerated {len(a)} bytes)")
            else:
                note(f"H  {d}/{name} == regenerated ({len(b)} bytes)")


def check_generated() -> None:
    decls = sorted(glob.glob(os.path.join("measurements", "*", "GENERATED.json")))
    if not decls:
        # Noted, not silent. A directory that claims generation only in prose has no
        # machine-readable claim for H to check, and that absence should be visible.
        prose = sorted(
            os.path.dirname(p) for p in glob.glob(os.path.join("measurements", "*", "README.md"))
            if "generated by" in open(p, encoding="utf-8", errors="replace").read(400).lower()
        )
        note(f"H  no GENERATED.json anywhere; generation is claimed in prose only by "
             f"{len(prose)}: {', '.join(prose) if prose else '(none)'}")
        return
    for p in decls:
        check_generated_dir(p)


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
    check_generated()
    check_urls()
    check_reads()

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
    # A check that could not be carried out is not a pass. Exit 3 so a caller that only
    # tests for zero still treats it as a problem, and a caller that reads the code can
    # tell "not exercised" from "failed".
    if unexercised:
        print(f"\nNOT EXERCISED: {len(unexercised)} check(s) could not be carried out",
              file=sys.stderr)
        for u in unexercised:
            print(f"  {u}", file=sys.stderr)
        return 3
    if not quiet:
        print("\nok -- published tree is self-consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
