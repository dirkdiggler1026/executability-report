"""Generate now.html -- the ten-second entry point.

The problem this solves
-----------------------
Everything this project has produced is supply-side. A stranger who wants to understand the
finding currently has to read a long report, or clone a repository, or obtain an archive
endpoint. There is no surface where the finding is legible in ten seconds, and that matters for
one specific reason: the pre-registered citation criterion is "within 60 days, at least one
other person's post cites a block number or a roundKeccak". A citation needs something citable.
A file inside a git repository is a weak citation target; a page with the block number and the
round hash printed on it is a strong one.

So this page adds NO new measurement. Every figure is already published under data/. It changes
the shape of the entry, not the content.

Three things it must do, and nothing else:
  1. the numbers, for every token and every size, live as of the latest published round
  2. the block number and the roundKeccak, so the page can be cited
  3. one line saying how to recompute it, and one line saying the report page is a DIFFERENT
     window (that page is a frozen 12-round snapshot from 2026-09-04 and never changes)

Definition of the statistic: median recovery over the latest day's rounds, with the p10-p90 range
underneath. Percentiles rather than min-max, because one round where a maker briefly pulled depth
would misrepresent the normal state; the range is kept because it is what exposes a bimodal
token. A round whose size could not be filled is NOT a zero -- it is counted separately, because
averaging it in as 0% hides the thing worth reporting. This is the same definition code/analyze.py
uses.

The range is labelled "within that day", and the mechanism sentence says the range is not a
characterisation of the token. That wording is load-bearing rather than cautious. Measured over
the last two published days, TWO cells change character between them:

    RDDT $100,000   0.04-33.50   ->  33.21-33.50
    GME  $10,000   13.68-58.82   ->  52.75-60.04

RDDT is the sharper case: across the published series its $100,000 median is 0.04 and 534 of 706
rounds are below 50%, while on the latest day it sits at ~33 with a narrow spread. So a single-day
page with an unqualified range would not merely fail to show the mechanism -- it would hand the
reader a wrong character judgement ("this token is stable"). The fix is the wording, not a new
column: adding a cross-window statistic here would break the one-sentence definition the page
rests on, and the mechanism belongs to the series, which the report already carries.

    python make_now.py
"""

from __future__ import annotations

import datetime
import gzip
import html
import json
import os
import statistics as st
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent
DATA = REPO / "data"
OUT = REPO / "now.html"
SIZES = [100, 1_000, 10_000, 100_000]
SIZE_LABEL = ["$100", "$1,000", "$10,000", "$100,000"]
ORDER = ["SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "RDDT", "AMC", "GME"]

# Cells the published pool table cannot support, and which therefore carry a marker tied to the
# footnote. QQQ at $100 is the known instance: the table keeps the eight best pools per token, and
# a cheaper 0.05% QQQ/USDG pool was created at block 55,328,824 -- after the table's cutoff -- so
# the series routes around it. Every other cell is the best route among the pools in the table.
FLAGGED = {("QQQ", 100)}


def pct(v: list[float], q: float) -> float:
    v = sorted(v)
    if not v:
        return 0.0
    i = (len(v) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def main() -> int:
    days = sorted(d for d in DATA.iterdir() if d.is_dir() and len(d.name) == 10)
    if not days:
        raise SystemExit(f"no dated day directories under {DATA}")
    day = days[-1]

    rounds = [json.loads(x) for x in (day / "rounds.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    last = rounds[-1]
    blocks = {r["block"] for r in rounds}

    cells: dict[tuple[str, int], list[float]] = {}
    unfilled: dict[tuple[str, int], int] = {}
    with gzip.open(day / "quotes.jsonl.gz", "rt") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            key = (r["sell_sym"], r["size_usd"])
            if r.get("status") == "ok" and r.get("recovery_pct") is not None:
                cells.setdefault(key, []).append(float(r["recovery_pct"]))
            else:
                unfilled[key] = unfilled.get(key, 0) + 1

    tokens = [t for t in ORDER if any(k[0] == t for k in list(cells) + list(unfilled))]
    tokens += sorted({k[0] for k in list(cells) + list(unfilled)} - set(tokens))

    n_rounds = len(blocks)
    span = f"{min(blocks):,} .. {max(blocks):,}"
    # 🔴 NOT `last["committed"]`. That field is `false` on every record ever published and
    #    always will be: A8 says chain state is never written back into a published data file,
    #    so the "yes" branch of a ternary on it is dead code. code/verify.py:33 already carries
    #    this lesson; this file was written the day after and repeated it anyway.
    #    This page reads published bytes only (see the docstring), so it must not ask the chain
    #    either. It states the boundary and hands over the call.
    # 🔴 The ledger address now lives in five published places (index.html x2, index.zh.html x2,
    #    README.md, here, and the generated page). That is error #05's shape exactly -- one fact
    #    written down in two places, then drifting apart -- and a mainnet deployment is the event
    #    that makes it drift. deployments.jsonl in the ledger repository stays the authority; this
    #    is a transcription, and the guard below refuses to generate a page from a stale one.
    LEDGER = "0xc4f7c2ed489d9f521d65b43cc4929d3c642c6fb9"
    LEDGER_CHAIN = 46630
    RH_RPC = "https://rpc.testnet.chain.robinhood.com"
    _authority = os.environ.get("DEPLOYMENTS_JSONL", "/root/predict-data/dexfeed/chain/deployments.jsonl")
    if os.path.exists(_authority):
        # Only runs where the authority file is reachable (the machine that publishes). Anywhere
        # else this is a no-op, so the script stays runnable by a stranger with just this repo.
        recs = [json.loads(l) for l in open(_authority) if l.strip()]
        match = [r for r in recs if r["chainId"] == LEDGER_CHAIN]
        if not match:
            raise SystemExit(f"make_now: chainId {LEDGER_CHAIN} is gone from {_authority} -- "
                             f"if the ledger moved, this file and both index pages move with it")
        if match[-1]["address"].lower() != LEDGER.lower():
            raise SystemExit(f"make_now: LEDGER is {LEDGER} but {_authority} says "
                             f"{match[-1]['address']} -- fix the transcription, do not edit the authority")
        if len(recs) > len(match):
            # 🔴 WARN, not fatal -- and the split matters. A wrong address above is fatal because the
            #    page would print a command that reads the wrong contract. A NEW chain appearing here
            #    does not make this page false, only incomplete: the 46630 ledger still exists and
            #    still returns what the page says. Killing the daily publication over an incomplete
            #    page would be the third time this project built a check that blocks the thing it
            #    protects (CI fmt blocking tests; copies_agree blocking backups). Publish, and shout.
            others = sorted({r["chainId"] for r in recs} - {LEDGER_CHAIN})
            print(f"WARN make_now: {_authority} now also has chainId {others}, and this page still "
                  f"points readers at {LEDGER_CHAIN} only. Page is incomplete, not wrong -- published "
                  f"anyway. Update index.html, index.zh.html, README.md and make_now.py together.",
                  file=sys.stderr)
    # Staleness defence. A page that regenerates daily will one day fail to regenerate, and the
    # failure mode this project exists to hunt is a page that keeps saying "latest" while showing
    # old numbers. So the generation time and the round's own time are both printed: a reader can
    # see the age without trusting anything.
    gen_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    round_utc = datetime.datetime.fromtimestamp(
        last["ts"], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def cell(sym: str, size: int) -> str:
        v = cells.get((sym, size), [])
        miss = unfilled.get((sym, size), 0)
        mk = '<span class="mk">*</span>' if (sym, size) in FLAGGED else ""
        if not v:
            return f'<td class="none">&mdash;{mk}<span class="sub">{miss} could not fill</span></td>'
        med = st.median(v)
        lo, hi = pct(v, 0.10), pct(v, 0.90)
        if hi - lo < 0.05:
            sub = "constant" if miss == 0 else f"constant &middot; {miss} could not fill"
        else:
            sub = f"{lo:.2f}&ndash;{hi:.2f}" + (f" &middot; {miss} miss" if miss else "")
        bad = " bad" if med < 90 else ""
        return (f'<td class="num{bad}">{med:.2f}{mk}<span class="sub">{sub}</span></td>')

    rows = "\n".join(
        "<tr><th>" + html.escape(s) + "</th>" + "".join(cell(s, z) for z in SIZES) + "</tr>"
        for s in tokens)

    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>what comes back when you sell &mdash; live</title>
<!--
  Generated by make_now.py from data/{day.name}/. Do not hand-edit.

  This page adds NO new measurement. Every figure here is already published under data/; the
  page exists so that the finding is legible in ten seconds and so that there is something
  citable -- the block number and the roundKeccak are printed below for exactly that reason.

  Deliberately NOT the same window as index.html. That page is a frozen 12-round snapshot ending
  at block 54,270,401 (2026-09-04) and never changes; this one is the live dated series. The two
  are labelled as different windows in the text, because a reader who finds one figure on one
  page and a different figure on the other must be able to see why.
-->
<style>
  :root{{--paper:#101719;--paper-2:#182124;--ink:#DCE6E4;--ink-2:#A3B4B4;--ink-3:#7B8D8E;
        --rule:#2B3A3C;--accent:#5FB6AC;--good:#63B98C;--bad:#D9736C;--warn:#D6A052}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--paper);color:var(--ink);
       font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
       -webkit-font-smoothing:antialiased;padding:56px 64px 72px;max-width:1180px;margin:0 auto}}
  .mono{{font-family:"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace}}
  .kicker{{font-size:13px;letter-spacing:.18em;color:var(--accent);font-weight:600}}
  h1{{margin-top:12px;font-size:31px;line-height:1.3;font-weight:400}}
  h1 b{{font-weight:600}}
  .lead{{margin-top:14px;font-size:16px;line-height:1.6;color:var(--ink-2);max-width:92ch}}
  .anchor{{margin-top:22px;padding:14px 18px;background:var(--paper-2);border:1px solid var(--rule);
          border-radius:4px;font-size:14px;line-height:1.9;color:var(--ink-2)}}
  .anchor b{{color:var(--ink);font-weight:400}}
  table{{margin-top:28px;width:100%;border-collapse:collapse}}
  th,td{{padding:12px 14px;text-align:right;vertical-align:top}}
  thead th{{font-size:12.5px;letter-spacing:.06em;color:var(--ink-3);font-weight:600;
           border-bottom:1px solid var(--rule)}}
  tbody th{{text-align:left;font-size:19px;font-weight:600;color:var(--ink);
           border-bottom:1px solid var(--paper-2)}}
  td.num{{font-family:"Cascadia Mono",Consolas,monospace;font-size:24px;color:var(--good);
         border-bottom:1px solid var(--paper-2);font-variant-numeric:tabular-nums}}
  td.num.bad{{color:var(--bad)}}
  td.none{{font-family:"Cascadia Mono",Consolas,monospace;font-size:24px;color:var(--ink-3);
          border-bottom:1px solid var(--paper-2)}}
  .mk{{color:var(--warn);font-size:15px;vertical-align:7px;margin-left:3px}}
  .sub{{display:block;margin-top:5px;font-family:"IBM Plex Sans",system-ui,sans-serif;
       font-size:11.5px;font-weight:400;color:var(--ink-3);letter-spacing:0}}
  .foot{{margin-top:30px;display:flex;flex-direction:column;gap:9px;font-size:13.5px;
        line-height:1.65;color:var(--ink-3);max-width:104ch}}
  .foot b{{color:var(--ink-2);font-weight:400}}
  .cmd{{margin-top:4px;padding:10px 14px;background:var(--paper-2);border:1px solid var(--rule);
       border-radius:3px;font-family:"Cascadia Mono",Consolas,monospace;font-size:13px;
       color:var(--ink-2);display:inline-block}}
  .qqq{{margin-top:10px;padding:11px 14px;background:var(--paper-2);
       border-left:2px solid var(--warn);border-radius:2px;font-size:12.5px;line-height:1.62;
       color:var(--ink-2)}}
  .qqq b{{color:var(--ink);font-weight:400}}
  a{{color:var(--accent);text-decoration:none}}
</style>
</head>
<body>
  <div class="kicker">WHAT COMES BACK WHEN YOU SELL</div>
  <h1>Not the quoted price. <b>The result of a full round trip, inside one pool.</b></h1>
  <div class="lead">Buy a tokenised stock with USDG and sell the whole position straight back
    through the same pool, at four sizes, at one pinned block every 30 minutes. Below is the
    latest published day: median recovery per token and size, with the p10&ndash;p90 range
    <b>within that day</b> beneath it. A round that could not fill is counted separately, never as
    a zero.</div>

  <div class="anchor mono">
    <b>latest round</b> &nbsp; block {last['block']:,} &nbsp;&middot;&nbsp; canon {html.escape(str(last['canon']))}
      &nbsp;&middot;&nbsp; {last['rows']} rows &nbsp;&middot;&nbsp; {round_utc}<br>
    <b>roundKeccak</b> &nbsp; {html.escape(str(last['roundKeccak']))}<br>
    <b>day</b> &nbsp; {day.name} &nbsp;&middot;&nbsp; {n_rounds} rounds &nbsp;&middot;&nbsp; blocks {span}<br>
    <b>in the ledger</b> &nbsp; this page does not ask &mdash; ask the ledger itself. Commits are batched, so whether the round above is on chain depends on whether its batch has been written &mdash; run it and see. Block 61,129,566 is committed and returns its hash with canon 2; a round that is not yet committed returns canon 0. Running both is the cheapest way to check that canon 0 means what it says:<br>
    &nbsp;&nbsp;&nbsp;&nbsp;cast call {LEDGER} 'getRoundHash(uint64)(bytes32,uint8)' {last['block']} --rpc-url {RH_RPC}<br>
    &nbsp;&nbsp;&nbsp;&nbsp;cast call {LEDGER} 'getRoundHash(uint64)(bytes32,uint8)' 61129566 --rpc-url {RH_RPC}<br>
    <b>generated</b> &nbsp; {gen_utc} &nbsp;&middot;&nbsp; regenerated daily with the data, so this page cannot be older than the day it shows
  </div>

  <table>
    <thead><tr><th></th>{"".join(f"<th>{l}</th>" for l in SIZE_LABEL)}</tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>

  <div class="foot">
    <div><b>Recompute any of it.</b> Every round is pinned to one block, canonically serialised and
      hashed. Replaying one needs an archive endpoint &mdash; a public RPC keeps only minutes of
      state history, and the verifier refuses explicitly rather than hanging when pointed at one.
      <div class="cmd">python code/verify.py {last['block']}</div></div>
    <div><b>This page is the dated series, regenerated daily; the report page is a different
      window.</b> That page is a frozen snapshot of 12 rounds ending at block 54,270,401
      (2026-09-04) and does not change after publication. A figure that differs between the two
      pages is a difference of window, not of method.</div>
    <div><b>Known limitation, stated here rather than in a footnote elsewhere.</b> Every row is the
      best route <i>among the pools in the published pool table</i>, and that table keeps the eight
      best pools per token. A pool created after it is invisible here.
      <div class="qqq"><b>* QQQ at $100.</b> This cell is one of the ten errors in the published
        archive. The pool table ends at block 53,983,886; a cheaper 0.05% QQQ/USDG pool was created
        at block 55,328,824, after that cutoff, so the series routes around it. Measured against
        the chain, this cell is about <b>95.6%</b>. The damage is bounded and the bound is
        checkable: that pool returns no quote above about <b>$300</b>, so the $1,000 row and every
        deeper size are unaffected by it.
        <br><b>What is not established:</b> whether <i>other</i> rows are affected by other
        post-cutoff pools. That is the post-cutoff pool scan, and the repository says so rather
        than implying this is the only one.</div></div>
    <div><b>The failure is not one thing.</b> Some tokens collapse at every size with almost no
      variance; some switch between two states with nothing in between; some slope down as size
      rises. <b>The range above shows how far each cell moved within the day &mdash; it is not a
      characterisation of the token.</b> A token that alternates between two states can look
      constant on any single day, and one that is quiet today can be wide tomorrow. Which shape a
      token has is a property of the series, not of one day; it is established in the report, not
      here.</div>
    <div><a href="https://github.com/dirkdiggler1026/executability-report">data, method, verifier and
      error archive</a> &middot; ten published errors, eight caught before publication</div>
  </div>
</body>
</html>
""", encoding="utf-8", newline="\n")

    print(f"wrote {OUT}")
    print(f"  day {day.name} · {n_rounds} rounds · blocks {span}")
    print(f"  latest block {last['block']:,} · keccak {str(last['roundKeccak'])[:18]}…")
    print(f"  {len(tokens)} tokens x {len(SIZES)} sizes = {len(tokens) * len(SIZES)} cells")
    print(f"  {sum(unfilled.values())} rounds could not fill at some size and are counted separately")
    return 0


if __name__ == "__main__":
    sys.exit(main())
