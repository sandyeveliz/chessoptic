"""Providers (output adapters): who we play against / where the game lives.

POC: providers are listed by hand here. A registry with entry points comes when there is a
second kind of provider worth plugging in from outside the package.
"""

from __future__ import annotations

from chessoptic.adapters.base import AdapterInfo, OutputAdapter
from chessoptic.adapters.tracking import INFO as TRACKING_INFO
from chessoptic.adapters.tracking import TrackingAdapter
from chessoptic.core.config import AppConfig

AVAILABLE: tuple[AdapterInfo, ...] = (TRACKING_INFO,)


def create_adapter(name: str, config: AppConfig) -> OutputAdapter:
    if name == TRACKING_INFO.name:
        return TrackingAdapter()
    # Unknown or not-yet-implemented provider: fall back to tracking so the app keeps working.
    return TrackingAdapter()


__all__ = ["AVAILABLE", "AdapterInfo", "OutputAdapter", "create_adapter"]
