"""TrackingAdapter: no opponent. Follows a game played on the board (both colours) for PGN."""

from __future__ import annotations

import time

import chess

from chessoptic.adapters.base import AdapterInfo, EmitFn
from chessoptic.core.events import GameOver, GameStarted, LinkState, LinkStatus, MoveAccepted

INFO = AdapterInfo(name="tracking", label="Solo seguimiento", kind="local", both_sides=True)


def result_and_reason(board: chess.Board) -> tuple[str, str] | None:
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    result = outcome.result()
    reasons = {
        chess.Termination.CHECKMATE: "jaque mate",
        chess.Termination.STALEMATE: "rey ahogado",
        chess.Termination.INSUFFICIENT_MATERIAL: "material insuficiente",
        chess.Termination.SEVENTYFIVE_MOVES: "regla de 75 jugadas",
        chess.Termination.FIVEFOLD_REPETITION: "quíntuple repetición",
        chess.Termination.FIFTY_MOVES: "regla de 50 jugadas",
        chess.Termination.THREEFOLD_REPETITION: "triple repetición",
    }
    return result, reasons.get(outcome.termination, str(outcome.termination).lower())


class TrackingAdapter:
    def __init__(self) -> None:
        self._emit: EmitFn | None = None

    @property
    def info(self) -> AdapterInfo:
        return INFO

    def start(self, emit: EmitFn) -> None:
        self._emit = emit
        emit(LinkStatus(LinkState.CONNECTED, INFO.label, "anotando"))

    def stop(self) -> None:
        if self._emit:
            self._emit(LinkStatus(LinkState.INACTIVE, INFO.label))
        self._emit = None

    def start_game(self, board: chess.Board) -> None:
        if self._emit:
            self._emit(GameStarted(f"local-{int(time.time())}", None, INFO.label, board.fen()))

    def on_move(self, move: chess.Move, board_after: chess.Board) -> None:
        if not self._emit:
            return
        self._emit(MoveAccepted(move))
        ended = result_and_reason(board_after)
        if ended is not None:
            self._emit(GameOver(ended[0], ended[1]))

    def end_game(self, result: str, reason: str) -> None:
        if self._emit:
            self._emit(GameOver(result, reason))
