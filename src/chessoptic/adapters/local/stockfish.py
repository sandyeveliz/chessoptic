"""StockfishAdapter: play against a local UCI engine (Stockfish by default)."""

from __future__ import annotations

import logging
import shutil
import threading
import time

import chess

from chessoptic.adapters.base import AdapterInfo, EmitFn
from chessoptic.adapters.local.engine import EngineProtocol, UciEngine
from chessoptic.core.config import AppConfig
from chessoptic.core.events import (
    AdapterError,
    GameOver,
    GameStarted,
    LinkState,
    LinkStatus,
    MoveAccepted,
    OpponentMove,
)

log = logging.getLogger(__name__)

INFO = AdapterInfo(name="stockfish", label="Stockfish local", kind="local", both_sides=False)

# UI level 1–8 → (Stockfish "Skill Level" 0–20, seconds per move)
LEVELS: dict[int, tuple[int, float]] = {
    1: (0, 0.2),
    2: (3, 0.3),
    3: (6, 0.4),
    4: (9, 0.5),
    5: (12, 0.6),
    6: (15, 0.8),
    7: (18, 1.0),
    8: (20, 1.5),
}


def find_stockfish(config: AppConfig | None = None) -> str | None:
    """Configured path first, then PATH."""
    if config is not None and config.stockfish_path:
        found = shutil.which(config.stockfish_path)
        if found:
            return found
    return shutil.which("stockfish")


def engine_from_config(config: AppConfig) -> UciEngine | None:
    path = find_stockfish(config)
    if path is None:
        return None
    skill, seconds = LEVELS.get(config.stockfish_level, LEVELS[4])
    return UciEngine(path, skill_level=skill, move_time_s=seconds)


class StockfishAdapter:
    def __init__(self, engine: EngineProtocol, my_color: bool = chess.WHITE) -> None:
        self._engine = engine
        self._my_color = my_color
        self._emit: EmitFn | None = None
        self._thinking: threading.Thread | None = None
        self._game_id = ""
        self._started = False

    @property
    def info(self) -> AdapterInfo:
        return INFO

    # ---- lifecycle ---------------------------------------------------------

    def start(self, emit: EmitFn) -> None:
        self._emit = emit
        try:
            self._engine.start()
        except Exception as exc:
            log.error("engine failed to start: %s", exc)
            emit(LinkStatus(LinkState.LOST, INFO.label, "no se pudo iniciar el motor"))
            emit(AdapterError(f"No se pudo iniciar el motor: {exc}", recoverable=False))
            return
        self._started = True
        emit(LinkStatus(LinkState.CONNECTED, self._engine.name))

    def stop(self) -> None:
        self._engine.stop()
        self._started = False
        if self._emit:
            self._emit(LinkStatus(LinkState.INACTIVE, INFO.label))
        self._emit = None

    # ---- game ------------------------------------------------------------------

    def start_game(self, board: chess.Board) -> None:
        if not self._emit:
            return
        if not self._started:
            self._emit(AdapterError("El motor no está disponible. Revisá la ruta en Ajustes."))
            return
        self._game_id = f"stockfish-{int(time.time())}"
        self._emit(GameStarted(self._game_id, self._my_color, self._engine.name, board.fen()))
        if board.turn != self._my_color:
            self._think(board.copy())

    def on_move(self, move: chess.Move, board_after: chess.Board) -> None:
        if not self._emit:
            return
        self._emit(MoveAccepted(move))
        if not board_after.is_game_over(claim_draw=True):
            self._think(board_after.copy())

    def end_game(self, result: str, reason: str) -> None:
        if self._emit:
            self._emit(GameOver(result, reason))

    # ---- thinking --------------------------------------------------------------

    def _think(self, board: chess.Board) -> None:
        game_id = self._game_id

        def worker() -> None:
            try:
                move = self._engine.play(board)
            except Exception as exc:
                log.exception("engine play failed")
                if self._emit:
                    self._emit(AdapterError(f"El motor falló: {exc}"))
                return
            if self._emit is None or game_id != self._game_id:
                return  # game ended or adapter stopped meanwhile
            self._emit(OpponentMove(move, board.san(move)))

        self._thinking = threading.Thread(target=worker, name="engine-think", daemon=True)
        self._thinking.start()
