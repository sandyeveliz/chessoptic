"""Hand / motion detection and the 'stable for N ms' gate before an occupancy is accepted."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from chessoptic.capture.source import Image

SMALL = 128  # motion is measured on a downscaled grayscale copy


@dataclass
class StabilityState:
    motion: float  # fraction of pixels that changed (0..1)
    moving: bool
    stable: bool  # quiet for at least window_ms


class StabilityDetector:
    def __init__(self, window_ms: int = 750, threshold: float = 0.02) -> None:
        self.window_ms = window_ms
        self.threshold = threshold
        self._previous: np.ndarray | None = None
        self._quiet_since: float | None = None

    def reset(self) -> None:
        self._previous = None
        self._quiet_since = None

    def update(self, rectified: Image, ts: float) -> StabilityState:
        gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (SMALL, SMALL), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (5, 5), 0)
        if self._previous is None:
            self._previous = small
            self._quiet_since = ts
            return StabilityState(motion=0.0, moving=False, stable=False)

        delta = cv2.absdiff(small, self._previous)
        motion = float((delta > 25).mean())
        self._previous = small

        moving = motion > self.threshold
        if moving:
            self._quiet_since = None
        elif self._quiet_since is None:
            self._quiet_since = ts
        quiet_ms = 0.0 if self._quiet_since is None else (ts - self._quiet_since) * 1000
        return StabilityState(motion=motion, moving=moving, stable=quiet_ms >= self.window_ms)
