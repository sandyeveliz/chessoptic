"""Providers (output adapters): who we play against / where the game lives.

POC: providers are listed by hand here. A registry with entry points comes when there is a
second kind of provider worth plugging in from outside the package.
"""

from __future__ import annotations

import chess

from chessoptic.adapters.base import AdapterInfo, OutputAdapter
from chessoptic.adapters.local.stockfish import INFO as STOCKFISH_INFO
from chessoptic.adapters.local.stockfish import StockfishAdapter, engine_from_config
from chessoptic.adapters.tracking import INFO as TRACKING_INFO
from chessoptic.adapters.tracking import TrackingAdapter
from chessoptic.core.config import AppConfig

AVAILABLE: tuple[AdapterInfo, ...] = (TRACKING_INFO, STOCKFISH_INFO)


def create_adapter(name: str, config: AppConfig) -> OutputAdapter:
    if name == STOCKFISH_INFO.name:
        engine = engine_from_config(config)
        if engine is not None:
            my_color = chess.WHITE if config.my_color != "black" else chess.BLACK
            return StockfishAdapter(engine, my_color)
        # No engine available: fall back to tracking so the app keeps working.
        return TrackingAdapter()
    return TrackingAdapter()


__all__ = ["AVAILABLE", "AdapterInfo", "OutputAdapter", "create_adapter"]
