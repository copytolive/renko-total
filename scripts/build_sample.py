#!/usr/bin/env python3
from __future__ import annotations
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from copytolive_renko import Tick,build_renko,reversal_signals,backtest_signals,summarize,monte_carlo
from copytolive_renko.canonical import bricks_to_dicts
from copytolive_renko.backtest import trades_to_dicts

def safe(x):
    if isinstance(x,float) and not math.isfinite(x): return None
    if isinstance(x,dict): return {k:safe(v) for k,v in x.items()}
    if isinstance(x,list): return [safe(v) for v in x]
    return x

def synthetic_ticks():
    prices=[200000,200010,200025,200040,200060,200080,200100,200120,200140,200110,200080,200050,200020,199990,199960,199940,199920,199900,199930,199960,199990,200020,200050,200080,200110,200140,200170,200140,200110,200080,200050,200020,199990,200020,200050,200080,200110,200140,200170,200200,200230,200260,200290,200320,200350]
    base_ts=1_767_225_600_000
    return [Tick(i,base_ts+i*60_000,mid-2,mid+2,1.0,1.0) for i,mid in enumerate(prices)]

def main():
    ticks=synthetic_ticks(); bricks=build_renko(ticks,20); sigs=reversal_signals(bricks,1)
    trades=backtest_signals(ticks,sigs,stop_units=40,take_units=60,price_unit=0.01,quantity_oz=100)
    payload={"meta":{"symbol":"XAUUSD","mode":"SYNTHETIC_DEMO","price_unit":0.01,"brick_size_units":20,
                     "brick_size_price":0.20,"note":"Demo only. Production must be generated from audited Dukascopy raw ticks."},
             "ticks":[{"tick_id":t.tick_id,"timestamp_ms":t.timestamp_ms,"bid_units":t.bid_units,"ask_units":t.ask_units} for t in ticks],
             "bricks":bricks_to_dicts(bricks),"trades":trades_to_dicts(trades),
             "metrics":summarize(trades),"monte_carlo":monte_carlo(trades,iterations=500)}
    out=ROOT/"web/data/sample.json"; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(safe(payload),indent=2,allow_nan=False))
    print(out)
if __name__=="__main__": main()
