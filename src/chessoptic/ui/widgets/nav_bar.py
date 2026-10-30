"""Bottom navigation: En vivo · Cámara · Log · Ajustes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QSizePolicy, QToolButton, QWidget

NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("live", "En vivo"),
    ("camera", "Cámara"),
    ("log", "Log"),
    ("settings", "Ajustes"),
)


class NavBar(QWidget):
    page_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for index, (key, label) in enumerate(NAV_ITEMS):
            button = QToolButton(self)
            button.setObjectName("navButton")
            button.setProperty("navKey", key)
            button.setText(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setMinimumHeight(44)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(button, 1)
            self._group.addButton(button, index)
        self._group.idClicked.connect(self.page_selected.emit)
        self.select(0)

    def select(self, index: int) -> None:
        button = self._group.button(index)
        if button is not None:
            button.setChecked(True)
