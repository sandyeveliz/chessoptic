"""Immutable events and snapshots shared by the core, the adapters and the UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import chess

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
    # Squares whose *image* changed since the last accepted position (empty = unknown).
    changed: tuple[bool, ...] = ()

    @property
    def changed_squares(self) -> set[int] | None:
        """Squares whose image changed since the reference; None when not known."""
        if not self.changed:
            return None
        return {sq for sq, flag in enumerate(self.changed) if flag}

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
    mismatched: tuple[int, ...] = ()  # squares that differ from what the stage expects
    error: str = ""  # human-readable list of those squares, empty when nothing is wrong


# ---------------------------------------------------------------- board events (tracker → session)


@dataclass(frozen=True)
class SquareIssue:
    square: int
    expected: int  # Occupancy value
    seen: int


@dataclass(frozen=True)
class MoveDetected:
    move: chess.Move
    san: str
    fen_before: str
    fen_after: str


@dataclass(frozen=True)
class MoveAmbiguous:
    candidates: tuple[chess.Move, ...]


@dataclass(frozen=True)
class PositionMismatch:
    issues: tuple[SquareIssue, ...]


@dataclass(frozen=True)
class PositionMatched:
    fen: str


# ---------------------------------------------------------------- adapter events (→ session)


class LinkState(StrEnum):
    INACTIVE = "inactive"
    ANNOUNCING = "announcing"
    CONNECTED = "connected"
    LOST = "lost"


@dataclass(frozen=True)
class LinkStatus:
    state: LinkState
    client: str
    detail: str = ""


@dataclass(frozen=True)
class GameStarted:
    game_id: str
    my_color: bool | None  # chess.WHITE / chess.BLACK; None = both sides (tracking)
    platform: str
    initial_fen: str


@dataclass(frozen=True)
class OpponentMove:
    move: chess.Move
    san: str


@dataclass(frozen=True)
class MoveAccepted:
    move: chess.Move


@dataclass(frozen=True)
class MoveRejected:
    move: chess.Move
    reason: str


@dataclass(frozen=True)
class ClockUpdate:
    white_ms: int | None
    black_ms: int | None


@dataclass(frozen=True)
class GameOver:
    result: str  # "1-0", "0-1", "1/2-1/2", "*"
    reason: str


@dataclass(frozen=True)
class AdapterError:
    message: str
    recoverable: bool = True


# ---------------------------------------------------------------- session snapshots (→ UI)


class Phase(StrEnum):
    STANDBY = "standby"
    IN_GAME = "in_game"


class DriverStateName(StrEnum):
    STARTING = "starting"
    UNCALIBRATED = "uncalibrated"
    VERIFYING_BOARD = "verifying_board"
    READY = "ready"
    PAUSED = "paused"
    MY_TURN = "my_turn"
    MOVING = "moving"
    OPPONENT_TURN = "opponent_turn"
    REPLAY = "replay"
    VERIFYING = "verifying"
    PROMOTION = "promotion"
    MISMATCH = "mismatch"
    LINK_LOST = "link_lost"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class DriverState:
    phase: Phase
    state: DriverStateName
    detail: str = ""


@dataclass(frozen=True)
class MoveRecord:
    number: int  # full-move number
    color: bool  # chess.WHITE / chess.BLACK
    san: str
    uci: str
    source: str  # "detected" | "opponent"
    wall_time: str  # HH:MM:SS


@dataclass(frozen=True)
class GameInfo:
    my_color: bool | None
    platform: str
    moves: tuple[MoveRecord, ...]
    result: str | None
    turn: bool  # side to move
    fen: str
    white_ms: int | None = None
    black_ms: int | None = None
    last_sent: str | None = None  # SAN of my last move, once accepted
    both_sides: bool = True  # tracking mode: the user plays both colours, no explicit start
    last_opponent: str | None = None  # SAN of the opponent's last move


@dataclass(frozen=True)
class PendingOpponentMove:
    san: str
    uci: str
    piece_name: str
    from_square: int
    to_square: int
    special: str | None  # "castle" | "en_passant" | "promotion" | None
    human_text: str


@dataclass(frozen=True)
class LogEntry:
    wall_time: str
    kind: str  # "move" | "event" | "error"
    text: str
    frame_path: str | None = None
