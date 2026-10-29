"""Last few moves in monospace with their wall time."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from chessoptic.core.events import GameInfo
from chessoptic.ui.theme import TOKENS


class MovesList(QWidget):
    def __init__(self, rows: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = rows
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._labels: list[QLabel] = []
        for _ in range(rows):
            label = QLabel("", self)
            label.setStyleSheet(f"font-family: '{TOKENS.font_mono}'; font-size: 12px;")
            layout.addWidget(label)
            self._labels.append(label)
        self.set_info(None)

    def set_info(self, info: GameInfo | None) -> None:
        records = list(info.moves[-self._rows :]) if info else []
        records.reverse()
        for i, label in enumerate(self._labels):
            if i < len(records):
                rec = records[i]
                who = (
                    "rival"
                    if rec.source == "opponent"
                    else ("jugada" if info and info.my_color is None else "enviada")
                )
                number = f"{rec.number}{'.' if rec.color else '…'}"
                label.setText(
                    f"<span style='color:{TOKENS.muted}'>{rec.wall_time}</span>  "
                    f"<span style='color:{TOKENS.muted}'>{who}</span>  {number} {rec.san}"
                )
            else:
                label.setText("")
