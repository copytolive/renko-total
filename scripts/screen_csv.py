#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from copytolive_renko.io import load_ticks_csv
from copytolive_renko.search import candidate_grid,screen

def ints(spec):
    if ":" in spec:
        a,b,s=(int(x) for x in spec.split(":")); return list(range(a,b+1,s))
    return [int(x) for x in spec.split(",") if x.strip()]
def safe(x):
    if isinstance(x,float) and not math.isfinite(x): return None
    if isinstance(x,dict): return {k:safe(v) for k,v in x.items()}
    if isinstance(x,list): return [safe(v) for v in x]
    return x
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--price-unit",default="0.01")
    ap.add_argument("--bricks",default="10:100:10"); ap.add_argument("--confirms",default="1,2,3")
    ap.add_argument("--stops",default="1,2,3,4"); ap.add_argument("--takes",default="2,3,4,5,6")
    ap.add_argument("--quantity-oz",type=float,default=100.0); ap.add_argument("--cost-usd",type=float,default=0.0)
    ap.add_argument("--min-entry",type=int,default=100); ap.add_argument("--min-profit",type=float,default=20000.0)
    ap.add_argument("--top",type=int,default=100); ap.add_argument("--out",default="screen_results.json"); args=ap.parse_args()
    ticks=load_ticks_csv(args.csv,price_unit=args.price_unit)
    cand=candidate_grid(ints(args.bricks),ints(args.confirms),ints(args.stops),ints(args.takes))
    rows=screen(ticks,cand,min_entries=args.min_entry,min_net_profit=args.min_profit,top_n=args.top,
                price_unit=float(args.price_unit),quantity_oz=args.quantity_oz,costs_usd=args.cost_usd)
    Path(args.out).write_text(json.dumps(safe(rows),indent=2,allow_nan=False))
    print(json.dumps({"candidates":len(cand),"passed":len(rows),"output":args.out},indent=2))
if __name__=="__main__": main()
