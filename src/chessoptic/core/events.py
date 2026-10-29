"""Immutable events and snapshots shared by the core, the adapters and the UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from chessoptic.board.occupancy import Grid
    from chessoptic.capture.webcam import CameraInfo
    from chessoptic.vision.calibration import Calibration


# ---------------------------------------------------------------- health


class HealthLevel(StrEnum):
    """Driver health 'traffic light'. Never reflects whose turn it is."""

    OK = "ok"
    WARN = "warn"
    ERR = "err"
    IDLE = "idle"


@dataclass(frozen=True)
class ComponentHealth:
    level: HealthLevel
    label: str
    detail: str = ""


@dataclass(frozen=True)
class HealthState:
    level: HealthLevel
    pill_text: str
    camera: ComponentHealth
    board: ComponentHealth
    link: ComponentHealth

    @staticmethod
    def starting() -> HealthState:
        idle = HealthLevel.IDLE
        return HealthState(
            level=idle,
            pill_text="Iniciando",
            camera=ComponentHealth(idle, "Cámara", "buscando"),
            board=ComponentHealth(idle, "Tablero", "sin calibrar"),
            link=ComponentHealth(idle, "Enlace", "inactivo"),
        )


# ---------------------------------------------------------------- camera / vision


class CameraState(StrEnum):
    OK = "ok"
    NO_CAMERA = "no_camera"
    DISCONNECTED = "disconnected"
    LOW_FPS = "low_fps"


@dataclass(frozen=True)
class CameraStatus:
    state: CameraState
    fps: float
    device: str


@dataclass(frozen=True)
class CamerasListed:
    cameras: tuple[CameraInfo, ...]


@dataclass(frozen=True)
class FrameEvent:
    """Latest frames for the UI (throttled). `rectified` is None until calibrated."""

    raw: np.ndarray
    rectified: np.ndarray | None
    ts: float


@dataclass(frozen=True)
class CalibrationChanged:
    calibration: Calibration | None


@dataclass(frozen=True)
class ClassifierTrained:
    trained: bool


@dataclass(frozen=True)
class StabilityEvent:
    motion: float
    moving: bool
    stable: bool
    ts: float


@dataclass(frozen=True)
class OccupancyFrame:
    grid: Grid
    confidence: tuple[float, ...]
    stable: bool
    motion: float
    ts: float

    @property
    def mean_confidence(self) -> float:
        return sum(self.confidence) / len(self.confidence) if self.confidence else 0.0


# ---------------------------------------------------------------- setup flow


@dataclass(frozen=True)
class InitialPositionCheck:
    white: int
    black: int
    missing: tuple[int, ...]  # squares that should hold a piece and look empty
    extra: tuple[int, ...]  # squares that should be empty and look occupied
    wrong_color: tuple[int, ...]
    complete: bool


class CheckLevel(StrEnum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass(frozen=True)
class Finding:
    code: str
    level: CheckLevel
    message: str
    action: str
    squares: tuple[int, ...] = ()


@dataclass(frozen=True)
class SetupCheckReport:
    level: CheckLevel
    findings: tuple[Finding, ...]
    mean_confidence: float
    suspicious: tuple[int, ...]


class MoveTestStage(StrEnum):
    WAITING_MOVE = "waiting_move"
    WAITING_BACK = "waiting_back"
    DONE = "done"


@dataclass(frozen=True)
class MoveTestProgress:
    stage: MoveTestStage
    detail: str
    latency_ms: float | None = None
