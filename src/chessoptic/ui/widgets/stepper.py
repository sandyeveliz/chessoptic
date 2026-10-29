"""Progress bar of N segments for the setup wizard."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from chessoptic.ui.theme import TOKENS


class Stepper(QWidget):
    def __init__(self, steps: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._steps = steps
        self._current = 0
        self.setFixedHeight(6)

    def set_current(self, index: int) -> None:
        self._current = index
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        gap = 4.0
        width = (self.width() - gap * (self._steps - 1)) / self._steps
        for i in range(self._steps):
            color = TOKENS.turn if i <= self._current else TOKENS.line_strong
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(i * (width + gap), 1, width, 4), 2, 2)
        painter.end()
