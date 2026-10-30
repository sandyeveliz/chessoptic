"""BoardTracker: turns stable occupancy frames into board events (move, mismatch, matched)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import chess

from chessoptic.board.model import (
    Ambiguous,
    BoardModel,
    Mismatch,
    Move,
    NoChange,
    Transient,
    changed_squares,
    wrong_squares,
)
from chessoptic.board.occupancy import Grid, diff
from chessoptic.core.events import (
    MoveAmbiguous,
    MoveDetected,
    OccupancyFrame,
    PositionMatched,
    PositionMismatch,
    SquareIssue,
)

TrackerEvent = MoveDetected | MoveAmbiguous | PositionMismatch | PositionMatched


@dataclass
class _Target:
    """Position we expect the user to reproduce (the opponent's move)."""

    move: chess.Move
    grid: Grid


class BoardTracker:
    def __init__(
        self,
        model: BoardModel,
        mismatch_grace_ms: int = 2000,
        confirm_frames: int = 2,
        on_accept: Callable[[Grid], None] | None = None,
    ) -> None:
        self.model = model
        self.mismatch_grace_ms = mismatch_grace_ms
        self.confirm_frames = confirm_frames
        self.on_accept = on_accept
        self._target: _Target | None = None
        self._mismatch_since: float | None = None
        self._in_mismatch = False
        self._candidate: tuple[chess.Move, int] | None = None  # (move, stable frames seen)

    # ---- control ---------------------------------------------------------

    def expect(self, move: chess.Move) -> None:
        """Verification mode: wait until the board shows `move` played, then push it."""
        self._target = _Target(move, self.model.occupancy_after(move))
        self._mismatch_since = None

    def clear_target(self) -> None:
        self._target = None

    def reset_mismatch(self) -> None:
        self._mismatch_since = None
        self._in_mismatch = False

    @property
    def expecting(self) -> chess.Move | None:
        return self._target.move if self._target else None

    # ---- occupancy -------------------------------------------------------

    def on_occupancy(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        if not frame.stable:
            return []
        if self._target is not None:
            return self._verify(frame)
        return self._detect(frame)

    def notify_accept(self) -> None:
        """The board shows the model's position: let the vision layer re-anchor and learn."""
        if self.on_accept is not None:
            self.on_accept(self.model.expected_occupancy())

    def _detect(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        resolution = self.model.resolve(frame.grid, frame.changed_squares)
        if isinstance(resolution, NoChange):
            self._candidate = None
            return self._clear_mismatch(frame)
        if isinstance(resolution, Move):
            self.reset_mismatch()
            if not self._confirmed(resolution.move):
                return []
            fen_before = self.model.fen
            san = self.model.push(resolution.move, observed=frame.grid)
            self.notify_accept()
            return [MoveDetected(resolution.move, san, fen_before, self.model.fen)]
        self._candidate = None
        if isinstance(resolution, Ambiguous):
            self.reset_mismatch()
            return [MoveAmbiguous(resolution.candidates)]
        if isinstance(resolution, Transient):
            return []
        assert isinstance(resolution, Mismatch)
        return self._maybe_mismatch(frame, PositionMismatch(resolution.issues))

    def _confirmed(self, move: chess.Move) -> bool:
        """A move must be seen on `confirm_frames` consecutive stable frames."""
        if self._candidate is not None and self._candidate[0] == move:
            self._candidate = (move, self._candidate[1] + 1)
        else:
            self._candidate = (move, 1)
        if self._candidate[1] >= self.confirm_frames:
            self._candidate = None
            return True
        return False

    def _verify(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        assert self._target is not None
        target = self._target
        current = self.model.expected_occupancy()
        reference = self.model.reference_grid()
        expected_changes = set(diff(current, target.grid))
        wrong = wrong_squares(frame.grid, reference, current, target.grid, frame.changed_squares)
        if not wrong:
            if not self._confirmed(target.move):
                return []
            self._target = None
            self.reset_mismatch()
            self.model.push(target.move, observed=frame.grid)
            self.notify_accept()
            return [PositionMatched(self.model.fen)]
        changed = changed_squares(frame.grid, reference, current, frame.changed_squares)
        if not changed or changed <= expected_changes:
            return self._clear_mismatch(frame)  # untouched or in progress
        issues = tuple(SquareIssue(sq, target.grid[sq], frame.grid[sq]) for sq in wrong)
        return self._maybe_mismatch(frame, PositionMismatch(issues))

    def _maybe_mismatch(self, frame: OccupancyFrame, event: PositionMismatch) -> list[TrackerEvent]:
        if self._mismatch_since is None:
            self._mismatch_since = frame.ts
            return []
        if (frame.ts - self._mismatch_since) * 1000 < self.mismatch_grace_ms:
            return []
        self._in_mismatch = True
        return [event]

    def _clear_mismatch(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        was = self._in_mismatch
        self.reset_mismatch()
        return [PositionMatched(self.model.fen)] if was else []
