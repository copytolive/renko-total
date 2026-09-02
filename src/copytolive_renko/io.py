from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .canonical import Tick, decimal_to_units

HEADER_ALIASES = {
    "timestamp": {"timestamp", "time", "date", "datetime"},
    "ask": {"askprice", "ask", "ask_price"},
    "bid": {"bidprice", "bid", "bid_price"},
    "ask_volume": {"askvolume", "ask_volume", "askvol", "ask_vol"},
    "bid_volume": {"bidvolume", "bid_volume", "bidvol", "bid_vol"},
}

def _norm(s: str) -> str:
    return "".join(ch for ch in s.strip().lower() if ch.isalnum() or ch == "_")

def map_headers(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ValueError("CSV has no header")
    by_norm = {_norm(x): x for x in fieldnames}
    out: dict[str, str] = {}
    for target, aliases in HEADER_ALIASES.items():
        for a in aliases:
            if _norm(a) in by_norm:
                out[target] = by_norm[_norm(a)]
                break
    for needed in ("timestamp", "ask", "bid"):
        if needed not in out:
            raise ValueError(f"required CSV column missing: {needed}; got {fieldnames}")
    return out

def parse_timestamp_ms(value: str) -> int:
    v = value.strip()
    if not v:
        raise ValueError("empty timestamp")
    try:
        n = Decimal(v)
        x = int(n)
        if x > 10**17:
            return x // 1_000_000
        if x > 10**14:
            return x // 1_000
        if x > 10**11:
            return x
        if x > 10**9:
            return x * 1000
    except Exception:
        pass
    from datetime import datetime, timezone
    s = v.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def load_ticks_csv(path: str | Path, *, price_unit: str = "0.01") -> list[Tick]:
    p = Path(path)
    out: list[Tick] = []
    with p.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        m = map_headers(reader.fieldnames)
        prev_ts = None
        for i, row in enumerate(reader):
            ts = parse_timestamp_ms(row[m["timestamp"]])
            if prev_ts is not None and ts < prev_ts:
                raise ValueError(f"non-monotonic timestamp at row {i + 2}")
            prev_ts = ts
            ask = decimal_to_units(row[m["ask"]], price_unit)
            bid = decimal_to_units(row[m["bid"]], price_unit)
            if ask < bid:
                raise ValueError(f"crossed quote at row {i + 2}: ask < bid")
            askv = float(row[m["ask_volume"]]) if m.get("ask_volume") and row.get(m["ask_volume"], "") else 0.0
            bidv = float(row[m["bid_volume"]]) if m.get("bid_volume") and row.get(m["bid_volume"], "") else 0.0
            out.append(Tick(i, ts, bid, ask, bidv, askv))
    return out

def ticks_to_rows(ticks: Iterable[Tick]) -> list[dict]:
    return [
        {"tick_id": t.tick_id, "timestamp_ms": t.timestamp_ms, "bid_units": t.bid_units,
         "ask_units": t.ask_units, "bid_volume": t.bid_volume, "ask_volume": t.ask_volume}
        for t in ticks
    ]
