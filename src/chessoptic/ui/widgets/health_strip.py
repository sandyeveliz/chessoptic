"""Three small cards: Cámara · Tablero · Enlace, each with a coloured dot."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from chessoptic.core.events import ComponentHealth, HealthLevel, HealthState
from chessoptic.ui.theme import TOKENS

LEVEL_COLORS: dict[HealthLevel, str] = {
    HealthLevel.OK: TOKENS.ok,
    HealthLevel.WARN: TOKENS.warn,
    HealthLevel.ERR: TOKENS.err,
    HealthLevel.IDLE: TOKENS.idle,
}


class HealthCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        self._dot = QLabel("•", self)
        self._label = QLabel("", self)
        self._label.setStyleSheet("font-weight: 600; font-size: 12px;")
        top.addWidget(self._dot)
        top.addWidget(self._label)
        top.addStretch(1)
        layout.addLayout(top)
        self._detail = QLabel("", self)
        self._detail.setObjectName("muted")
        self._detail.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._detail)

    def set_component(self, component: ComponentHealth) -> None:
        self._label.setText(component.label)
        self._detail.setText(component.detail)
        self._dot.setStyleSheet(f"color: {LEVEL_COLORS[component.level]}; font-size: 14px;")


class HealthStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._camera = HealthCard(self)
        self._board = HealthCard(self)
        self._link = HealthCard(self)
        for card in (self._camera, self._board, self._link):
            layout.addWidget(card, 1)
        self.set_state(HealthState.starting())

    def set_state(self, state: HealthState) -> None:
        self._camera.set_component(state.camera)
        self._board.set_component(state.board)
        self._link.set_component(state.link)
