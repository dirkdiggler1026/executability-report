# The multiplier is published. When it changes is not.

**Three public endpoints the issuer operates, read 2026-09-29, against the chain.** The
question this settles is not "can the multiplier be found" — it can, three ways — but
**whether anything tells you it moved**, which is the only part an integrator cannot work
around.

---

## 1. What is published, and it agrees with the chain exactly

```
GET https://api.robinhood.com/rhj/assets                 195 assets, no key, no pagination
GET https://api.robinhood.com/rhj/corporate-actions      51 rows, all CASH_DIVIDEND
GET https://api.robinhood.com/rhj/price-deviations       2 rows, as of 2026-09-28
```

`assets` carries `currentMultiplier` per asset. For all nine symbols this project tracks it
equals `uiMultiplier()` on chain **to the last digit** — so the API, the getter, and the ratio
of the two amounts in a transfer log are one number reached three ways, not three estimates.

## 2. The change itself, located to a single block

`uiMultiplier()` needs no transfer, so it binary-searches to one block. The transfer-log route
can only bracket to the nearest pair of transfers — for QQQ that was 32 seconds; the getter
gives one second.

```
            multiplier              first block at new value     UTC
GOOGL   1.0 -> 1.000193924414112587        63,752,473        2026-09-15 15:10:27
NVDA    1.0 -> 1.000775159164630595        58,958,493        2026-09-10 00:00:30
SPY     1.0 -> 1.001717991187472003        65,785,791        2026-09-18 00:10:33
QQQ     1.0 -> 1.000700791241405425        69,216,816        2026-09-22 00:10:34
AAPL      1.000566080061092436 throughout   — already above 1 on 2026-09-01
TSLA, AMC, GME, RDDT     exactly 1.0 throughout
```

Each bracketed to **one block, one second**, over the window 51,274,668 – 75,336,022
(2026-09-01 to 2026-09-29).

## 3. 🔴 Nothing announces it

```
on chain    over blocks 69,216,800–69,217,140 — 340 blocks spanning the QQQ change —
            the token emitted FOUR logs: two Transfers and their two companion logs.
            No event. (Public endpoint, no key, so this half is reproducible by anyone.)

off chain   the corporate-actions feed publishes a processDate, and it is not the date
            the multiplier moves:
              GOOGL   processDate 2026-09-14   multiplier moved 09-15      +1 day
              NVDA    processDate 2026-10-01   multiplier moved 09-10     -21 days
              QQQ     processDate 2026-10-08   multiplier moved 09-22     -16 days
              SPY     no entry in the feed at all, and it moved 09-18

            `assets` has a `pendingMultiplier` field. On 2026-09-29 it is EMPTY for
            all 195 assets, including NVDA whose process date is two days away.
```

⚠️ **What this does not say.** The offsets above are consistent with a multiplier that moves
on one date in a dividend's life and a feed that publishes another — that would be ordinary,
not wrong. We do not have the underlying dividend calendar and are not guessing at which date
is which. The measured claim is narrower and is enough: **no published date coincides with the
change, and no published field carried advance notice on the day we looked.**

## 4. Why a snapshot cannot finish this, and what is now running

`pendingMultiplier` being empty today does not establish that it is never populated. That
question has one shape of answer — watch the field across a change — and it cannot be answered
retrospectively, because the endpoint has no history and none is published.

Two process dates fall within days: **NVDA 2026-10-01** and **QQQ 2026-10-08**. A two-hourly
snapshot of all three endpoints started 2026-09-29 14:49 UTC (`code/collect_rhj_assets.py`,
canon `rhj-issuer-feed-v1`), recording the raw body and its sha256 each run so a gap is
distinguishable from a quiet day. The window opens now and does not reopen — the same reason
this project records rather than reconstructs.

## 5. The deviation feed, for completeness

Their published test: a deviation is disclosed when the on-chain price differs from the
underlying's reference by **5% or more for seven consecutive trading days**, assessed at each
business day's close, NYSE closing price benchmarked to the nearest block against a trailing
seven-day on-chain average. As of 2026-09-28 it lists two:

```
SATS   NYSE 89.22   on-chain 1,440.89    +1,514.99%  premium   11 consecutive days
WEEK   NYSE 100.04  on-chain 49.90         -50.12%   discount  11 consecutive days
```

Both first observed 2026-09-14. The test is working and it is publishing.

🔴 It is a **price** test, and price is not the thing this project measures. QQQ's mid is not
deviating — a $10,000 sell recovers 1.93% of mid and a $100,000 sell recovers 0.03%
(`measurements/oneside-depth/`). A token can be priced correctly to the last cent and still be
unsellable at size, and a 5%/7-day price test is structurally unable to see that. **That is
not a defect in their test** — it measures what it says it measures. It is the reason the two
measurements are not substitutes.

## Files

```
rhj-2026-09-29T144925Z.json          all three endpoints, raw bodies and sha256
uimultiplier-call-...json            the getter, the historical reads, the bisection,
                                     and the event scan   (see ../accrual-multiplier/)
code/collect_rhj_assets.py           the snapshotter now running two-hourly
code/read_ui_multiplier.py           the getter/bisect/event-scan program
```
