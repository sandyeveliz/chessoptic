"""'Log' tab: filtered event list, export PGN and export log."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from chessoptic.core.events import LogEntry
from chessoptic.ui.bridge import CoreBridge
from chessoptic.ui.theme import TOKENS

FILTERS: tuple[tuple[str, str], ...] = (
    ("all", "Todo"),
    ("move", "Jugadas"),
    ("event", "Eventos"),
    ("error", "Errores"),
)
KIND_COLORS = {"move": TOKENS.turn, "event": TOKENS.muted, "error": TOKENS.err}
MAX_ENTRIES = 500


class LogTab(QWidget):
    export_pgn = Signal()

    def __init__(self, bridge: CoreBridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[LogEntry] = []
        self._filter = "all"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        title = QLabel("LOG", self)
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        filters = QHBoxLayout()
        self._group = QButtonGroup(self)
        for key, label in FILTERS:
            button = QToolButton(self)
            button.setObjectName("navButton")
            button.setText(label)
            button.setCheckable(True)
            button.setChecked(key == "all")
            button.setProperty("filter", key)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(button)
            filters.addWidget(button)
        filters.addStretch(1)
        self._group.buttonClicked.connect(self._on_filter)
        layout.addLayout(filters)

        self._list = QListWidget(self)
        self._list.setStyleSheet(
            f"QListWidget {{ background: {TOKENS.surface}; border: 1px solid {TOKENS.line}; "
            f"border-radius: 8px; font-family: '{TOKENS.font_mono}'; font-size: 12px; }}"
            "QListWidget::item { padding: 4px 8px; }"
        )
        layout.addWidget(self._list, 1)

        actions = QHBoxLayout()
        pgn = QPushButton("Exportar PGN", self)
        pgn.clicked.connect(self.export_pgn.emit)
        log_button = QPushButton("Exportar log", self)
        log_button.clicked.connect(self._export_log)
        actions.addWidget(pgn)
        actions.addWidget(log_button)
        layout.addLayout(actions)

        bridge.log_entry.connect(self.add_entry)

    def add_entry(self, entry: LogEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > MAX_ENTRIES:
            self._entries.pop(0)
        if self._filter in ("all", entry.kind):
            self._append_item(entry)

    def _append_item(self, entry: LogEntry) -> None:
        item = QListWidgetItem(f"{entry.wall_time}  {entry.text}")
        item.setForeground(Qt.GlobalColor.black)
        color = KIND_COLORS.get(entry.kind, TOKENS.ink)
        item.setData(Qt.ItemDataRole.ForegroundRole, color)
        self._list.insertItem(0, item)

    def _on_filter(self, button: QToolButton) -> None:
        self._filter = str(button.property("filter"))
        self._list.clear()
        for entry in self._entries:
            if self._filter in ("all", entry.kind):
                self._append_item(entry)

    def _export_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar log", "chessoptic.log", "Log (*.log *.txt)"
        )
        if not path:
            return
        Path(path).write_text(
            "\n".join(f"{e.wall_time} [{e.kind}] {e.text}" for e in self._entries),
            encoding="utf-8",
        )
