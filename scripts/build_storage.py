#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from copytolive_renko.storage import csv_to_parquet_exact, build_duckdb_catalog


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("parquet"); p.add_argument("csv"); p.add_argument("out")
    d=sub.add_parser("duckdb"); d.add_argument("parquet_root"); d.add_argument("db")
    a=ap.parse_args()
    r=csv_to_parquet_exact(a.csv,a.out) if a.cmd=="parquet" else build_duckdb_catalog(a.parquet_root,a.db)
    print(json.dumps(r,indent=2))
if __name__=="__main__": main()
