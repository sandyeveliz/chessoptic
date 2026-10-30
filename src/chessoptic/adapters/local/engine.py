"""Engine protocol and a UCI implementation on top of python-chess."""

from __future__ import annotations

import logging
import random
from collections.abc import Sequence
from typing import Protocol

import chess
import chess.engine

log = logging.getLogger(__name__)


class EngineProtocol(Protocol):
    """Anything that can pick a move for the side to move. UCI is one implementation."""

    @property
    def name(self) -> str: ...

    def start(self) -> None: ...

    def play(self, board: chess.Board) -> chess.Move: ...

    def stop(self) -> None: ...


class UciEngine:
    """Any UCI engine (Stockfish, Leela, …). `skill_level` is applied when the engine has it."""

    def __init__(
        self,
        path: str,
        skill_level: int | None = None,
        move_time_s: float = 0.5,
        threads: int = 1,
    ) -> None:
        self._path = path
        self._skill_level = skill_level
        self._move_time = move_time_s
        self._threads = threads
        self._engine: chess.engine.SimpleEngine | None = None
        self._name = "UCI"

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> None:
        self._engine = chess.engine.SimpleEngine.popen_uci(self._path)
        self._name = str(self._engine.id.get("name", "UCI"))
        options: dict[str, str | int | bool | None] = {}
        if "Threads" in self._engine.options:
            options["Threads"] = self._threads
        if self._skill_level is not None and "Skill Level" in self._engine.options:
            options["Skill Level"] = self._skill_level
        if options:
            self._engine.configure(options)
        log.info("engine started: %s (%s)", self._name, self._path)

    def play(self, board: chess.Board) -> chess.Move:
        if self._engine is None:
            raise RuntimeError("engine not started")
        result = self._engine.play(board, chess.engine.Limit(time=self._move_time))
        if result.move is None:
            raise RuntimeError("engine returned no move")
        return result.move

    def stop(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except chess.engine.EngineError:
                log.debug("engine quit failed", exc_info=True)
            self._engine = None


class RandomEngine:
    """Plays random legal moves. Useful for tests and demos without Stockfish."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        return "Aleatorio"

    def start(self) -> None:
        return None

    def play(self, board: chess.Board) -> chess.Move:
        return self._rng.choice(list(board.legal_moves))

    def stop(self) -> None:
        return None


class ScriptedEngine:
    """Replays a fixed list of moves (UCI). Falls back to random when the script runs out."""

    def __init__(self, moves: Sequence[str]) -> None:
        self._moves = list(moves)
        self._fallback = RandomEngine(0)

    @property
    def name(self) -> str:
        return "Guionado"

    def start(self) -> None:
        return None

    def play(self, board: chess.Board) -> chess.Move:
        while self._moves:
            move = chess.Move.from_uci(self._moves.pop(0))
            if board.is_legal(move):
                return move
        return self._fallback.play(board)

    def stop(self) -> None:
        return None
