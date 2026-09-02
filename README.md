# CopyToLive Renko Total — XAUUSD

Launch-oriented research stack for deterministic Renko construction and raw BID/ASK tick replay.

## What is included

- Canonical integer Renko kernel: fixed floor anchor, inclusive continuation, 2-brick reversal, multi-brick/tick, lineage.
- Anti-lookahead raw tick execution: BUY ASK/BID, SELL BID/ASK, entry strictly after signal tick.
- Metrics: entries, WR, PF, Net Profit, EV/trade, avg win/loss, Max DD, Recovery Factor, max consecutive loss, SQN, positive/worst year.
- Monte Carlo bootstrap DD/pass statistics.
- Parameter screening across brick/confirmation/SL/TP grids.
- Dukascopy XAUUSD daily resumable downloader wrapper.
- Exact Decimal128 Parquet archive + DuckDB catalog helpers.
- Static zero-backend web viewer for Renko/backtest JSON.
- Standard-library golden tests for core correctness.

## Public browser

Production browser: https://renko-total.vercel.app/\n\nGitHub Pages workflow is retained as an optional manual deployment path after Pages is enabled in repository settings.

GitHub Pages deploys the static viewer from `web/`. Public mode shows the deterministic sample/result viewer; local control buttons are only active when served by the included local server.

## Local browser control

The included `scripts/local_server.py` binds only to `127.0.0.1:5173` and exposes an allow-listed control API for:

- prepare Python/Node/Dukascopy stack,
- one-day XAUUSD smoke download,
- start/resume total history,
- run latest-CSV backtest,
- inspect local status/jobs.

No arbitrary shell endpoint is exposed.

## Local verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/build_sample.py
python3 -m http.server 8080 -d web
```

## Historical data pipeline

After `dukascopy-node@1.50.0` is installed under the project `node/` folder:

```bash
python3 scripts/download_xauusd.py --base . --from 2026-09-01 --to 2026-09-01 --smoke
```

Only after the smoke day is valid should total history run:

```bash
python3 scripts/download_xauusd.py --base . --from 1999-06-03
```

The downloader is resumable and excludes the current partial UTC day by default.

## Backtest one CSV

```bash
PYTHONPATH=src python3 scripts/run_csv_backtest.py ticks.csv \
  --price-unit 0.01 --brick 100 --sl-bricks 2 --tp-bricks 4 \
  --quantity-oz 100 --out web/data/latest.json
```

## Screening

```bash
PYTHONPATH=src python3 scripts/screen_csv.py ticks.csv \
  --bricks 50:500:50 --confirms 1,2,3 --stops 1,2,3,4 --takes 2,3,4,5,6 \
  --min-entry 100 --min-profit 20000 --out screen_results.json
```

A profitable historical result is not a promise of future returns. Production publication should include dataset coverage, costs, OOS, Monte Carlo, and correlation gates.
