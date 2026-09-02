#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

START_DEFAULT = date(1999, 6, 3)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def find_csv(out_dir: Path) -> Path | None:
    exact = out_dir / "ticks.csv"
    if exact.exists():
        return exact
    csvs = sorted(out_dir.glob("*.csv"), key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    return csvs[0] if csvs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--from", dest="start", default=str(START_DEFAULT))
    ap.add_argument("--to", dest="end", default=None, help="inclusive UTC date; default last complete UTC day")
    ap.add_argument("--symbol", default="xauusd")
    ap.add_argument("--smoke", action="store_true", help="download only first requested day")
    args = ap.parse_args()

    base = Path(args.base).expanduser().resolve()
    duka = base / "node/node_modules/.bin/dukascopy-node"
    if not duka.exists():
        raise SystemExit(f"dukascopy-node missing: {duka}")
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else datetime.now(timezone.utc).date() - timedelta(days=1)
    if args.smoke:
        end = start
    cache = base / "cache/dukascopy"
    cache.mkdir(parents=True, exist_ok=True)
    summary = []

    for d in daterange(start, end):
        nxt = d + timedelta(days=1)
        out = base / "data/raw" / args.symbol / f"year={d.year:04d}" / f"month={d.month:02d}" / f"day={d.day:02d}"
        out.mkdir(parents=True, exist_ok=True)
        manifest = out / "manifest.json"
        if manifest.exists():
            try:
                old = json.loads(manifest.read_text())
                cp = out / old.get("csv_name", "ticks.csv")
                if old.get("status") in {"ok", "empty"} and cp.exists() and old.get("sha256") == sha256(cp):
                    summary.append(old)
                    print(d, old.get("status"), "resume")
                    continue
            except Exception:
                pass

        for p in out.glob("*.csv"):
            p.unlink()
        cmd = [
            str(duka), "-i", args.symbol, "-from", str(d), "-to", str(nxt),
            "-t", "tick", "-f", "csv", "-dir", str(out), "-fn", "ticks.csv",
            "-r", "5", "-rp", "1500", "-ch", "-chpath", str(cache),
        ]
        p = subprocess.run(cmd, cwd=base / "node", text=True, capture_output=True)
        csv_path = find_csv(out)
        rec = {
            "symbol": args.symbol, "date_utc": str(d), "from_utc": str(d), "to_utc_exclusive": str(nxt),
            "returncode": p.returncode, "stdout_tail": p.stdout[-3000:], "stderr_tail": p.stderr[-3000:],
        }
        if p.returncode != 0:
            rec["status"] = "download_error"
        elif csv_path is None:
            rec["status"] = "empty"
            csv_path = out / "ticks.csv"
            csv_path.write_text("timestamp,askPrice,bidPrice,askVolume,bidVolume\n")
        else:
            lines = csv_path.read_text(encoding="utf-8", errors="replace").splitlines()
            rec["header"] = lines[0] if lines else ""
            rec["first_rows"] = lines[1:4]
            rec["rows_approx"] = max(0, len(lines) - 1)
            rec["status"] = "ok" if len(lines) > 1 else "empty"
        rec["csv_name"] = csv_path.name
        rec["bytes"] = csv_path.stat().st_size
        rec["sha256"] = sha256(csv_path)
        manifest.write_text(json.dumps(rec, indent=2, sort_keys=True))
        summary.append(rec)
        print(d, rec["status"], rec.get("rows_approx", 0))

    sm = base / "manifests/xauusd_download_summary.json"
    sm.parent.mkdir(parents=True, exist_ok=True)
    sm.write_text(json.dumps(summary, indent=2, sort_keys=True))
    bad = [r for r in summary if r.get("status") == "download_error"]
    print(json.dumps({"days": len(summary), "bad": len(bad), "summary": str(sm)}, indent=2))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
