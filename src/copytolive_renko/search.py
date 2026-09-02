from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence
from .backtest import backtest_signals, reversal_signals
from .canonical import Tick, build_renko
from .metrics import monte_carlo, summarize

@dataclass(frozen=True, slots=True)
class Candidate:
    brick_size_units: int
    confirm_bricks: int
    stop_bricks: int
    take_bricks: int

def candidate_grid(brick_sizes: Iterable[int], confirms: Iterable[int],
                   stops: Iterable[int], takes: Iterable[int]) -> list[Candidate]:
    return [Candidate(b,c,s,t) for b in brick_sizes for c in confirms for s in stops for t in takes]

def evaluate_candidate(ticks: Sequence[Tick], c: Candidate, *, price_unit: float = 0.01,
                       quantity_oz: float = 1.0, costs_usd: float = 0.0,
                       mc_iterations: int = 250) -> dict:
    bricks = build_renko(ticks, c.brick_size_units)
    signals = reversal_signals(bricks, c.confirm_bricks)
    trades = backtest_signals(ticks, signals,
        stop_units=c.stop_bricks*c.brick_size_units,
        take_units=c.take_bricks*c.brick_size_units,
        price_unit=price_unit, quantity_oz=quantity_oz, round_trip_cost_usd=costs_usd)
    m = summarize(trades)
    mc = monte_carlo(trades, iterations=mc_iterations)
    return {"method":"renko_direction_confirm","brick_size_units":c.brick_size_units,
            "confirm_bricks":c.confirm_bricks,"sl_bricks":c.stop_bricks,"tp_bricks":c.take_bricks,
            "brick_count":len(bricks),**m,"monte_carlo_pass_pct":mc["pass_rate_pct"],
            "mc_95_dd_pct":mc["dd95_pct"]}

def screen(ticks: Sequence[Tick], candidates: Sequence[Candidate], *, min_entries: int = 100,
           min_net_profit: float = 20_000.0, min_pf: float = 1.0, top_n: int = 100, **kwargs) -> list[dict]:
    rows=[]
    for c in candidates:
        r=evaluate_candidate(ticks,c,**kwargs)
        if r["total_entry"] < min_entries or r["net_profit_usd"] < min_net_profit or r["pf_net"] < min_pf:
            continue
        rows.append(r)
    rows.sort(key=lambda r:(r["net_profit_usd"],r["pf_net"],r["sqn"]),reverse=True)
    return rows[:top_n]
