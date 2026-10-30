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
    DetectionPhase,
    MoveAmbiguous,
    MoveDetected,
    OccupancyFrame,
    PositionMatched,
    PositionMismatch,
    SquareIssue,
)

TrackerEvent = MoveDetected | MoveAmbiguous | PositionMismatch | PositionMatched

PIECE_NAMES = {
    chess.PAWN: "el peón",
    chess.KNIGHT: "el caballo",
    chess.BISHOP: "el alfil",
    chess.ROOK: "la torre",
    chess.QUEEN: "la dama",
    chess.KING: "el rey",
}


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
        self.phase = DetectionPhase.WAITING
        self.phase_detail = ""
        self.phase_squares: tuple[int, ...] = ()

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

    def _set_phase(
        self, phase: DetectionPhase, detail: str = "", squares: tuple[int, ...] = ()
    ) -> None:
        self.phase, self.phase_detail, self.phase_squares = phase, detail, squares

    def on_occupancy(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        if not frame.stable:
            # Hands still moving: whatever looked wrong may be a move in progress.
            self._mismatch_since = None
            self._candidate = None
            self._set_phase(DetectionPhase.HAND, "Movimiento sobre el tablero…")
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
            self._set_phase(DetectionPhase.WAITING)
            return self._clear_mismatch(frame)
        if isinstance(resolution, Move):
            self.reset_mismatch()
            san = self.model.san(resolution.move)
            if not self._confirmed(resolution.move):
                self._set_phase(
                    DetectionPhase.SEEN,
                    f"Vi {san}, confirmando…",
                    (resolution.move.from_square, resolution.move.to_square),
                )
                return []
            fen_before = self.model.fen
            san = self.model.push(resolution.move, observed=frame.grid)
            self.notify_accept()
            self._set_phase(DetectionPhase.ACCEPTED, f"Jugada aceptada: {san}")
            return [MoveDetected(resolution.move, san, fen_before, self.model.fen)]
        self._candidate = None
        if isinstance(resolution, Ambiguous):
            self.reset_mismatch()
            self._set_phase(DetectionPhase.SEEN, "Promoción: ¿qué pieza pusiste?")
            return [MoveAmbiguous(resolution.candidates)]
        if isinstance(resolution, Transient):
            self._set_phase(DetectionPhase.LIFTED, *self._describe_lifted(resolution.candidates))
            return []
        assert isinstance(resolution, Mismatch)
        return self._maybe_mismatch(frame, PositionMismatch(resolution.issues))

    def _describe_lifted(self, candidates: tuple[chess.Move, ...]) -> tuple[str, tuple[int, ...]]:
        origins = sorted({m.from_square for m in candidates})
        if len(origins) == 1:
            piece = self.model.board.piece_at(origins[0])
            name = PIECE_NAMES.get(piece.piece_type, "pieza") if piece else "pieza"
            return (
                f"Levantaste {name} de {chess.square_name(origins[0])}; esperando que la apoyes.",
                tuple(origins),
            )
        return ("Jugada en curso, esperando que termine…", tuple(origins))

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
        san = self.model.san(target.move)
        if not wrong:
            if not self._confirmed(target.move):
                self._set_phase(DetectionPhase.SEEN, f"Veo {san}, confirmando…")
                return []
            self._target = None
            self.reset_mismatch()
            self.model.push(target.move, observed=frame.grid)
            self.notify_accept()
            self._set_phase(DetectionPhase.ACCEPTED, f"{san} verificada en el tablero")
            return [PositionMatched(self.model.fen)]
        changed = changed_squares(frame.grid, reference, current, frame.changed_squares)
        if not changed:
            self._set_phase(DetectionPhase.WAITING, f"Esperando que reproduzcas {san}")
            return self._clear_mismatch(frame)
        if changed <= expected_changes:
            self._set_phase(DetectionPhase.LIFTED, f"Reproduciendo {san}…", tuple(changed))
            return self._clear_mismatch(frame)  # in progress
        issues = tuple(SquareIssue(sq, target.grid[sq], frame.grid[sq]) for sq in wrong)
        return self._maybe_mismatch(frame, PositionMismatch(issues))

    def _maybe_mismatch(self, frame: OccupancyFrame, event: PositionMismatch) -> list[TrackerEvent]:
        squares = tuple(i.square for i in event.issues)
        names = ", ".join(chess.square_name(sq) for sq in squares[:4])
        if self._mismatch_since is None:
            self._mismatch_since = frame.ts
        elapsed_ms = (frame.ts - self._mismatch_since) * 1000
        if elapsed_ms < self.mismatch_grace_ms:
            left = max(0.0, (self.mismatch_grace_ms - elapsed_ms) / 1000)
            self._set_phase(
                DetectionPhase.UNEXPLAINED,
                f"No cuadra con ninguna jugada ({names}) · {left:.0f} s",
                squares,
            )
            return []
        self._in_mismatch = True
        self._set_phase(DetectionPhase.MISMATCH, f"La posición no coincide: {names}", squares)
        return [event]

    def _clear_mismatch(self, frame: OccupancyFrame) -> list[TrackerEvent]:
        was = self._in_mismatch
        self.reset_mismatch()
        return [PositionMatched(self.model.fen)] if was else []
