"""Three small cards: Cámara · Tablero · Enlace, each with a coloured dot."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(5)
        self._dot = QLabel("•", self)
        self._label = QLabel("", self)
        self._label.setStyleSheet("font-weight: 600; font-size: 11px;")
        self._full_detail = ""
        self._detail = QLabel("", self)
        self._detail.setObjectName("muted")
        self._detail.setStyleSheet("font-size: 11px;")
        self._detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        layout.addWidget(self._detail, 1)

    def set_component(self, component: ComponentHealth) -> None:
        self._label.setText(component.label)
        self._full_detail = component.detail
        self._elide()
        self.setToolTip(f"{component.label}: {component.detail}")
        self._dot.setStyleSheet(f"color: {LEVEL_COLORS[component.level]}; font-size: 14px;")

    def _elide(self) -> None:
        metrics = QFontMetrics(self._detail.font())
        width = max(0, self._detail.width() - 2)
        self._detail.setText(
            metrics.elidedText(self._full_detail, Qt.TextElideMode.ElideRight, width)
        )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._elide()


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
