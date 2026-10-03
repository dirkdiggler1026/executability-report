# Wrapper multipliers: the same underlying, two issuers, two different numbers

Measured 2026-10-02 and 2026-10-03. Raw readings are the two JSON files in this directory;
`multiplier_crosschain.py` reproduces them.

Two token issuers wrap the same underlying US equities. Four tickers are common to the two sets of
tokens I hold addresses for: AAPL, GOOGL, NVDA and TSLA. Each token exposes the same getter,
`uiMultiplier()`, and the value it returns is not the same on both sides:

```
                 Coinbase-issued (Base)        Robinhood-issued (RH Chain)
  AAPL      1.000000000000000000  (+0.00 bp)   1.000566080061092436  (+5.66 bp)
  GOOGL     1.000377118676784179  (+3.77 bp)   1.000193924414112587  (+1.94 bp)
  NVDA      1.000537939576369481  (+5.38 bp)   1.000775159164630595  (+7.75 bp)
  TSLA      1.000000000000000000  (+0.00 bp)   1.000000000000000000  (+0.00 bp)
```

Three of the four differ, and the ordering is not consistent: for AAPL and NVDA the
Robinhood-issued wrapper reports the larger value, for GOOGL the Coinbase-issued one does. So this
is not one issuer reporting more than the other — it varies by underlying.

## Provenance

Both chains were read inside one run, four seconds apart, twice: at blocks 52,085,835 / 78,399,218
on 2026-10-02T17:10Z, and at blocks 52,108,456 / 78,846,673 on 2026-10-03T05:44Z, 12.6 hours later.
**None of the sixteen values changed in any digit between the two readings.**

On Base, the addresses were taken from the hub contract that lists and holds these assets — its
asset count reads 8 (seven equity wrappers plus one USDC reserve) — and cross-checked against an
on-chain index. They were not resolved by symbol: searching a symbol returns impostor tokens with
the same ticker. The RH Chain addresses come from `code/rhchain.py` in this repository. Both address
sets are in the data files next to this note.

## What this is not

It is not a price and it is not a fee: the multiplier is a claim ratio on the underlying, read from
the token. I am not attributing the difference — issue date, dividend history, withholding treatment
and fees are all folded into one number here, and this measurement does not separate them. The
stability claim covers exactly what was measured: two readings, 12.6 hours apart. It is not a claim
that the value only moves at corporate actions; thirteen hours cannot support that.

## Why it matters, mechanically

A balance is not a claim. Reading `balanceOf` without applying the token's own multiplier gives a
number that is wrong by the amount above, and the amount differs per wrapper and per underlying.

## Reproducing it

```
python3 multiplier_crosschain.py --selftest          # offline: selectors, decimal conversion, skew rule
RH_RPC=<your endpoint> python3 multiplier_crosschain.py --out mult-$(date -u +%Y%m%dT%H%MZ).json
```

The script reads both chains in one run and records each chain's block height and UTC time. If the
two reads are more than `--max-skew` seconds apart it labels the result `skew_exceeded` rather than
reporting a comparison, because the multiplier accrues over time: two readings taken on different
days differ by date, not by wrapper. A control check requires at least one token to read exactly
1.000000000000000000 on each chain — if none does, the fault is in the path, not in the issuer.

`evm.py` (keccak256) and `rhchain.py` (the RH address list) are in `code/` at the repository root.
