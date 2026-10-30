"""Frame and the FrameSource protocol, plus sources that need no hardware."""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]  # BGR, HxWx3


@dataclass(frozen=True)
class Frame:
    image: Image
    ts: float
    index: int

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.image.shape[:2]
        return int(w), int(h)


class FrameSource(Protocol):
    """Anything that yields frames. `read()` returns None when exhausted or broken."""

    @property
    def name(self) -> str: ...

    def read(self) -> Frame | None: ...

    def close(self) -> None: ...


class ListSource:
    """Frames from an in-memory list (tests, synthetic sequences)."""

    def __init__(self, images: Iterable[Image], name: str = "list") -> None:
        self._images = list(images)
        self._name = name
        self._index = 0

    @property
    def name(self) -> str:
        return self._name

    def read(self) -> Frame | None:
        if self._index >= len(self._images):
            return None
        frame = Frame(self._images[self._index], time.monotonic(), self._index)
        self._index += 1
        return frame

    def close(self) -> None:
        self._images = []


class VideoFileSource:
    """Frames from a video file. With `realtime=True` it paces reads to the file's fps."""

    def __init__(self, path: str | Path, realtime: bool = False) -> None:
        self._path = Path(path)
        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise OSError(f"cannot open video {self._path}")
        self._fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0
        self._realtime = realtime
        self._index = 0
        self._started = time.monotonic()

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def fps(self) -> float:
        return self._fps

    def read(self) -> Frame | None:
        ok, image = self._cap.read()
        if not ok:
            return None
        if self._realtime:
            due = self._started + self._index / self._fps
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        frame = Frame(cast(Image, image), time.monotonic(), self._index)
        self._index += 1
        return frame

    def close(self) -> None:
        self._cap.release()
