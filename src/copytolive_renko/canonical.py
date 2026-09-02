from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Iterable, Literal, Sequence

PriceSource = Literal["mid", "bid", "ask"]


@dataclass(frozen=True, slots=True)
class Tick:
    tick_id: int
    timestamp_ms: int
    bid_units: int
    ask_units: int
    bid_volume: float = 0.0
    ask_volume: float = 0.0

    def source_price(self, source: PriceSource = "mid") -> int:
        if source == "bid":
            return self.bid_units
        if source == "ask":
            return self.ask_units
        # Deterministic integer midpoint. A half-unit spread floors toward bid.
        return (self.bid_units + self.ask_units) // 2


@dataclass(frozen=True, slots=True)
class RenkoBrick:
    brick_id: int
    open_units: int
    high_units: int
    low_units: int
    close_units: int
    direction: int  # +1 up, -1 down
    is_reversal: bool
    source_tick_open: int
    source_tick_close: int
    source_timestamp_open: int
    source_timestamp_close: int


def decimal_to_units(value: str | int | float | Decimal, price_unit: str | Decimal) -> int:
    """Convert decimal price to integer units deterministically.

    Values are rounded half-up to the nearest configured unit. Raw archival storage should
    preserve source decimals; this conversion happens at the canonical-engine boundary.
    """
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    u = price_unit if isinstance(price_unit, Decimal) else Decimal(str(price_unit))
    if u <= 0:
        raise ValueError("price_unit must be positive")
    return int((d / u).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def floor_anchor(price_units: int, brick_size_units: int) -> int:
    if brick_size_units <= 0:
        raise ValueError("brick_size_units must be positive")
    return (price_units // brick_size_units) * brick_size_units


def build_renko(
    ticks: Iterable[Tick],
    brick_size_units: int,
    *,
    anchor_units: int | None = None,
    source: PriceSource = "mid",
) -> list[RenkoBrick]:
    """Build canonical integer Renko bricks.

    Rules:
    - fixed anchor; default = floor(first source price / brick_size) * brick_size
    - inclusive continuation thresholds
    - 2-brick reversal
    - one source tick may emit multiple bricks
    - brick_id is monotonically increasing and is the horizontal identity
    """
    if brick_size_units <= 0:
        raise ValueError("brick_size_units must be positive")

    seq = iter(ticks)
    try:
        first = next(seq)
    except StopIteration:
        return []

    first_price = first.source_price(source)
    last_close = floor_anchor(first_price, brick_size_units) if anchor_units is None else int(anchor_units)
    direction = 0
    brick_id = 0
    prev_close_tick = first.tick_id
    prev_close_ts = first.timestamp_ms
    out: list[RenkoBrick] = []

    def emit(open_u: int, close_u: int, tick: Tick, *, reversal: bool) -> None:
        nonlocal brick_id, prev_close_tick, prev_close_ts, last_close, direction
        d = 1 if close_u > open_u else -1
        out.append(
            RenkoBrick(
                brick_id=brick_id,
                open_units=open_u,
                high_units=max(open_u, close_u),
                low_units=min(open_u, close_u),
                close_units=close_u,
                direction=d,
                is_reversal=reversal,
                source_tick_open=prev_close_tick,
                source_tick_close=tick.tick_id,
                source_timestamp_open=prev_close_ts,
                source_timestamp_close=tick.timestamp_ms,
            )
        )
        brick_id += 1
        prev_close_tick = tick.tick_id
        prev_close_ts = tick.timestamp_ms
        last_close = close_u
        direction = d

    def process_tick(tick: Tick) -> None:
        nonlocal direction, last_close
        p = tick.source_price(source)
        b = brick_size_units

        if direction == 0:
            if p >= last_close + b:
                while p >= last_close + b:
                    emit(last_close, last_close + b, tick, reversal=False)
                return
            if p <= last_close - b:
                while p <= last_close - b:
                    emit(last_close, last_close - b, tick, reversal=False)
                return
            return

        if direction > 0:
            # Continuation first: inclusive threshold.
            while p >= last_close + b:
                emit(last_close, last_close + b, tick, reversal=False)
            # Two-brick reversal. The reversal brick spans two grid levels from the
            # previous close and opens one brick inside the old direction.
            if p <= last_close - 2 * b:
                old_close = last_close
                emit(old_close - b, old_close - 2 * b, tick, reversal=True)
                while p <= last_close - b:
                    emit(last_close, last_close - b, tick, reversal=False)
            return

        # direction < 0
        while p <= last_close - b:
            emit(last_close, last_close - b, tick, reversal=False)
        if p >= last_close + 2 * b:
            old_close = last_close
            emit(old_close + b, old_close + 2 * b, tick, reversal=True)
            while p >= last_close + b:
                emit(last_close, last_close + b, tick, reversal=False)

    # The first tick can itself be far from its floored anchor.
    process_tick(first)
    for tick in seq:
        process_tick(tick)
    return out


def bricks_to_dicts(bricks: Sequence[RenkoBrick]) -> list[dict]:
    return [
        {
            "brick_id": b.brick_id,
            "open_units": b.open_units,
            "high_units": b.high_units,
            "low_units": b.low_units,
            "close_units": b.close_units,
            "direction": b.direction,
            "is_reversal": b.is_reversal,
            "source_tick_open": b.source_tick_open,
            "source_tick_close": b.source_tick_close,
            "source_timestamp_open": b.source_timestamp_open,
            "source_timestamp_close": b.source_timestamp_close,
        }
        for b in bricks
    ]
