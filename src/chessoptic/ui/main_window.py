"""The side panel: header with brand + health pill, stacked pages, bottom nav."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chessoptic.core.config import AppConfig, save_config
from chessoptic.core.events import HealthLevel, HealthState
from chessoptic.ui.widgets.health_pill import HealthPill
from chessoptic.ui.widgets.nav_bar import NAV_ITEMS, NavBar

MIN_WIDTH = 300
DEFAULT_WIDTH = 380


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self.setWindowTitle("ChessOptic")
        self.setMinimumWidth(MIN_WIDTH)

        root = QWidget(self)
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        self._pages = QStackedWidget(root)
        for _key, label in NAV_ITEMS:
            self._pages.addWidget(self._placeholder(label))
        layout.addWidget(self._pages, 1)

        self._nav = NavBar(root)
        self._nav.page_selected.connect(self._pages.setCurrentIndex)
        layout.addWidget(self._nav)

        self.setCentralWidget(root)
        self.set_always_on_top(config.window.always_on_top)
        self._restore_geometry()

    # ---- building blocks -------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)

        brand = QHBoxLayout()
        brand.setSpacing(0)
        chess = QLabel("Chess", header)
        chess.setObjectName("brand")
        optic = QLabel("Optic", header)
        optic.setObjectName("brandAccent")
        brand.addWidget(chess)
        brand.addWidget(optic)
        layout.addLayout(brand)
        layout.addStretch(1)

        self._pill = HealthPill(header)
        layout.addWidget(self._pill)
        return header

    def _placeholder(self, label: str) -> QWidget:
        page = QWidget(self)
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel(label, page)
        title.setObjectName("sectionLabel")
        title.setText(label.upper())
        hint = QLabel("Próximamente", page)
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(hint, 1)
        return page

    # ---- public API used by the bridge / controller ----------------------

    def set_health(self, state: HealthState) -> None:
        self._pill.set_state(state.level, state.pill_text)

    def set_pill(self, level: HealthLevel, text: str) -> None:
        self._pill.set_state(level, text)

    def set_always_on_top(self, enabled: bool) -> None:
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if was_visible:
            self.show()
        self._config.window.always_on_top = enabled

    # ---- geometry --------------------------------------------------------

    def _restore_geometry(self) -> None:
        win = self._config.window
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = max(MIN_WIDTH, win.width or DEFAULT_WIDTH)
        if available is not None:
            height = win.height or available.height()
            x = win.x if win.x is not None else available.right() - width + 1
            y = win.y if win.y is not None else available.top()
        else:
            height = win.height or 860
            x = win.x or 0
            y = win.y or 0
        self.setGeometry(x, y, width, height)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        geometry = self.geometry()
        win = self._config.window
        win.x, win.y = geometry.x(), geometry.y()
        win.width, win.height = geometry.width(), geometry.height()
        save_config(self._config)
        super().closeEvent(event)
