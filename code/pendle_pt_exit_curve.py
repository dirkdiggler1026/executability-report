#!/usr/bin/env python3
"""The pre-expiry exit curve of a Pendle PT market, computed from one archived capture.

    python3 code/pendle_pt_exit_curve.py --capture measurements/orbio-pendle/orbio-<n>.json
    python3 code/pendle_pt_exit_curve.py --capture … --out-dir measurements/orbio-pendle
    python3 code/pendle_pt_exit_curve.py --selftest

Exit 0 clean, 1 when a self-check fails, 3 when the curve could not be computed at all.

## The quantity

Isomorphic to the Base work, deliberately, so the two are comparable:

    recovery(N) = (what selling N PT actually pays out) / (N x the market's own pre-trade
                  marginal quote for PT)

The denominator is the market's quote *before* the trade, for the same asset, at the same
block. It is what a holder reading the market would believe N PT is worth; the numerator is
what the curve actually pays. The gap is the exit cost, and nothing outside the market enters
either side -- no index, no oracle, no external price.

**And one thing the claim is not: clock-free.** When this caliber was settled the stated
reason for preferring it was that it moves with depth and size but not with the calendar. That
is wrong, and the size of the error is worth printing: `rateScalar` is `scalarRoot x 365d /
timeToExpiry`, so the curve flattens as expiry approaches. Holding this market's reserves
fixed and moving only the clock, selling 200,000 PT recovers 91.91% a year out and 99.99% half
a day out. So a single capture's recovery is a fact about that block, and **a series of them
across captures is not a depth series** -- it mixes the book with the calendar, which is the
exact failure the caliber was chosen to avoid. That is why every row also carries recovery
recomputed at one declared reference time to expiry: the clock is pinned, so what is left to
move is the state. The reference column is the one to put in a series; the measured column is
the one to quote for that block.

That choice was made over the obvious alternative, and the reason is the whole point. The
alternative denominator is PT's face value: one PT redeems for one unit of asset at expiry, so
proceeds over face value is also a number between zero and one. **But that number rises
towards 1 as expiry approaches no matter what happens to depth**, because the discount a PT
trades at shrinks with the remaining time. Reading it as an improvement in depth would be the
same mistake as quoting an annualised implied rate near maturity and calling the result thin
liquidity: it moves with the clock, not with the book. So face value is computed and reported
below, labelled, as a second quantity -- never as the claim.

## What the inputs are, and where the conversions happen

Raw fields only, from one archived capture: the market's nine `readState` words, the PY index,
and the block timestamp. `lastLnImpliedRate` and `lnFeeRateRoot` are logarithms; this file is
where they become rates, and that conversion is in the source rather than in the archive so a
reader can disagree with it.

**A capture without the PY index cannot be used.** Pendle's market maths takes it and
`readState` does not return it, so the market's own nine words are not sufficient to price a
trade. Captures taken before that read existed are refused -- judged by whether the field is
present, not by the capture's timestamp, because a timestamp rule would quietly admit a
capture that happens to be new and short the field.

The PY index for this market currently reads exactly 1.0, which is the trap: a quantity that
equals one looks like a quantity that can be left out. It is multiplied in explicitly so that
the day it stops being one, nothing has to be remembered.

## Pre-expiry only

Before expiry an exit is a trade against this curve. After it, PT redeems and the question
becomes the redemption path. Those are two different quantities and this file computes only
the first: a capture at or after expiry exits 3 with that said, rather than returning a
number under the same label.

## Three self-checks, and what none of them establishes

1. **As the size goes to zero, recovery goes to one minus the fee.** The curve's own limit,
   independent of every state field but the fee root.
2. **Recovery falls monotonically as size grows.** Selling PT pushes the market's PT
   proportion up, which raises the exchange rate, which lowers the payout.
3. **The pre-trade marginal rate equals `exp(lastLnImpliedRate x timeToExpiry / 365d)`.** This
   is an identity: the rate anchor is defined by subtracting the log-proportion term and the
   marginal rate adds it back, so the reserves cancel and the stored implied rate is what is
   left. It ties the implementation to a field the market wrote itself.

**None of the three establishes that this matches Pendle's deployed contract.** 1 and 2 are
properties of the formula, so a formula that is wrong in the same way everywhere satisfies
both. 3 catches an inconsistency between the anchor and the rate but not an error made
identically in both -- flip the sign in one and it fires; flip it in both and the identity
still holds. What would establish the match is an independent evaluation, and neither one is
available here: the market's swap entry point reverts under `eth_call` because it requires PT
to be transferred in first, and both markets on this chain are nearly inactive -- the live one
has not emitted an event since block 83,458,608 -- so there is no recent trade to replay
against. The logs that do exist are archived in `measurements/pendle-market-logs/`, and
reconstructing the state they occurred at is a separate piece of work that has not been done.

So the standing of any number this file prints is: **the published formula, evaluated on an
archived state, not validated against any executed trade.** That sentence travels with the
artifact.

## Arithmetic

The contract evaluates this in 1e18 fixed point with Balancer's `LogExpMath`; this evaluates
it in 60-digit decimal. The difference is rounding in the last places and is not modelled. A
size the contract would refuse is refused here too: the market reverts above a PT proportion
of 0.96, and such a size is reported as a refusal rather than as a low recovery, because "the
market will not quote this" and "the market quotes this badly" are different findings.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from decimal import Decimal, getcontext

getcontext().prec = 60

WAD = Decimal(10) ** 18
IMPLIED_RATE_TIME = Decimal(365 * 24 * 3600)
MAX_PROPORTION = Decimal("0.96")           # MarketMathCore's MAX_MARKET_PROPORTION
ONE = Decimal(1)
PASS, FAIL, NOT_EXERCISED = 0, 1, 3

STATE_WORDS = ("totalPt", "totalSy", "totalLp", "treasury", "scalarRoot", "expiry",
               "lnFeeRateRoot", "reserveFeePercent", "lastLnImpliedRate")
DEFAULT_SIZES = ("1", "10", "100", "1000", "10000", "50000", "100000", "200000", "400000")
# The clock the reference column is computed at. A convention, not a measurement: thirty days
# is far enough out that the curve has not yet collapsed onto the fee, and it is declared in
# every artifact so a reader comparing two artifacts can check they share it.
REFERENCE_SECONDS = 30 * 24 * 3600


def log_proportion(p: Decimal) -> Decimal:
    """ln(p / (1 - p)) -- MarketMathCore._logProportion."""
    return (p / (ONE - p)).ln()


class Market:
    """One capture's state, in units of whole tokens rather than 1e18 fixed point."""

    def __init__(self, words: dict, py_index_raw: str, block_time: int):
        def wad(name: str) -> Decimal:
            return Decimal(int(words[name], 16)) / WAD
        self.total_pt = wad("totalPt")
        self.total_sy = wad("totalSy")
        self.scalar_root = wad("scalarRoot")
        self.ln_fee_rate_root = wad("lnFeeRateRoot")
        self.last_ln_implied_rate = wad("lastLnImpliedRate")
        self.expiry = int(words["expiry"], 16)
        self.reserve_fee_percent = Decimal(int(words["reserveFeePercent"], 16))
        self.py_index = Decimal(int(py_index_raw, 16)) / WAD
        self.block_time = block_time
        self.time_to_expiry = self.expiry - block_time

    # ── the curve ──────────────────────────────────────────────────────────────────────
    def at_reference_clock(self, seconds_to_expiry: int) -> "Market":
        """The same reserves, read as if this many seconds remained. A counterfactual, and
        labelled as one: it exists so a series across captures compares the book rather than
        the calendar."""
        other = object.__new__(Market)
        other.__dict__.update(self.__dict__)
        other.block_time = self.expiry - seconds_to_expiry
        other.time_to_expiry = seconds_to_expiry
        return other

    def precompute(self, mutate: frozenset = frozenset()) -> dict:
        t = Decimal(self.time_to_expiry)
        rate_scalar = self.scalar_root * IMPLIED_RATE_TIME / t
        total_asset = self.total_sy * self.py_index          # syToAsset
        marginal_rate_from_stored = (self.last_ln_implied_rate * t / IMPLIED_RATE_TIME).exp()
        proportion0 = self.total_pt / (self.total_pt + total_asset)
        lnp0 = log_proportion(proportion0)
        if "anchor_sign_flipped" in mutate:
            rate_anchor = marginal_rate_from_stored + lnp0 / rate_scalar
        else:
            rate_anchor = marginal_rate_from_stored - lnp0 / rate_scalar
        fee_rate = (self.ln_fee_rate_root * t / IMPLIED_RATE_TIME).exp()
        if "fee_applied_twice" in mutate:
            fee_rate = fee_rate * fee_rate
        return {"rate_scalar": rate_scalar, "total_asset": total_asset,
                "rate_anchor": rate_anchor, "fee_rate": fee_rate,
                "proportion0": proportion0,
                "marginal_rate_from_stored": marginal_rate_from_stored}

    def exchange_rate(self, comp: dict, net_pt_to_account: Decimal,
                      mutate: frozenset = frozenset()) -> Decimal:
        """MarketMathCore._getExchangeRate. Raises ValueError where the contract reverts."""
        if "rate_constant" in mutate:
            net_pt_to_account = Decimal(0)
        numerator = self.total_pt - net_pt_to_account
        proportion = numerator / (self.total_pt + comp["total_asset"])
        if proportion > MAX_PROPORTION:
            raise ValueError(f"market proportion would reach {proportion:.6f}, above the "
                             f"{MAX_PROPORTION} cap the market reverts on -- no quote exists "
                             f"for this size")
        rate = log_proportion(proportion) / comp["rate_scalar"] + comp["rate_anchor"]
        if rate < ONE:
            raise ValueError(f"exchange rate {rate:.9f} below one, which the market reverts "
                             f"on -- no quote exists for this size")
        return rate

    def sell_pt(self, comp: dict, size_pt: Decimal,
                mutate: frozenset = frozenset()) -> dict:
        """Proceeds of selling size_pt PT into the market, in asset and in SY."""
        rate = self.exchange_rate(comp, -size_pt, mutate)
        pre_fee_asset = size_pt / rate
        net_asset = pre_fee_asset / comp["fee_rate"]          # the sell branch of calcTrade
        fee_asset = pre_fee_asset - net_asset
        return {"rate": rate, "pre_fee_asset": pre_fee_asset, "net_asset": net_asset,
                "fee_asset": fee_asset,
                "reserve_asset": fee_asset * self.reserve_fee_percent / Decimal(100),
                "net_sy": net_asset / self.py_index}

    def row(self, comp: dict, size_pt: Decimal, mutate: frozenset = frozenset()) -> dict:
        """One ladder row: the claim, the second quantity, and the refusals."""
        marginal_rate = self.exchange_rate(comp, Decimal(0), mutate)
        try:
            q = self.sell_pt(comp, size_pt, mutate)
        except ValueError as exc:
            return {"size_pt": str(size_pt), "quoted": False, "refused_because": str(exc),
                    "size_as_fraction_of_totalPt": str(
                        (size_pt / self.total_pt).quantize(Decimal("0.000001")))}
        # (a) the claim: proceeds against the market's own pre-trade marginal quote.
        recovery = q["net_asset"] * marginal_rate / size_pt
        # (b) the second quantity: proceeds against PT's face value of one asset per PT.
        #     Reported, labelled, never the claim -- it rises towards 1 with the clock.
        face = q["net_asset"] / size_pt
        return {
            "size_pt": str(size_pt), "quoted": True,
            "size_as_fraction_of_totalPt": str(
                (size_pt / self.total_pt).quantize(Decimal("0.000001"))),
            "recovery_pct": str((recovery * 100).quantize(Decimal("0.000001"))),
            "proceeds_vs_face_value_pct": str((face * 100).quantize(Decimal("0.000001"))),
            "exchange_rate_after": str(q["rate"].quantize(Decimal("0.000000001"))),
            "proceeds_sy": str(q["net_sy"].quantize(Decimal("0.000000001"))),
            "fee_asset": str(q["fee_asset"].quantize(Decimal("0.000000001"))),
            "to_reserve_asset": str(q["reserve_asset"].quantize(Decimal("0.000000001"))),
        }


# ── self-checks ──────────────────────────────────────────────────────────────────────────
def self_checks(m: Market, comp: dict, rows: list, mutate: frozenset = frozenset(),
                reference_seconds: int = REFERENCE_SECONDS,
                ref_rows: list | None = None) -> list[dict]:
    out = []

    # 1. size -> 0 gives one minus the fee.
    tiny = m.total_pt / Decimal(10) ** 12
    limit = m.row(comp, tiny, mutate)
    # 🔴 The expectation is rebuilt from the market's raw lnFeeRateRoot, NOT read out of
    #    comp. Taking it from comp would compare the curve against the same number the curve
    #    used, so a wrong fee would satisfy the check -- which is what happened the first
    #    time this drill was run: the fee-applied-twice arm passed.
    want = ONE / (m.ln_fee_rate_root * Decimal(m.time_to_expiry)
                  / IMPLIED_RATE_TIME).exp() * 100
    got = Decimal(limit["recovery_pct"]) if limit["quoted"] else None
    ok1 = got is not None and abs(got - want) < Decimal("0.000001")
    out.append({"check": "limit_at_zero_size_is_one_minus_fee", "ok": ok1,
                "detail": f"recovery at {tiny:.3e} PT = "
                          f"{'refused' if got is None else f'{got:.9f}%'}, one minus the fee "
                          f"rebuilt from lnFeeRateRoot = {want:.9f}%",
                "boundary": "a property of the formula; it is satisfied by any formula wrong "
                            "in the same way at every size. It does catch a wrong fee, "
                            "because the fee it compares against is recomputed from the raw "
                            "state field rather than taken from the precompute"})

    # 2. monotone decreasing over the sizes that were quoted.
    q = [(Decimal(r["size_pt"]), Decimal(r["recovery_pct"])) for r in rows if r["quoted"]]
    breaks = [(a[0], b[0]) for a, b in zip(q, q[1:]) if b[1] >= a[1]]
    ok2 = len(q) >= 2 and not breaks
    out.append({"check": "recovery_falls_as_size_grows", "ok": ok2,
                "detail": (f"{len(q)} quoted sizes, "
                           + ("strictly decreasing" if not breaks else
                              f"not decreasing between {breaks[0][0]} and {breaks[0][1]} PT"))
                if len(q) >= 2 else f"only {len(q)} quoted size(s): nothing to compare",
                "boundary": "orders the rows against each other and says nothing about "
                            "whether any one of them is right"})

    # 3. the pre-trade marginal rate is the stored implied rate.
    try:
        r0 = m.exchange_rate(comp, Decimal(0), mutate)
        delta = abs(r0 - comp["marginal_rate_from_stored"])
        ok3 = delta < Decimal("1e-30")
        detail = (f"marginal rate {r0:.18f} vs exp(lastLnImpliedRate x t / 365d) "
                  f"{comp['marginal_rate_from_stored']:.18f}, difference {delta:.3e}")
    except ValueError as exc:
        ok3, detail = False, f"no marginal rate: {exc}"
    out.append({"check": "marginal_rate_equals_stored_implied_rate", "ok": ok3,
                "detail": detail,
                "boundary": "ties the rate anchor to the rate function; an error made "
                            "identically in both still satisfies it"})

    # 4. the clock control is actually wired. Nearer expiry must recover more at the same
    #    reserves: rateScalar goes as 1/timeToExpiry and the fee rate grows with it, so both
    #    push the same way. A reference column that silently equalled the measured one would
    #    look like a depth series and be a calendar series, which is the error this whole
    #    column exists to prevent -- so it is checked rather than assumed.
    pairs = [(Decimal(a["recovery_pct"]), Decimal(b["recovery_pct"]))
             for a, b in zip(rows, ref_rows or []) if a["quoted"] and b["quoted"]]
    dt_sign = (reference_seconds > m.time_to_expiry) - (reference_seconds < m.time_to_expiry)
    if not pairs:
        ok4, detail4 = False, "no size was quoted at both clocks, so nothing was compared"
    elif dt_sign == 0:
        ok4 = all(a == b for a, b in pairs)
        detail4 = (f"the capture sits exactly at the reference clock "
                   f"({reference_seconds:,} s), so the two columns must be identical and "
                   f"{'are' if ok4 else 'are not'}")
    else:
        want_higher_measured = dt_sign > 0          # reference further out => measured higher
        # 🔴 A tie counts as a failure. The clocks differ, so the fee rate alone guarantees
        #    the two columns differ -- two equal columns mean the reference was computed at
        #    the capture's own clock and is controlling for nothing. Exempting ties is how
        #    this check passed a deliberately disabled control the first time it was drilled.
        bad = [(a, b) for a, b in pairs if (a > b) != want_higher_measured]
        ok4 = not bad
        detail4 = (f"capture at {m.time_to_expiry:,} s to expiry, reference at "
                   f"{reference_seconds:,} s; measured recovery is "
                   f"strictly {'above' if want_higher_measured else 'below'} the reference "
                   f"at {len(pairs) - len(bad)}/{len(pairs)} sizes")
    out.append({"check": "clock_control_moves_the_curve", "ok": ok4, "detail": detail4,
                "boundary": "shows the reference column is computed at a different clock and "
                            "in the right direction. It does not establish that the reference "
                            "clock is the right one to compare at -- that is a convention, "
                            "and it is declared in the artifact rather than derived"})
    return out


def compute(m: Market, sizes: list, mutate: frozenset = frozenset(),
            reference_seconds: int = REFERENCE_SECONDS) -> dict:
    comp = m.precompute(mutate)
    rows = [m.row(comp, Decimal(s), mutate) for s in sizes]
    # "clock_ignored" is a drill mutation: the reference column is computed at the capture's
    # own clock, which is how this column would silently stop controlling for anything.
    ref = m if "clock_ignored" in mutate else m.at_reference_clock(reference_seconds)
    ref_comp = ref.precompute(mutate)
    ref_rows = [ref.row(ref_comp, Decimal(s), mutate) for s in sizes]
    for r, rr in zip(rows, ref_rows):
        r["recovery_pct_at_reference_clock"] = (rr["recovery_pct"] if rr["quoted"]
                                                else "refused")
    checks = self_checks(m, comp, rows, mutate, reference_seconds, ref_rows)
    return {"comp": comp, "rows": rows, "checks": checks,
            "reference_seconds": reference_seconds,
            "reference_comp": ref_comp, "reference_rows": ref_rows}


# ── running it on a capture ──────────────────────────────────────────────────────────────
def load_capture(path: str) -> tuple[Market | None, dict, str]:
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, {}, f"{path}: unreadable as JSON ({exc})"
    words = d.get("readState_words_raw") or {}
    missing = [w for w in STATE_WORDS if w not in words]
    if missing:
        return None, d, (f"{path}: the capture does not carry readState's words "
                         f"{missing} -- it cannot price anything")
    # 🔴 Judged by field presence, not by the capture's date: a timestamp rule would admit a
    #    new capture that happens to be short the field, which is exactly how this read came
    #    to be missing from the first two captures.
    py = (d.get("pricing_inputs_raw") or {}).get("yt_pyIndexCurrent") or ""
    if not py:
        return None, d, (f"{path}: no PY index in this capture. Pendle's market maths takes "
                         f"one and readState does not return it, so the market's nine words "
                         f"are not enough to price a trade. The analysable series starts at "
                         f"the first capture that carries the field")
    if "block_timestamp" not in d:
        return None, d, f"{path}: no block_timestamp, so time to expiry cannot be formed"
    m = Market(words, py, int(d["block_timestamp"]))
    if m.time_to_expiry <= 0:
        return None, d, (f"{path}: captured at or after expiry (block timestamp "
                         f"{dt.datetime.utcfromtimestamp(m.block_time).isoformat()}Z, expiry "
                         f"{dt.datetime.utcfromtimestamp(m.expiry).isoformat()}Z). Before "
                         f"expiry an exit is a trade against this curve; after it, PT redeems "
                         f"and the question is the redemption path. This file computes the "
                         f"first only, and will not publish the second under the same label")
    return m, d, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--sizes", default=",".join(DEFAULT_SIZES))
    ap.add_argument("--reference-days", type=float, default=30.0,
                    help="the clock the reference column is pinned at; declared in the "
                         "artifact, because two artifacts are only comparable if it matches")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.capture:
        print("--capture is required (or --selftest)", file=sys.stderr)
        return NOT_EXERCISED

    m, cap, why = load_capture(a.capture)
    if m is None:
        print(f"NOT EXERCISED  {why}", file=sys.stderr)
        return NOT_EXERCISED
    sizes = [s.strip() for s in a.sizes.split(",") if s.strip()]
    ref_seconds = int(a.reference_days * 86400)
    res = compute(m, sizes, reference_seconds=ref_seconds)
    comp, rows, checks = res["comp"], res["rows"], res["checks"]

    print(f"{a.capture}")
    print(f"  block {cap.get('block_number'):,} · "
          f"{dt.datetime.utcfromtimestamp(m.block_time).isoformat()}Z · "
          f"{m.time_to_expiry:,} s to expiry "
          f"({dt.datetime.utcfromtimestamp(m.expiry).isoformat()}Z)")
    print(f"  totalPt {m.total_pt:,.6f} · totalSy {m.total_sy:,.6f} · PY index {m.py_index} · "
          f"fee rate {comp['fee_rate']:.9f} · PT proportion {comp['proportion0']:.9f}")
    print(f"\n  {'size (PT)':>12} {'of totalPt':>11} {'recovery %':>13} "
          f"{f'at {a.reference_days:g}d clock':>16} {'vs face %':>11} {'rate after':>12}")
    for r in rows:
        if r["quoted"]:
            print(f"  {r['size_pt']:>12} {r['size_as_fraction_of_totalPt']:>11} "
                  f"{r['recovery_pct']:>13} "
                  f"{r['recovery_pct_at_reference_clock']:>16} "
                  f"{r['proceeds_vs_face_value_pct']:>11} "
                  f"{r['exchange_rate_after']:>12}")
        else:
            print(f"  {r['size_pt']:>12} {r['size_as_fraction_of_totalPt']:>11} "
                  f"{'refused':>13}   {r['refused_because'][:52]}")
    print()
    for c in checks:
        print(f"  {'ok ' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    bad = [c["check"] for c in checks if not c["ok"]]

    if a.out_dir:
        art = {
            "_what": "The pre-expiry exit curve of one Pendle PT market, computed by "
                     "code/pendle_pt_exit_curve.py from the archived capture named below. "
                     "Every input is a raw field from that capture; every conversion is in "
                     "that file.",
            "_claim": "recovery_pct is proceeds from selling N PT divided by N times the "
                      "market's own pre-trade marginal quote, at the same block. Nothing "
                      "outside the market enters either side.",
            "_second_quantity": "proceeds_vs_face_value_pct is the same proceeds against PT's "
                                "face value of one asset per PT. It is NOT the claim: it "
                                "rises towards 100% as expiry approaches regardless of depth, "
                                "because the discount PT trades at shrinks with the remaining "
                                "time. Reading it as a depth improvement is the same error as "
                                "quoting an annualised implied rate near maturity.",
            "_standing": "the published formula evaluated on an archived state, NOT validated "
                         "against any executed trade. The market's swap entry point reverts "
                         "under eth_call because it requires PT transferred in first, and "
                         "this market has been nearly inactive, so no recent trade exists to "
                         "replay against. See measurements/pendle-market-logs/ for the logs "
                         "that do exist; reconstructing the state they occurred at has not "
                         "been done.",
            "capture": os.path.basename(a.capture),
            "market": cap.get("market"), "block_number": cap.get("block_number"),
            "block_hash": cap.get("block_hash"), "block_timestamp": m.block_time,
            "expiry": m.expiry, "seconds_to_expiry": m.time_to_expiry,
            "inputs_raw": {k: (cap.get("readState_words_raw") or {}).get(k)
                           for k in STATE_WORDS},
            "py_index_raw": (cap.get("pricing_inputs_raw") or {}).get("yt_pyIndexCurrent"),
            "derived": {k: str(comp[k]) for k in
                        ("rate_scalar", "total_asset", "rate_anchor", "fee_rate",
                         "proportion0", "marginal_rate_from_stored")},
            "_clock_control": "recovery_pct is this block's number and is the one to quote "
                              "for this block. It is NOT clock-free: rateScalar is "
                              "scalarRoot x 365d / timeToExpiry, so the curve flattens as "
                              "expiry approaches and recovery rises with nothing happening "
                              "to the book. recovery_pct_at_reference_clock recomputes each "
                              "row with the same reserves at reference_seconds_to_expiry, "
                              "which pins the calendar so a series across captures compares "
                              "the book. A series built from recovery_pct instead would read "
                              "a market walking towards expiry as a market getting deeper.",
            "reference_seconds_to_expiry": res["reference_seconds"],
            "reference_derived": {k: str(res["reference_comp"][k]) for k in
                                  ("rate_scalar", "rate_anchor", "fee_rate")},
            "rows": rows, "self_checks": checks,
            "arithmetic_note": "60-digit decimal; the contract uses 1e18 fixed point with "
                               "Balancer LogExpMath, so figures can differ in the last "
                               "places and that difference is not modelled. A size above the "
                               "market's 0.96 PT-proportion cap is a refusal, not a low "
                               "recovery: the market would revert.",
        }
        out = os.path.abspath(a.out_dir)
        os.makedirs(out, exist_ok=True)
        name = f"curve-{cap.get('block_number')}.json"
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(art, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"  wrote {os.path.join(a.out_dir, name)}")

    if bad:
        print(f"\nself-check failed: {bad}", file=sys.stderr)
        return FAIL
    return PASS


# ── drill ────────────────────────────────────────────────────────────────────────────────
# Five arms over one synthetic state. The arms must DISAGREE: a drill whose clean arm and
# broken arms all come out the same cannot tell a working curve from a broken one, and each
# break must be named by a different check -- otherwise one check is doing all the work and
# the others are decoration.
def _stub_words(expiry: int) -> dict:
    def w(x: int) -> str:
        return "0x" + f"{x:064x}"
    return {"totalPt": w(431957 * 10 ** 18), "totalSy": w(241801 * 10 ** 18),
            "totalLp": w(314902 * 10 ** 18), "treasury": w(0),
            "scalarRoot": w(23985056794157100995), "expiry": w(expiry),
            "lnFeeRateRoot": w(7968169649176873), "reserveFeePercent": w(80),
            "lastLnImpliedRate": w(115426772510134633)}


def selftest() -> int:
    t0 = 1_792_000_000
    m = Market(_stub_words(1_792_627_200), "0x" + f"{10**18:064x}", t0)
    sizes = list(DEFAULT_SIZES)
    arms, outcomes = [], {}

    for name, mutate in (("clean", frozenset()),
                         ("anchor_sign_flipped", frozenset({"anchor_sign_flipped"})),
                         ("rate_constant", frozenset({"rate_constant"})),
                         ("fee_applied_twice", frozenset({"fee_applied_twice"})),
                         ("clock_ignored", frozenset({"clock_ignored"}))):
        res = compute(m, sizes, mutate)
        failed = [c["check"] for c in res["checks"] if not c["ok"]]
        code = FAIL if failed else PASS
        arms.append((name, code, failed))
        outcomes[name] = (code, tuple(failed))
        print(f"  arm {name:<20} exit {code} · failing checks {failed or '-'}")

    expired, _, why = load_capture_stub(1_792_000_000 - 1)
    print(f"  arm {'post_expiry':<20} exit {NOT_EXERCISED} · {why[:88]}")
    arms.append(("post_expiry", NOT_EXERCISED, ["<refused before computing>"]))

    problems = []
    if outcomes["clean"][0] != PASS:
        problems.append(f"the clean arm did not pass: {outcomes['clean'][1]}")
    for broken in ("anchor_sign_flipped", "rate_constant", "fee_applied_twice",
                   "clock_ignored"):
        if outcomes[broken][0] != FAIL:
            problems.append(f"arm {broken} was not caught")
    named = {k: outcomes[k][1] for k in ("anchor_sign_flipped", "rate_constant",
                                         "fee_applied_twice", "clock_ignored")}
    if len({v for v in named.values()}) != 4:
        problems.append(f"two broken arms are caught by the same check(s): {named} -- one "
                        f"check is doing the work of several")
    if len({c for _, c, _ in arms}) < 3:
        problems.append("the arms do not produce three distinct exit codes")
    if problems:
        print("\nselftest FAILED", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return FAIL
    print("\nselftest: passed -- every break is caught, each by a different check, and the "
          "arms produce three distinct exit codes")
    return PASS


def load_capture_stub(block_time: int) -> tuple[Market | None, dict, str]:
    """A capture whose block time is past expiry, written to a temp file so the real
    loader -- not a copy of its logic -- is what refuses it."""
    import tempfile
    cap = {"readState_words_raw": _stub_words(block_time - 1),
           "pricing_inputs_raw": {"yt_pyIndexCurrent": "0x" + f"{10**18:064x}"},
           "block_timestamp": block_time, "block_number": 1}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(cap, fh)
        path = fh.name
    try:
        return load_capture(path)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    sys.exit(main())
