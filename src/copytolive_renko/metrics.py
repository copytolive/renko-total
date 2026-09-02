from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from random import Random
from statistics import mean, pstdev
from typing import Sequence

from .backtest import Trade

def _drawdown(equity: Sequence[float]) -> tuple[float, float]:
    peak = float("-inf")
    max_dd = 0.0
    max_dd_pct = 0.0
    for x in equity:
        peak = max(peak, x)
        dd = peak - x
        max_dd = max(max_dd, dd)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, dd / peak * 100.0)
    return max_dd, max_dd_pct

def profit_factor(pnls: Sequence[float]) -> float:
    gross_win = sum(x for x in pnls if x > 0)
    gross_loss = -sum(x for x in pnls if x < 0)
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return gross_win / gross_loss

def max_consecutive_losses(pnls: Sequence[float]) -> int:
    best = cur = 0
    for x in pnls:
        if x < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best

def summarize(trades: Sequence[Trade], starting_equity: float = 10_000.0) -> dict:
    pnls = [t.pnl_usd for t in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    equity = [starting_equity]
    for x in pnls:
        equity.append(equity[-1] + x)
    max_dd, max_dd_pct = _drawdown(equity)
    net = sum(pnls)
    avg = mean(pnls) if pnls else 0.0
    sd = pstdev(pnls) if len(pnls) > 1 else 0.0
    sqn = sqrt(len(pnls)) * avg / sd if sd > 0 else 0.0
    yearly: dict[int, float] = {}
    for t in trades:
        y = datetime.fromtimestamp(t.exit_timestamp_ms / 1000, tz=timezone.utc).year
        yearly[y] = yearly.get(y, 0.0) + t.pnl_usd
    worst_year = min(yearly.values()) if yearly else 0.0
    positive_years = sum(1 for v in yearly.values() if v > 0)
    recovery = net / max_dd if max_dd > 0 else (float("inf") if net > 0 else 0.0)
    return {
        "total_entry": len(trades),
        "wr_pct": (len(wins) / len(trades) * 100.0) if trades else 0.0,
        "pf_net": profit_factor(pnls),
        "net_profit_usd": net,
        "ev_per_trade_usd": avg,
        "avg_win_usd": mean(wins) if wins else 0.0,
        "avg_loss_usd": mean(losses) if losses else 0.0,
        "max_dd_usd": max_dd,
        "max_dd_pct": max_dd_pct,
        "recovery_factor": recovery,
        "max_consecutive_loss": max_consecutive_losses(pnls),
        "sqn": sqn,
        "positive_year": positive_years,
        "worst_year_usd": worst_year,
        "years": yearly,
    }

def monte_carlo(trades: Sequence[Trade], *, starting_equity: float = 10_000.0,
                iterations: int = 1000, seed: int = 7, dd_limit_pct: float = 50.0) -> dict:
    pnls = [t.pnl_usd for t in trades]
    if not pnls:
        return {"iterations": iterations, "pass_rate_pct": 0.0, "dd95_pct": 0.0}
    rng = Random(seed)
    dds: list[float] = []
    passes = 0
    for _ in range(iterations):
        equity = [starting_equity]
        for _ in pnls:
            equity.append(equity[-1] + pnls[rng.randrange(len(pnls))])
        _, dd_pct = _drawdown(equity)
        dds.append(dd_pct)
        if dd_pct <= dd_limit_pct and equity[-1] > starting_equity:
            passes += 1
    dds.sort()
    idx = min(len(dds)-1, max(0, int(round(0.95 * (len(dds)-1)))))
    return {"iterations": iterations, "pass_rate_pct": passes / iterations * 100.0,
            "dd95_pct": dds[idx], "dd_limit_pct": dd_limit_pct}
