"""Webcam enumeration and capture through OpenCV, with the backend that works per OS."""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import cast

import cv2

from chessoptic.capture.source import Frame, Image

log = logging.getLogger(__name__)

PROBE_INDICES = range(0, 6)
PROBE_TIMEOUT_S = 4.0
DEFAULT_SIZE = (1280, 720)
MAX_CONSECUTIVE_FAILURES = 30


def camera_backend() -> int:
    system = platform.system()
    if system == "Windows":
        # MSMF is not built into the headless wheel; DSHOW opens devices by index fine.
        return int(cv2.CAP_DSHOW)
    if system == "Darwin":
        return int(cv2.CAP_AVFOUNDATION)
    return int(cv2.CAP_V4L2)


def _quiet_opencv() -> None:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)


@dataclass(frozen=True)
class CameraInfo:
    index: int
    name: str
    width: int
    height: int

    @property
    def key(self) -> str:
        """Stable-ish identifier for profiles: name wins over index when known."""
        safe = "".join(ch if ch.isalnum() else "_" for ch in self.name).strip("_")
        return safe or f"camera{self.index}"

    @property
    def label(self) -> str:
        return f"{self.name} ({self.width}x{self.height})"


def _probe(index: int) -> tuple[int, int] | None:
    _quiet_opencv()
    cap = cv2.VideoCapture(index, camera_backend())
    try:
        if not cap.isOpened():
            return None
        ok, _ = cap.read()
        if not ok:
            return None
        return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()


def _probe_with_timeout(index: int, timeout_s: float) -> tuple[int, int] | None:
    result: list[tuple[int, int] | None] = []

    def worker() -> None:
        try:
            result.append(_probe(index))
        except Exception:
            result.append(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive() or not result:
        return None
    return result[0]


def system_camera_names() -> list[str]:
    """Best-effort friendly names in OS order; may be empty. Never raises."""
    system = platform.system()
    try:
        if system == "Windows":
            script = (
                "Get-PnpDevice -Class Camera,Image -Status OK | "
                "Select-Object -ExpandProperty FriendlyName"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            ).stdout
            names = [ln.strip() for ln in out.splitlines() if ln.strip()]
            # Scanners also show up under 'Image'; keep things that look like cameras first.
            cams = [n for n in names if any(k in n.lower() for k in ("cam", "webcam", "camera"))]
            return cams or names
        if system == "Linux":
            from pathlib import Path

            names = []
            for node in sorted(Path("/sys/class/video4linux").glob("video*")):
                name_file = node / "name"
                if name_file.exists():
                    names.append(name_file.read_text(encoding="utf-8").strip())
            return names
    except Exception as exc:
        log.debug("camera names unavailable: %s", exc)
    return []


def list_cameras() -> list[CameraInfo]:
    """Probe indices with a timeout each (OpenCV can hang on some devices)."""
    names = system_camera_names()
    found: list[CameraInfo] = []
    for index in PROBE_INDICES:
        size = _probe_with_timeout(index, PROBE_TIMEOUT_S)
        if size is None:
            continue
        name = names[len(found)] if len(found) < len(names) else f"Cámara {index}"
        found.append(CameraInfo(index, name, size[0], size[1]))
    return found


class WebcamSource:
    """Live frames from a webcam. Tracks fps and reports failures via `healthy`."""

    def __init__(self, info: CameraInfo, size: tuple[int, int] = DEFAULT_SIZE) -> None:
        _quiet_opencv()
        self._info = info
        self._cap = cv2.VideoCapture(info.index, camera_backend())
        if not self._cap.isOpened():
            raise OSError(f"cannot open camera {info.label}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        self._index = 0
        self._failures = 0
        self._fps_window: list[float] = []

    @property
    def name(self) -> str:
        return self._info.name

    @property
    def info(self) -> CameraInfo:
        return self._info

    @property
    def fps(self) -> float:
        if len(self._fps_window) < 2:
            return 0.0
        span = self._fps_window[-1] - self._fps_window[0]
        return (len(self._fps_window) - 1) / span if span > 0 else 0.0

    @property
    def healthy(self) -> bool:
        return self._failures < MAX_CONSECUTIVE_FAILURES

    def read(self) -> Frame | None:
        ok, image = self._cap.read()
        now = time.monotonic()
        if not ok or image is None:
            self._failures += 1
            return None
        self._failures = 0
        self._fps_window.append(now)
        if len(self._fps_window) > 30:
            self._fps_window.pop(0)
        frame = Frame(cast(Image, image), now, self._index)
        self._index += 1
        return frame

    def set_property(self, prop: int, value: float) -> bool:
        return bool(self._cap.set(prop, value))

    def get_property(self, prop: int) -> float:
        return float(self._cap.get(prop))

    def close(self) -> None:
        self._cap.release()
