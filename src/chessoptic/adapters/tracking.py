"""TrackingAdapter: no opponent. Follows a game played on the board (both colours) for PGN."""

from __future__ import annotations

import time

import chess

from chessoptic.adapters.base import AdapterInfo, EmitFn
from chessoptic.core.events import GameOver, GameStarted, LinkState, LinkStatus, MoveAccepted

INFO = AdapterInfo(name="tracking", label="Solo seguimiento", kind="local", both_sides=True)


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
        self._emit(MoveAccepted(move))  # mate / draws are detected by the session

    def end_game(self, result: str, reason: str) -> None:
        if self._emit:
            self._emit(GameOver(result, reason))
