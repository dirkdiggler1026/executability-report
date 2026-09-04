# Executability — data and verification

Independent measurement of executable depth across on-chain aggregators,
tokenized stocks on Robinhood Chain, and prediction markets.

**Report:** https://dirkdiggler1026.github.io/executability-report/

## Contents

```
index.html    the report (single file, open in a browser)
data/         raw measurements
  2026-09-03/  2026-09-04/
    quotes.jsonl.gz   one row per quote
    rounds.jsonl      canonical hash per round
    MANIFEST.sha256   checksums
code/         collection and verification scripts
```

## This snapshot

Figures in the report correspond to **17 rounds, ending at block
53,861,286** (2026-09-03 17:09 → 09-04 UTC). Collection is ongoing, so
the data files here will grow past what the report describes. Existing
rounds never change.

Integrity check:

```bash
cd data/2026-09-03 && sha256sum -c MANIFEST.sha256
cd data/2026-09-04 && sha256sum -c MANIFEST.sha256
```

## Verify it yourself

Every tokenized-stock figure in the report can be recomputed
independently. You need an archive node for Robinhood Chain (historical
`eth_call`; public endpoints usually retain only ~128 blocks of state):

```bash
export RHCHAIN_RPC="https://<your archive endpoint>"
python3 code/verify.py 53579264      # first baseline round
python3 code/verify.py --latest
```

The script replays all quote calls at that block height, recomputes the
hash, and compares it against `rounds.jsonl`. A match proves the round's
data is unmodified.

## Canonical preimage `rhdepth-v1`

Only fields a third party can reproduce exactly at the same block are
hashed:

```
per line: block|sym|side|size_usd|poolId|amount_in_raw|amount_out_raw|status
integers as decimal strings (uint256 exceeds JS safe-integer range)
lines sorted lexicographically, joined with \n,
prefixed with "rhdepth-v1" on its own line, then keccak256
```

Timestamps, network latency and all derived floats are excluded. They
cannot be reproduced across runs or languages, and including them would
silently break the claim that anyone can recompute and check.

## Verifiable baseline

**Starts 2026-09-03 17:09 UTC, block 53,579,264.**

Earlier data (six rounds, 12:44–14:07) has a collection defect: the
quote calls in a round were not pinned to a single block height, so the
recorded block number does not match the state the data came from. That
batch is quarantined, is **not** included here, is not verifiable, and
supports no conclusion.

## Dependencies

None. `code/evm.py` is a from-scratch implementation (keccak-f[1600],
static ABI encoding, eth_call) needing only Python 3 and curl.

## Limits

- Quotes come from simulated Quoter calls, not executed trades. Real
  execution is affected by MEV, slippage protection and gas, and is
  generally worse.
- Tokenized stocks cover USDG-quoted pools only.
- The baseline spans hours, not weeks. It does not extrapolate across
  weekends or earnings windows.
