"""StateBlock: the card under the health strip that changes with the driver state.

Variants follow docs/UI.md §4: my turn (blue fill), opponent turn (border), replay (brand
border + big SAN), promotion (4 buttons), mismatch (error border + squares), link lost
(error card), game over (result + reorder), and the standby cards.
"""

from __future__ import annotations

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chessoptic.core.events import (
    DetectionPhase,
    DetectionState,
    DriverState,
    DriverStateName,
    GameInfo,
    PendingOpponentMove,
    Phase,
)
from chessoptic.ui.theme import TOKENS

VARIANT_STYLE: dict[str, str] = {
    "my_turn": f"background: {TOKENS.turn}; border: 2px solid {TOKENS.turn}; color: #FFFFFF;",
    "opponent": f"background: {TOKENS.surface}; border: 2px solid {TOKENS.line_strong};",
    "replay": f"background: {TOKENS.surface}; border: 3px solid {TOKENS.brand_light};",
    "mismatch": f"background: {TOKENS.surface}; border: 2px solid {TOKENS.err};",
    "link_lost": f"background: {TOKENS.err_bg}; border: 2px solid {TOKENS.err};",
    "game_over": f"background: {TOKENS.surface}; border: 1px solid {TOKENS.line};",
    "standby": f"background: {TOKENS.surface}; border: 1px solid {TOKENS.line};",
}

PROMOTION_PIECES: tuple[tuple[int, str], ...] = (
    (chess.QUEEN, "Dama"),
    (chess.ROOK, "Torre"),
    (chess.BISHOP, "Alfil"),
    (chess.KNIGHT, "Caballo"),
)


class StateBlock(QFrame):
    new_game = Signal()
    end_game = Signal()
    resync = Signal()
    promotion_chosen = Signal(int)
    export_pgn = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stateBlock")
        # Keep the card at its natural height: the camera view is what shrinks, never the buttons.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._variant = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self._label = QLabel("", self)
        self._label.setStyleSheet("font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        self._title = QLabel("", self)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"font-family: '{TOKENS.font_display}'; font-size: 17px; font-weight: 600;"
        )
        self._big = QLabel("", self)
        self._big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._big.setStyleSheet(
            f"font-family: '{TOKENS.font_mono}'; font-size: 34px; font-weight: 600; "
            f"color: {TOKENS.turn};"
        )
        self._detail = QLabel("", self)
        self._detail.setWordWrap(True)
        self._detail.setStyleSheet("font-size: 12px;")
        self._detection_label = QLabel("", self)
        self._detection_label.setWordWrap(True)
        self._detection_label.hide()
        layout.addWidget(self._label)
        layout.addWidget(self._title)
        layout.addWidget(self._big)
        layout.addWidget(self._detail)
        layout.addWidget(self._detection_label)

        self._buttons = QWidget(self)
        self._buttons_layout = QGridLayout(self._buttons)
        self._buttons_layout.setContentsMargins(0, 4, 0, 0)
        self._buttons_layout.setSpacing(8)
        layout.addWidget(self._buttons)

        self._state: DriverState | None = None
        self._info: GameInfo | None = None
        self._pending: PendingOpponentMove | None = None
        self._both_sides = True
        self._detection: DetectionState | None = None
        self.refresh()

    # ---- inputs ----------------------------------------------------------

    def set_state(self, state: DriverState) -> None:
        self._state = state
        self.refresh()

    def set_info(self, info: GameInfo) -> None:
        self._info = info
        self._both_sides = info.both_sides
        self.refresh()

    def set_pending(self, pending: PendingOpponentMove | None) -> None:
        self._pending = pending
        self.refresh()

    def set_detection(self, detection: DetectionState) -> None:
        """Second line of the card: what the camera is doing right now (docs/STATES.md)."""
        self._detection = detection
        self._render_detection()

    def _render_detection(self) -> None:
        detection = self._detection
        if detection is None or detection.phase == DetectionPhase.IDLE or not detection.detail:
            self._detection_label.hide()
            return
        light = self._variant == "my_turn"
        colors = {
            DetectionPhase.WAITING: "rgba(255,255,255,0.85)" if light else TOKENS.muted,
            DetectionPhase.HAND: "#FFFFFF" if light else TOKENS.turn,
            DetectionPhase.READING: "#FFFFFF" if light else TOKENS.turn,
            DetectionPhase.LIFTED: "#FFFFFF" if light else TOKENS.turn,
            DetectionPhase.SEEN: "#FFFFFF" if light else TOKENS.ok,
            DetectionPhase.ACCEPTED: "#FFFFFF" if light else TOKENS.ok,
            DetectionPhase.UNEXPLAINED: "#FFE2A8" if light else TOKENS.warn,
            DetectionPhase.MISMATCH: TOKENS.err,
            DetectionPhase.THINKING: TOKENS.muted,
        }
        color = colors.get(detection.phase, TOKENS.muted)
        self._detection_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color};")
        self._detection_label.setText(f"• {detection.detail}")
        self._detection_label.show()

    # ---- rendering -------------------------------------------------------

    def _apply_variant(self, variant: str) -> None:
        if variant != self._variant:
            self._variant = variant
            self.setStyleSheet(
                f"QFrame#stateBlock {{ {VARIANT_STYLE[variant]} border-radius: 10px; }}"
            )
        light = variant == "my_turn"
        color = "#FFFFFF" if light else TOKENS.ink
        muted = "rgba(255,255,255,0.85)" if light else TOKENS.muted
        self._label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; letter-spacing: 1px; color: {muted};"
        )
        self._title.setStyleSheet(
            f"font-family: '{TOKENS.font_display}'; font-size: 17px; font-weight: 600; "
            f"color: {color};"
        )
        self._detail.setStyleSheet(f"font-size: 12px; color: {muted};")
        self._render_detection()

    def _set_buttons(self, specs: list[tuple[str, object, bool]]) -> None:
        while self._buttons_layout.count():
            item = self._buttons_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        columns = 2 if len(specs) > 2 else max(1, len(specs))
        for index, (text, slot, primary) in enumerate(specs):
            button = QPushButton(text, self._buttons)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if primary:
                button.setProperty("primary", "true")
            button.clicked.connect(slot)
            self._buttons_layout.addWidget(button, index // columns, index % columns)
        self._buttons.setVisible(bool(specs))

    def refresh(self) -> None:
        state = self._state
        info = self._info
        name = state.state if state else DriverStateName.STARTING
        detail = state.detail if state else ""
        self._big.hide()
        turn_text = ""
        if info is not None:
            turn_text = "Mueven blancas" if info.turn == chess.WHITE else "Mueven negras"

        if state is None or state.phase == Phase.STANDBY:
            self._apply_variant("standby")
            if name == DriverStateName.READY:
                self._label.setText("LISTO")
                self._title.setText("Listo para jugar")
                self._detail.setText(detail)
                specs: list[tuple[str, object, bool]] = []
                if not self._both_sides:
                    specs.append(("Empezar partida", self.new_game.emit, True))
                self._set_buttons(specs)
            elif name == DriverStateName.VERIFYING_BOARD:
                self._label.setText("TABLERO")
                self._title.setText("Armá la posición inicial")
                self._detail.setText(
                    detail or "Cuando las 32 piezas estén en su lugar, sigue solo."
                )
                self._set_buttons([])
            else:
                self._label.setText("")
                self._title.setText("Iniciando")
                self._detail.setText(detail)
                self._set_buttons([])
            return

        if name in (DriverStateName.MY_TURN, DriverStateName.MOVING):
            self._apply_variant("my_turn")
            self._label.setText(turn_text.upper() if self._both_sides else "TU TURNO")
            if name == DriverStateName.MOVING:
                self._title.setText("Detectando…")
            else:
                self._title.setText("Seguimiento de la partida" if self._both_sides else "Tu turno")
            last = ""
            if info is not None and info.moves:
                rec = info.moves[-1]
                last = f"Última: {rec.number}{'.' if rec.color else '…'} {rec.san}"
            self._detail.setText(last or "Hacé tu jugada en el tablero.")
            self._set_buttons([("Terminar", self.end_game.emit, False)])
        elif name == DriverStateName.OPPONENT_TURN:
            self._apply_variant("opponent")
            self._label.setText("TURNO DEL RIVAL")
            self._title.setText("Esperando…")
            sent = info.last_sent if info else None
            self._detail.setText(f"Tu jugada: {sent} · enviada y aceptada" if sent else detail)
            self._set_buttons([("Terminar", self.end_game.emit, False)])
        elif name in (DriverStateName.REPLAY, DriverStateName.VERIFYING):
            self._apply_variant("replay")
            self._label.setText("RIVAL JUGÓ · REPRODUCILA EN EL TABLERO")
            pending = self._pending
            self._title.setText("")
            self._big.setText(pending.san if pending else detail)
            self._big.show()
            self._detail.setText(pending.human_text if pending else "")
            self._set_buttons([("Terminar", self.end_game.emit, False)])
        elif name == DriverStateName.PROMOTION:
            self._apply_variant("replay")
            self._label.setText("PROMOCIÓN")
            self._title.setText("¿Qué pieza pusiste?")
            self._detail.setText(detail)
            self._set_buttons(
                [
                    (
                        label,
                        (lambda _=False, p=piece: self.promotion_chosen.emit(p)),
                        piece == chess.QUEEN,
                    )
                    for piece, label in PROMOTION_PIECES
                ]
            )
        elif name == DriverStateName.MISMATCH:
            self._apply_variant("mismatch")
            self._label.setText("⚠ LA POSICIÓN NO COINCIDE")
            self._title.setText("Revisá las casillas marcadas")
            pending_text = (
                f" Jugada del rival pendiente: {self._pending.san}." if self._pending else ""
            )
            self._detail.setText(
                (
                    f"Casillas: {detail}. Corregí las piezas y la jugada se verifica sola."
                    if detail
                    else "Corregí las piezas marcadas y la jugada se verifica sola."
                )
                + pending_text
            )
            self._set_buttons([("Resincronizar", self.resync.emit, True)])
        elif name == DriverStateName.LINK_LOST:
            self._apply_variant("link_lost")
            self._label.setText("ENLACE PERDIDO")
            self._title.setText("Se perdió la conexión con el proveedor")
            self._detail.setText(detail or "Reconectá desde Ajustes.")
            self._set_buttons([("Terminar", self.end_game.emit, False)])
        elif name == DriverStateName.GAME_OVER:
            self._apply_variant("game_over")
            self._label.setText("PARTIDA TERMINADA")
            result = info.result if info and info.result else ""
            self._title.setText(result or "Fin de partida")
            moves = len(info.moves) if info else 0
            self._detail.setText(
                f"{detail} · {moves} jugadas. Reordená el tablero para la próxima."
            )
            self._set_buttons(
                [
                    ("Exportar PGN", self.export_pgn.emit, False),
                    ("Nueva partida", self.new_game.emit, True),
                ]
            )
        else:
            self._apply_variant("standby")
            self._label.setText("")
            self._title.setText(str(name))
            self._detail.setText(detail)
            self._set_buttons([])
