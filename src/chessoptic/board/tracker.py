"""BoardTracker: turns stable occupancy frames into board events (move, mismatch, matched)."""

from __future__ import annotations

from dataclasses import dataclass

import chess

from chessoptic.board.model import Ambiguous, BoardModel, Mismatch, Move, NoChange, Transient
from chessoptic.board.occupancy import Grid, diff
from chessoptic.core.events import (
    MoveAmbiguous,
    MoveDetected,
    OccupancyFrame,
    PositionMatched,
    PositionMismatch,
)

TrackerEvent = MoveDetected | MoveAmbiguous | PositionMismatch | PositionMatched


@dataclass
class _Target:
    """Position we expect the user to reproduce (the opponent's move)."""

    move: chess.Move
    grid: Grid


class BoardTracker:
    def __init__(self, model: BoardModel, mismatch_grace_ms: int = 2000) -> None:
        self.model = model
        self.mismatch_grace_ms = mismatch_grace_ms
        self._target: _Target | None = None
        self._mismatch_since: float | None = None
        self._in_mismatch = False

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

    def _detect(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        resolution = self.model.resolve(frame.grid)
        if isinstance(resolution, NoChange):
            return self._clear_mismatch(frame)
        if isinstance(resolution, Move):
            self.reset_mismatch()
            fen_before = self.model.fen
            san = self.model.push(resolution.move)
            return [MoveDetected(resolution.move, san, fen_before, self.model.fen)]
        if isinstance(resolution, Ambiguous):
            self.reset_mismatch()
            return [MoveAmbiguous(resolution.candidates)]
        if isinstance(resolution, Transient):
            return []
        assert isinstance(resolution, Mismatch)
        return self._maybe_mismatch(frame, PositionMismatch(resolution.issues))

    def _verify(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        assert self._target is not None
        target = self._target
        if frame.grid == target.grid:
            self._target = None
            self.reset_mismatch()
            self.model.push(target.move)
            return [PositionMatched(self.model.fen)]
        current = self.model.expected_occupancy()
        changed = set(diff(current, frame.grid))
        expected_changes = set(diff(current, target.grid))
        if not changed or changed <= expected_changes:
            return self._clear_mismatch(frame)  # untouched or in progress
        issues = self.model.issues_against(frame.grid, target.grid)
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
