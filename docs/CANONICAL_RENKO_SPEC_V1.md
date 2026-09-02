# CopyToLive Canonical Renko V1

## Raw source
- Dukascopy XAUUSD BID + ASK ticks.
- Archive raw source immutably by UTC day with checksum and manifest.
- Preserve raw prices exactly in Decimal128 Parquet before canonical integer normalization.

## Canonical engine
- `brick_id` is the primary horizontal identity.
- Fixed anchor; default anchor is floor(first source price / brick size) × brick size.
- Integer price units only inside the production Renko kernel.
- Continuation threshold is inclusive.
- Reversal requires 2 brick sizes.
- One source tick may emit multiple bricks.
- Every brick retains source tick/timestamp lineage.

## Execution / anti-lookahead
- A brick signal only exists after its closing source tick.
- Market entry must occur on a later eligible raw tick.
- BUY entry = ASK; BUY exit = BID.
- SELL entry = BID; SELL exit = ASK.
- TP/SL is evaluated from raw chronological quotes, never inferred from Renko OHLC.

## Validation
- The custom integer kernel is canonical.
- renkodf is a reference implementation, not the production source of truth.
- mplchart is a structural visual/reference validator.
- QuantConnect LEAN is a finalist execution/accounting validator, not the canonical Renko generator.
