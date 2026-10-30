"""GameSession: the state machine between the board tracker, the provider and the UI.

States (docs/STATES.md): standby VERIFYING_BOARD → READY; in game MY_TURN ⇄ MOVING,
OPPONENT_TURN → REPLAY → MY_TURN, PROMOTION, MISMATCH, LINK_LOST, GAME_OVER.
All inputs (vision thread, provider callbacks, UI actions) are serialised by one lock.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import chess

from chessoptic.adapters.base import OutputAdapter
from chessoptic.board.model import BoardModel
from chessoptic.board.occupancy import Grid
from chessoptic.board.tracker import BoardTracker
from chessoptic.core.bus import EventBus
from chessoptic.core.events import (
    AdapterError,
    DriverState,
    DriverStateName,
    GameInfo,
    GameOver,
    GameStarted,
    InitialPositionCheck,
    LinkState,
    LinkStatus,
    LogEntry,
    MoveAccepted,
    MoveAmbiguous,
    MoveDetected,
    MoveRecord,
    MoveRejected,
    OccupancyFrame,
    OpponentMove,
    PendingOpponentMove,
    Phase,
    PositionMatched,
    PositionMismatch,
)
from chessoptic.game.modes import GameMode
from chessoptic.game.outcome import result_and_reason
from chessoptic.game.pgn import save_pgn

log = logging.getLogger(__name__)

PIECE_NAMES = {
    chess.PAWN: "peón",
    chess.KNIGHT: "caballo",
    chess.BISHOP: "alfil",
    chess.ROOK: "torre",
    chess.QUEEN: "dama",
    chess.KING: "rey",
}

STANDBY_STATES = {
    DriverStateName.STARTING,
    DriverStateName.VERIFYING_BOARD,
    DriverStateName.READY,
    DriverStateName.PAUSED,
}


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


class GameSession:
    def __init__(
        self,
        bus: EventBus,
        adapter: OutputAdapter,
        mode: GameMode,
        mismatch_grace_ms: int = 2000,
        promotion_default: str = "ask",
        on_accept: Callable[[Grid], None] | None = None,
    ) -> None:
        self._bus = bus
        self._adapter = adapter
        self._mode = mode
        self._promotion_default = promotion_default
        self._lock = threading.RLock()
        self._model = BoardModel(both_sides=adapter.info.both_sides)
        self._tracker = BoardTracker(self._model, mismatch_grace_ms, on_accept=on_accept)
        self._state = DriverStateName.VERIFYING_BOARD
        self._state_before_issue: DriverStateName = DriverStateName.MY_TURN
        self._my_color: bool | None = None
        self._platform = adapter.info.label
        self._moves: list[MoveRecord] = []
        self._result: str | None = None
        self._initial_fen = chess.STARTING_FEN
        self._pending_my_move: tuple[chess.Move, str] | None = None
        self._promotion_candidates: tuple[chess.Move, ...] = ()
        self._pending_opponent: PendingOpponentMove | None = None
        self._last_sent: str | None = None
        self._last_opponent: str | None = None
        self._link = LinkState.INACTIVE
        self._detail = ""
        self._unsubscribe: list[Callable[[], None]] = []

    # ---- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._unsubscribe.append(self._bus.subscribe(OccupancyFrame, self._on_occupancy))
        self._unsubscribe.append(self._bus.subscribe(InitialPositionCheck, self._on_initial_check))
        self._adapter.start(self._on_adapter_event)
        self._publish_all()

    def stop(self) -> None:
        for unsub in self._unsubscribe:
            unsub()
        self._unsubscribe.clear()
        self._adapter.stop()

    # ---- UI actions --------------------------------------------------------

    def new_game(self) -> None:
        with self._lock:
            if self._state not in STANDBY_STATES and self._state != DriverStateName.GAME_OVER:
                return
            self._reset_game()
            if self._adapter.info.both_sides:
                # Tracking: the game starts with the first detected move.
                self._set_state(DriverStateName.READY, "Hacé la primera jugada en el tablero.")
                return
            self._adapter.start_game(self._model.board.copy())

    def end_game(self) -> None:
        with self._lock:
            if self._state in STANDBY_STATES:
                return
            self._adapter.end_game("*", "terminada desde ChessOptic")

    def resync(self) -> None:
        with self._lock:
            self._tracker.reset_mismatch()
            if self._state == DriverStateName.MISMATCH:
                self._set_state(self._state_before_issue, "Revisando la posición…")

    def set_promotion(self, piece: int) -> None:
        with self._lock:
            if self._state != DriverStateName.PROMOTION:
                return
            chosen = next((m for m in self._promotion_candidates if m.promotion == piece), None)
            if chosen is None:
                return
            self._promotion_candidates = ()
            fen_before = self._model.fen
            san = self._model.push(chosen)
            self._tracker.notify_accept()
            self._handle_my_move(MoveDetected(chosen, san, fen_before, self._model.fen))

    def export_pgn(self) -> Path | None:
        with self._lock:
            if not self._moves:
                return None
            path = save_pgn(self.info, self._initial_fen)
            self._log("event", f"PGN exportado: {path.name}")
            return path

    # ---- snapshots ---------------------------------------------------------

    @property
    def state(self) -> DriverState:
        return DriverState(self._phase(), self._state, self._detail)

    @property
    def info(self) -> GameInfo:
        return GameInfo(
            my_color=self._my_color,
            platform=self._platform,
            moves=tuple(self._moves),
            result=self._result,
            turn=self._model.board.turn,
            fen=self._model.fen,
            last_sent=self._last_sent,
            last_opponent=self._last_opponent,
            both_sides=self._adapter.info.both_sides,
        )

    def _phase(self) -> Phase:
        return Phase.STANDBY if self._state in STANDBY_STATES else Phase.IN_GAME

    # ---- vision input ------------------------------------------------------

    def _on_initial_check(self, check: InitialPositionCheck) -> None:
        with self._lock:
            if self._state not in (DriverStateName.VERIFYING_BOARD, DriverStateName.READY):
                return
            if check.complete and self._state == DriverStateName.VERIFYING_BOARD:
                self._model.reset()
                self._tracker.clear_target()
                self._tracker.reset_mismatch()
                hint = (
                    "Hacé la primera jugada en el tablero."
                    if self._adapter.info.both_sides
                    else "Apretá «Empezar partida»."
                )
                self._set_state(DriverStateName.READY, hint)
            elif (
                not check.complete
                and self._state == DriverStateName.READY
                and not self._adapter.info.both_sides
            ):
                # With an opponent the game starts on request; while waiting, keep the
                # board verified. When tracking both sides the tracker decides instead:
                # a legal move starts the game, anything else is a mismatch.
                self._set_state(
                    DriverStateName.VERIFYING_BOARD,
                    f"Blancas {check.white}/16 · Negras {check.black}/16",
                )

    def _on_occupancy(self, frame: OccupancyFrame) -> None:
        with self._lock:
            state = self._state
            if state in (
                DriverStateName.VERIFYING_BOARD,
                DriverStateName.PAUSED,
                DriverStateName.GAME_OVER,
                DriverStateName.LINK_LOST,
                DriverStateName.OPPONENT_TURN,
                DriverStateName.PROMOTION,
            ):
                return
            if state == DriverStateName.READY and not self._adapter.info.both_sides:
                return
            if state in (DriverStateName.MY_TURN, DriverStateName.MOVING):
                if not frame.stable:
                    if state == DriverStateName.MY_TURN:
                        self._set_state(DriverStateName.MOVING, "Detectando…")
                    return
                if state == DriverStateName.MOVING:
                    self._set_state(DriverStateName.MY_TURN, "")
            for event in self._tracker.on_occupancy(frame):
                self._on_tracker_event(event)

    def _on_tracker_event(self, event: object) -> None:
        state = self._state
        if isinstance(event, MoveDetected):
            if state == DriverStateName.READY:
                board_before = chess.Board(event.fen_before)
                self._adapter.start_game(board_before)  # emits GameStarted synchronously
            self._handle_my_move(event)
        elif isinstance(event, MoveAmbiguous):
            if self._promotion_default != "ask":
                piece = {"queen": chess.QUEEN, "rook": chess.ROOK, "bishop": chess.BISHOP}.get(
                    self._promotion_default, chess.QUEEN
                )
                chosen = next((m for m in event.candidates if m.promotion == piece), None)
                if chosen is not None:
                    fen_before = self._model.fen
                    san = self._model.push(chosen)
                    self._handle_my_move(MoveDetected(chosen, san, fen_before, self._model.fen))
                    return
            self._promotion_candidates = event.candidates
            self._set_state(DriverStateName.PROMOTION, "Elegí la pieza de la promoción.")
        elif isinstance(event, PositionMismatch):
            if state in STANDBY_STATES:
                if state == DriverStateName.READY:
                    names = ", ".join(chess.square_name(i.square) for i in event.issues[:6])
                    self._tracker.reset_mismatch()
                    self._set_state(DriverStateName.VERIFYING_BOARD, f"Revisá {names}.")
                return
            self._state_before_issue = (
                state if state != DriverStateName.MISMATCH else self._state_before_issue
            )
            names = ", ".join(chess.square_name(i.square) for i in event.issues[:6])
            self._bus.publish(event)
            self._log("error", f"posición no coincide: {names}")
            self._set_state(DriverStateName.MISMATCH, names)
        elif isinstance(event, PositionMatched):
            if state == DriverStateName.MISMATCH:
                self._set_state(self._state_before_issue, "")
                self._bus.publish(event)
            if self._pending_opponent is not None and self._tracker.expecting is None:
                record = self._record(
                    self._pending_opponent.uci, self._pending_opponent.san, "opponent"
                )
                self._last_opponent = record.san
                self._pending_opponent = None
                self._publish_pending(None)
                self._log(
                    "move",
                    f"rival {record.number}{'.' if record.color else '…'} "
                    f"{record.san} · verificada",
                )
                self._set_state(DriverStateName.MY_TURN, "")
                self._publish_info()
                self._check_game_over()

    def _handle_my_move(self, event: MoveDetected) -> None:
        self._pending_my_move = (event.move, event.san)
        self._adapter.on_move(event.move, self._model.board.copy())

    # ---- provider input ------------------------------------------------------

    def _on_adapter_event(self, event: object) -> None:
        with self._lock:
            if isinstance(event, LinkStatus):
                self._link = event.state
                self._bus.publish(event)
                if event.state == LinkState.LOST and self._state not in STANDBY_STATES:
                    self._state_before_issue = self._state
                    self._set_state(DriverStateName.LINK_LOST, event.detail)
                elif (
                    event.state == LinkState.CONNECTED and self._state == DriverStateName.LINK_LOST
                ):
                    self._set_state(self._state_before_issue, "")
            elif isinstance(event, GameStarted):
                self._my_color = event.my_color
                self._platform = event.platform
                self._initial_fen = event.initial_fen
                self._result = None
                self._log("event", f"partida iniciada · {event.platform}")
                mine = event.my_color is None or event.my_color == self._model.board.turn
                self._set_state(
                    DriverStateName.MY_TURN if mine else DriverStateName.OPPONENT_TURN, ""
                )
                self._publish_info()
            elif isinstance(event, MoveAccepted):
                if self._pending_my_move is None:
                    return
                move, san = self._pending_my_move
                self._pending_my_move = None
                record = self._record(move.uci(), san, "detected")
                self._last_sent = san
                self._log(
                    "move",
                    f"{'enviada' if not self._adapter.info.both_sides else 'jugada'} "
                    f"{record.number}{'.' if record.color else '…'} {san}",
                )
                if self._adapter.info.both_sides:
                    self._set_state(DriverStateName.MY_TURN, "")
                else:
                    self._set_state(DriverStateName.OPPONENT_TURN, "Esperando…")
                self._publish_info()
                self._check_game_over()
            elif isinstance(event, MoveRejected):
                self._pending_my_move = None
                self._log("error", f"jugada rechazada: {event.reason}")
                self._bus.publish(AdapterError(f"Jugada rechazada: {event.reason}"))
                # The model already has the move; undo it so the board can be corrected.
                self._model.pop()
                self._state_before_issue = DriverStateName.MY_TURN
                self._set_state(DriverStateName.MISMATCH, "Deshacé la jugada en el tablero.")
            elif isinstance(event, OpponentMove):
                self._tracker.expect(event.move)
                self._pending_opponent = self._describe(event.move, event.san)
                self._publish_pending(self._pending_opponent)
                self._log("move", f"rival {event.san} · recibida")
                self._set_state(DriverStateName.REPLAY, event.san)
            elif isinstance(event, GameOver):
                self._result = event.result
                self._log("event", f"fin de partida · {event.result} · {event.reason}")
                self._tracker.clear_target()
                self._publish_pending(None)
                self._set_state(DriverStateName.GAME_OVER, f"{event.result} · {event.reason}")
                self._publish_info()
            elif isinstance(event, AdapterError):
                self._log("error", event.message)
                self._bus.publish(event)

    # ---- helpers -----------------------------------------------------------

    def _check_game_over(self) -> None:
        ended = result_and_reason(self._model.board)
        if ended is None or self._state == DriverStateName.GAME_OVER:
            return
        self._on_adapter_event(GameOver(ended[0], ended[1]))

    def _reset_game(self) -> None:
        self._model.reset()
        self._tracker.clear_target()
        self._tracker.reset_mismatch()
        self._moves = []
        self._result = None
        self._pending_my_move = None
        self._pending_opponent = None
        self._promotion_candidates = ()
        self._last_sent = None
        self._last_opponent = None
        self._publish_pending(None)
        self._set_state(DriverStateName.VERIFYING_BOARD, "Armá la posición inicial.")
        self._publish_info()

    def _record(self, uci: str, san: str, source: str) -> MoveRecord:
        board_after = self._model.board
        color = not board_after.turn  # the side that just moved
        # fullmove_number only increments after Black's move.
        number = (
            board_after.fullmove_number if color == chess.WHITE else board_after.fullmove_number - 1
        )
        record = MoveRecord(number, color, san, uci, source, _now())
        self._moves.append(record)
        return record

    def _describe(self, move: chess.Move, san: str) -> PendingOpponentMove:
        board = self._model.board
        piece = board.piece_at(move.from_square)
        name = PIECE_NAMES.get(piece.piece_type, "pieza") if piece else "pieza"
        special: str | None = None
        if board.is_castling(move):
            special = "castle"
            text = "Enrocá: mové el rey dos casillas y pasá la torre."
        elif board.is_en_passant(move):
            special = "en_passant"
            text = (
                f"Captura al paso: el peón va a {chess.square_name(move.to_square)} "
                "y sacá el peón capturado."
            )
        elif move.promotion:
            special = "promotion"
            text = (
                f"Promoción en {chess.square_name(move.to_square)}: "
                f"poné una {PIECE_NAMES.get(move.promotion, 'pieza')}."
            )
        else:
            text = (
                f"Mové el {name} de {chess.square_name(move.from_square)} "
                f"a {chess.square_name(move.to_square)}."
            )
            if board.is_capture(move):
                text += " Sacá la pieza capturada."
        return PendingOpponentMove(
            san, move.uci(), name, move.from_square, move.to_square, special, text
        )

    def _set_state(self, state: DriverStateName, detail: str) -> None:
        self._state = state
        self._detail = detail
        self._bus.publish(self.state)

    def _publish_info(self) -> None:
        self._bus.publish(self.info)

    def _publish_pending(self, pending: PendingOpponentMove | None) -> None:
        self._bus.publish(PendingOpponentChanged(pending))

    def _publish_all(self) -> None:
        self._bus.publish(self.state)
        self._publish_info()
        self._publish_pending(self._pending_opponent)

    def _log(self, kind: str, text: str) -> None:
        self._bus.publish(LogEntry(_now(), kind, text))


@dataclass(frozen=True)
class PendingOpponentChanged:
    """Bus payload for 'pending opponent move changed' (None clears it)."""

    pending: PendingOpponentMove | None
