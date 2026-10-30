"""Setup-flow logic that lives in the core: initial-position check and the move test."""

from __future__ import annotations

import logging

import chess

from chessoptic.board.occupancy import STARTPOS, Grid, Occupancy, counts, from_board
from chessoptic.core.bus import EventBus
from chessoptic.core.events import (
    ClassifierTrained,
    InitialPositionCheck,
    MoveTestProgress,
    MoveTestStage,
    OccupancyFrame,
    StabilityEvent,
)
from chessoptic.vision.pipeline import VisionPipeline

log = logging.getLogger(__name__)


def _after_e2e4() -> Grid:
    board = chess.Board()
    board.push_uci("e2e4")
    return from_board(board)


EXPECTED_E2E4: Grid = _after_e2e4()


def compare_with_startpos(grid: Grid) -> InitialPositionCheck:
    missing, extra, wrong = [], [], []
    for sq in chess.SQUARES:
        expected, seen = STARTPOS[sq], grid[sq]
        if expected == seen:
            continue
        if seen == Occupancy.EMPTY:
            missing.append(sq)
        elif expected == Occupancy.EMPTY:
            extra.append(sq)
        else:
            wrong.append(sq)
    white, black, _ = counts(grid)
    return InitialPositionCheck(
        white=white,
        black=black,
        missing=tuple(missing),
        extra=tuple(extra),
        wrong_color=tuple(wrong),
        complete=not (missing or extra or wrong),
    )


class SetupFlow:
    """Subscribes to vision events and drives: auto-training, initial check, move test."""

    def __init__(self, bus: EventBus, pipeline: VisionPipeline) -> None:
        self._bus = bus
        self._pipeline = pipeline
        self._arm_training = False
        self._watch_initial = False
        self._move_stage: MoveTestStage | None = None
        self._last_moving_ts: float | None = None
        bus.subscribe(StabilityEvent, self._on_stability)
        bus.subscribe(OccupancyFrame, self._on_occupancy)

    # ---- controls --------------------------------------------------------

    def arm_initial_training(self) -> None:
        """Train the classifier from the next stable frame (board must show the start position)."""
        self._pipeline.set_classifier(None)
        self._bus.publish(ClassifierTrained(False))
        self._arm_training = True
        self._watch_initial = True

    def watch_initial_position(self, enabled: bool) -> None:
        self._watch_initial = enabled

    def start_move_test(self) -> None:
        self._move_stage = MoveTestStage.WAITING_MOVE
        self._bus.publish(MoveTestProgress(self._move_stage, "Mové el peón de e2 a e4 y soltá."))

    def stop_move_test(self) -> None:
        self._move_stage = None

    # ---- event handlers --------------------------------------------------

    def _on_stability(self, event: StabilityEvent) -> None:
        if event.moving:
            self._last_moving_ts = event.ts
        if self._arm_training and event.stable:
            classifier = self._pipeline.train_initial()
            if classifier is not None:
                self._arm_training = False
                self._bus.publish(ClassifierTrained(True))
                log.info("classifier trained from the initial position")

    def _on_occupancy(self, event: OccupancyFrame) -> None:
        if not event.stable:
            return
        if self._watch_initial:
            self._bus.publish(compare_with_startpos(event.grid))
        if self._move_stage is not None:
            self._advance_move_test(event)

    def _advance_move_test(self, event: OccupancyFrame) -> None:
        latency = None
        if self._last_moving_ts is not None:
            latency = (event.ts - self._last_moving_ts) * 1000
        if self._move_stage == MoveTestStage.WAITING_MOVE and event.grid == EXPECTED_E2E4:
            self._move_stage = MoveTestStage.WAITING_BACK
            self._bus.publish(
                MoveTestProgress(
                    self._move_stage, "e2–e4 detectada. Ahora volvé el peón a e2.", latency
                )
            )
        elif self._move_stage == MoveTestStage.WAITING_BACK and event.grid == STARTPOS:
            self._move_stage = MoveTestStage.DONE
            self._bus.publish(
                MoveTestProgress(self._move_stage, "Vuelta a e2 detectada. Todo listo.", latency)
            )
