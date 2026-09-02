# Launch Status

## Code gates
- Canonical Renko core: implemented.
- Raw BID/ASK anti-lookahead replay: implemented.
- Metrics + Monte Carlo: implemented.
- Strategy grid screening: implemented.
- Dukascopy resumable downloader: implemented, requires smoke validation against installed CLI.
- Parquet/DuckDB storage: implemented, requires pyarrow/duckdb environment.
- Web viewer: implemented.
- Core golden tests: required PASS before release.

## Data gates still required on the user's Mac
- Confirm actual `dukascopy-node@1.50.0` CSV filename/header/timestamp semantics with a one-day XAUUSD smoke test.
- Audit coverage/gaps before claiming 1999-present total history.
- Generate audited Parquet/DuckDB history.
- Run OOS/correlation/finalist validation on real history.
- Do not publish synthetic sample metrics as live performance.
