"""Application bootstrap: QApplication, fonts, stylesheet, main window."""

from __future__ import annotations

import logging
import os
import sys

from chessoptic.core.config import load_config

log = logging.getLogger(__name__)

SMOKE_DURATION_MS = 1000


def run_app(smoke: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if smoke and not os.environ.get("QT_QPA_PLATFORM") and not _has_display():
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    # Imported after the platform decision so Qt picks it up.
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from chessoptic.ui.main_window import MainWindow
    from chessoptic.ui.theme import full_stylesheet, load_fonts

    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert isinstance(app, QApplication)
    app.setApplicationName("ChessOptic")
    app.setOrganizationName("ChessOptic")

    tokens = load_fonts()
    app.setFont(QFont(tokens.font_sans, 10))
    app.setStyleSheet(full_stylesheet(tokens))

    config = load_config()
    window = MainWindow(config)
    window.show()

    if smoke:
        QTimer.singleShot(SMOKE_DURATION_MS, app.quit)
    return int(app.exec())


def _has_display() -> bool:
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True
