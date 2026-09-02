#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from copytolive_renko.io import load_ticks_csv
from copytolive_renko import build_renko,reversal_signals,backtest_signals,summarize,monte_carlo
from copytolive_renko.canonical import bricks_to_dicts
from copytolive_renko.backtest import trades_to_dicts

def safe(x):
    if isinstance(x,float) and not math.isfinite(x): return None
    if isinstance(x,dict): return {k:safe(v) for k,v in x.items()}
    if isinstance(x,list): return [safe(v) for v in x]
    return x

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--price-unit",default="0.01")
    ap.add_argument("--brick",type=int,required=True); ap.add_argument("--confirm",type=int,default=1)
    ap.add_argument("--sl-bricks",type=int,default=2); ap.add_argument("--tp-bricks",type=int,default=4)
    ap.add_argument("--quantity-oz",type=float,default=100.0); ap.add_argument("--cost-usd",type=float,default=0.0)
    ap.add_argument("--out",default="backtest_result.json"); args=ap.parse_args()
    ticks=load_ticks_csv(args.csv,price_unit=args.price_unit); bricks=build_renko(ticks,args.brick)
    signals=reversal_signals(bricks,args.confirm)
    trades=backtest_signals(ticks,signals,stop_units=args.sl_bricks*args.brick,take_units=args.tp_bricks*args.brick,
        price_unit=float(args.price_unit),quantity_oz=args.quantity_oz,round_trip_cost_usd=args.cost_usd)
    payload={"meta":{"source_csv":str(Path(args.csv).resolve()),"price_unit":args.price_unit,"brick_size_units":args.brick},
             "bricks":bricks_to_dicts(bricks),"trades":trades_to_dicts(trades),
             "metrics":summarize(trades),"monte_carlo":monte_carlo(trades)}
    clean=safe(payload); Path(args.out).write_text(json.dumps(clean,indent=2,allow_nan=False))
    print(json.dumps(clean["metrics"],indent=2,allow_nan=False))
if __name__=="__main__": main()
