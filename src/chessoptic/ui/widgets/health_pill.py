"""The driver-health 'traffic light' shown in the header."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from chessoptic.core.events import HealthLevel


class HealthPill(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("healthPill")
        self.set_state(HealthLevel.IDLE, "Iniciando")

    def set_state(self, level: HealthLevel, text: str) -> None:
        self.setText(f"•  {text}")
        if self.property("level") != str(level):
            self.setProperty("level", str(level))
            # Dynamic property changed: re-polish so the QSS selector applies.
            style = self.style()
            style.unpolish(self)
            style.polish(self)
