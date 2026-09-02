from __future__ import annotations
from decimal import Decimal
from pathlib import Path
from .io import map_headers, parse_timestamp_ms

def csv_to_parquet_exact(csv_path: str | Path, parquet_path: str | Path) -> dict:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for Parquet conversion") from exc
    import csv
    src=Path(csv_path); dst=Path(parquet_path); dst.parent.mkdir(parents=True,exist_ok=True)
    ts=[]; asks=[]; bids=[]; askv=[]; bidv=[]
    with src.open(newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f); m=map_headers(reader.fieldnames)
        for row in reader:
            ts.append(parse_timestamp_ms(row[m["timestamp"]]))
            asks.append(Decimal(row[m["ask"]]))
            bids.append(Decimal(row[m["bid"]]))
            askv.append(float(row[m["ask_volume"]]) if m.get("ask_volume") and row.get(m["ask_volume"],"") else 0.0)
            bidv.append(float(row[m["bid_volume"]]) if m.get("bid_volume") and row.get(m["bid_volume"],"") else 0.0)
    table=pa.table({"timestamp_ms":pa.array(ts,type=pa.int64()),
                    "ask_price":pa.array(asks,type=pa.decimal128(20,10)),
                    "bid_price":pa.array(bids,type=pa.decimal128(20,10)),
                    "ask_volume":pa.array(askv,type=pa.float64()),
                    "bid_volume":pa.array(bidv,type=pa.float64())})
    pq.write_table(table,dst,compression="zstd",write_statistics=True,row_group_size=1_000_000)
    return {"rows":table.num_rows,"bytes":dst.stat().st_size,"path":str(dst)}

def build_duckdb_catalog(parquet_root: str | Path, db_path: str | Path) -> dict:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("duckdb is required") from exc
    root=Path(parquet_root); db=Path(db_path); db.parent.mkdir(parents=True,exist_ok=True)
    pattern=str(root/"year=*"/"month=*"/"day=*"/"ticks.parquet").replace("'","''")
    files=list(root.glob("year=*/month=*/day=*/ticks.parquet"))
    if not files:
        return {"files":0,"rows":0,"db":str(db)}
    con=duckdb.connect(str(db))
    con.execute(f"CREATE OR REPLACE VIEW xauusd_ticks AS SELECT * FROM read_parquet('{pattern}', hive_partitioning=true)")
    row=con.execute("SELECT COUNT(*), MIN(timestamp_ms), MAX(timestamp_ms), MIN(bid_price), MAX(bid_price) FROM xauusd_ticks").fetchone()
    con.close()
    return {"files":len(files),"rows":row[0],"first_timestamp_ms":row[1],"last_timestamp_ms":row[2],
            "min_bid":str(row[3]),"max_bid":str(row[4]),"db":str(db)}
