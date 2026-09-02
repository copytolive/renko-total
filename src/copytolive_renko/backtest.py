from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from .canonical import RenkoBrick, Tick


@dataclass(frozen=True, slots=True)
class Signal:
    brick_id: int
    side: int  # +1 long, -1 short
    source_tick_id: int
    source_timestamp_ms: int


@dataclass(frozen=True, slots=True)
class Trade:
    side: int
    signal_brick_id: int
    signal_tick_id: int
    entry_tick_id: int
    exit_tick_id: int
    entry_timestamp_ms: int
    exit_timestamp_ms: int
    entry_units: int
    exit_units: int
    sl_units: int
    tp_units: int
    pnl_price_units: int
    pnl_usd: float
    exit_reason: str


def reversal_signals(bricks: Sequence[RenkoBrick], confirm_bricks: int = 1) -> list[Signal]:
    if confirm_bricks <= 0:
        raise ValueError("confirm_bricks must be positive")
    out: list[Signal] = []
    streak_dir = 0
    streak = 0
    last_emitted_dir = 0
    for b in bricks:
        if b.direction == streak_dir:
            streak += 1
        else:
            streak_dir = b.direction
            streak = 1
        if streak >= confirm_bricks and streak_dir != last_emitted_dir:
            out.append(Signal(b.brick_id, streak_dir, b.source_tick_close, b.source_timestamp_close))
            last_emitted_dir = streak_dir
    return out


def backtest_signals(
    ticks: Sequence[Tick],
    signals: Sequence[Signal],
    *,
    stop_units: int,
    take_units: int,
    price_unit: float = 0.01,
    quantity_oz: float = 1.0,
    round_trip_cost_usd: float = 0.0,
    max_holding_ticks: int | None = None,
) -> list[Trade]:
    """Non-overlapping tick replay with strict anti-lookahead.

    A signal formed on tick N is only eligible for entry on a tick with tick_id > N.
    BUY: entry ASK, exits on BID. SELL: entry BID, exits on ASK.
    """
    if stop_units <= 0 or take_units <= 0:
        raise ValueError("stop_units and take_units must be positive")
    if not ticks or not signals:
        return []

    sigs = sorted(signals, key=lambda s: (s.source_tick_id, s.brick_id))
    sig_i = 0
    pending: Signal | None = None
    position: dict | None = None
    trades: list[Trade] = []

    for tick in ticks:
        # Signals are only known after their source tick. We stage them here; entry is
        # deliberately performed only on a later tick.
        while sig_i < len(sigs) and sigs[sig_i].source_tick_id <= tick.tick_id:
            s = sigs[sig_i]
            if position is None and pending is None:
                pending = s
            sig_i += 1

        if position is None and pending is not None and tick.tick_id > pending.source_tick_id:
            side = pending.side
            entry = tick.ask_units if side > 0 else tick.bid_units
            position = {
                "signal": pending,
                "side": side,
                "entry_tick": tick,
                "entry": entry,
                "sl": entry - stop_units if side > 0 else entry + stop_units,
                "tp": entry + take_units if side > 0 else entry - take_units,
                "held": 0,
            }
            pending = None
            # Do not allow the same quote used for entry to also hit TP/SL.
            continue

        if position is None:
            continue

        position["held"] += 1
        side = position["side"]
        executable = tick.bid_units if side > 0 else tick.ask_units
        reason = None
        if side > 0:
            if executable <= position["sl"]:
                reason = "SL"
            elif executable >= position["tp"]:
                reason = "TP"
        else:
            if executable >= position["sl"]:
                reason = "SL"
            elif executable <= position["tp"]:
                reason = "TP"

        if reason is None and max_holding_ticks is not None and position["held"] >= max_holding_ticks:
            reason = "TIME"

        if reason is not None:
            pnl_units = (executable - position["entry"]) * side
            pnl_usd = pnl_units * price_unit * quantity_oz - round_trip_cost_usd
            s = position["signal"]
            e = position["entry_tick"]
            trades.append(
                Trade(
                    side=side,
                    signal_brick_id=s.brick_id,
                    signal_tick_id=s.source_tick_id,
                    entry_tick_id=e.tick_id,
                    exit_tick_id=tick.tick_id,
                    entry_timestamp_ms=e.timestamp_ms,
                    exit_timestamp_ms=tick.timestamp_ms,
                    entry_units=position["entry"],
                    exit_units=executable,
                    sl_units=position["sl"],
                    tp_units=position["tp"],
                    pnl_price_units=pnl_units,
                    pnl_usd=pnl_usd,
                    exit_reason=reason,
                )
            )
            position = None

    if position is not None:
        tick = ticks[-1]
        side = position["side"]
        executable = tick.bid_units if side > 0 else tick.ask_units
        pnl_units = (executable - position["entry"]) * side
        pnl_usd = pnl_units * price_unit * quantity_oz - round_trip_cost_usd
        s = position["signal"]
        e = position["entry_tick"]
        trades.append(
            Trade(
                side=side,
                signal_brick_id=s.brick_id,
                signal_tick_id=s.source_tick_id,
                entry_tick_id=e.tick_id,
                exit_tick_id=tick.tick_id,
                entry_timestamp_ms=e.timestamp_ms,
                exit_timestamp_ms=tick.timestamp_ms,
                entry_units=position["entry"],
                exit_units=executable,
                sl_units=position["sl"],
                tp_units=position["tp"],
                pnl_price_units=pnl_units,
                pnl_usd=pnl_usd,
                exit_reason="EOD",
            )
        )
    return trades


def trades_to_dicts(trades: Iterable[Trade]) -> list[dict]:
    return [asdict(t) for t in trades]
