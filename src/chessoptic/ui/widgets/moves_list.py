"""Last moves as notation pairs ("3. Bc4  Nc6"), newest at the bottom and highlighted."""

from __future__ import annotations

import chess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QWidget

from chessoptic.core.events import GameInfo, MoveRecord
from chessoptic.ui.theme import TOKENS


def _san_html(rec: MoveRecord | None, latest: bool) -> str:
    if rec is None:
        return ""
    if latest:
        return (
            f"<span style='background:{TOKENS.turn}; color:#FFFFFF; font-weight:600; "
            f"padding:1px 6px; border-radius:4px;'>{rec.san}</span>"
        )
    return rec.san


class MovesList(QFrame):
    """Shows the last `rows` full moves; the most recent half-move gets a filled chip."""

    def __init__(self, rows: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._rows = rows
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(12, 8, 12, 8)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(4)
        self._grid.setColumnStretch(3, 1)
        mono = f"font-family: '{TOKENS.font_mono}'; font-size: 13px;"
        self._cells: list[tuple[QLabel, QLabel, QLabel, QLabel]] = []
        for row in range(rows):
            number = QLabel("", self)
            number.setStyleSheet(mono + f"color: {TOKENS.muted};")
            white = QLabel("", self)
            white.setStyleSheet(mono)
            black = QLabel("", self)
            black.setStyleSheet(mono)
            meta = QLabel("", self)
            meta.setStyleSheet(f"font-size: 11px; color: {TOKENS.muted};")
            meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for col, widget in enumerate((number, white, black, meta)):
                self._grid.addWidget(widget, row, col)
            self._cells.append((number, white, black, meta))
        self._empty = QLabel("Todavía no hay jugadas.", self)
        self._empty.setObjectName("muted")
        self._grid.addWidget(self._empty, 0, 0, 1, 4)
        self.set_info(None)

    def set_info(self, info: GameInfo | None) -> None:
        records = list(info.moves) if info else []
        self._empty.setVisible(not records)
        for cells in self._cells:
            for label in cells:
                label.setVisible(bool(records))
        if not records:
            return
        latest = records[-1]
        pairs: dict[int, tuple[MoveRecord | None, MoveRecord | None]] = {}
        for rec in records:
            w_rec, b_rec = pairs.get(rec.number, (None, None))
            if rec.color == chess.WHITE:
                w_rec = rec
            else:
                b_rec = rec
            pairs[rec.number] = (w_rec, b_rec)
        shown = sorted(pairs)[-self._rows :]
        for row, (number, white, black, meta) in enumerate(self._cells):
            if row >= len(shown):
                for label in (number, white, black, meta):
                    label.setText("")
                continue
            n = shown[row]
            w, b = pairs[n]
            number.setText(f"{n}.")
            white.setText(_san_html(w, w is latest))
            black.setText(_san_html(b, b is latest))
            if latest in (w, b):
                who = "rival" if latest.source == "opponent" else "vos"
                if info is not None and info.my_color is None:
                    who = "blancas" if latest.color == chess.WHITE else "negras"
                meta.setText(f"{who} · {latest.wall_time}")
            else:
                meta.setText("")
