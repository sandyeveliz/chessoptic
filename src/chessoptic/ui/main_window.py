"""The side panel: header with brand + health pill; either the setup wizard or the tabs."""

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

from chessoptic.core.config import save_config
from chessoptic.core.events import HealthLevel, HealthState
from chessoptic.core.runtime import CoreRuntime
from chessoptic.ui.bridge import CoreBridge
from chessoptic.ui.views.camera_tab import CameraTab
from chessoptic.ui.views.live import LiveView
from chessoptic.ui.views.log_tab import LogTab
from chessoptic.ui.views.settings_tab import SettingsTab
from chessoptic.ui.views.wizard import WizardView
from chessoptic.ui.widgets.health_pill import HealthPill
from chessoptic.ui.widgets.nav_bar import NavBar

MIN_WIDTH = 300
DEFAULT_WIDTH = 380


class MainWindow(QMainWindow):
    def __init__(self, runtime: CoreRuntime) -> None:
        super().__init__()
        self._runtime = runtime
        self._config = runtime.config
        self._bridge = CoreBridge(runtime.bus, self)
        self.setWindowTitle("ChessOptic")
        self.setMinimumWidth(MIN_WIDTH)

        root = QWidget(self)
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())

        # Two modes: wizard (no nav) and shell (tabs + nav).
        self._modes = QStackedWidget(root)
        layout.addWidget(self._modes, 1)

        self._wizard = WizardView(runtime, self._bridge, self)
        self._wizard.finished.connect(self._show_shell)
        self._modes.addWidget(self._wizard)

        shell = QWidget(self)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self._pages = QStackedWidget(shell)
        self._live = LiveView(runtime, self._bridge, shell)
        self._live.recalibrate_requested.connect(lambda: self.start_wizard(0))
        self._camera_tab = CameraTab(runtime, self._bridge, shell)
        self._camera_tab.recalibrate_requested.connect(lambda: self.start_wizard(2))
        self._camera_tab.recheck_requested.connect(lambda: self.start_wizard(3))
        self._log_tab = LogTab(self._bridge, shell)
        self._log_tab.export_pgn.connect(self._live.export_pgn)
        self._settings_tab = SettingsTab(runtime, shell)
        self._settings_tab.always_on_top_changed.connect(self.set_always_on_top)
        self._settings_tab.provider_changed.connect(lambda name: runtime.start_session(name))
        self._pages.addWidget(self._live)
        self._pages.addWidget(self._camera_tab)
        self._pages.addWidget(self._log_tab)
        self._pages.addWidget(self._settings_tab)
        shell_layout.addWidget(self._pages, 1)
        self._nav = NavBar(shell)
        self._nav.page_selected.connect(self._pages.setCurrentIndex)
        shell_layout.addWidget(self._nav)
        self._modes.addWidget(shell)

        self.setCentralWidget(root)
        self._bridge.health_changed.connect(self.set_health)
        self.set_always_on_top(self._config.window.always_on_top)
        self._restore_geometry()
        self.start_wizard(0)

    # ---- building blocks -------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        brand = QHBoxLayout()
        brand.setSpacing(0)
        chess_label = QLabel("Chess", header)
        chess_label.setObjectName("brand")
        optic_label = QLabel("Optic", header)
        optic_label.setObjectName("brandAccent")
        brand.addWidget(chess_label)
        brand.addWidget(optic_label)
        layout.addLayout(brand)
        layout.addStretch(1)
        self._pill = HealthPill(header)
        layout.addWidget(self._pill)
        return header

    # ---- modes -------------------------------------------------------------

    def start_wizard(self, step: int) -> None:
        self._modes.setCurrentIndex(0)
        self._wizard.start(step)

    def _show_shell(self) -> None:
        self._modes.setCurrentIndex(1)
        self._nav.select(0)
        self._pages.setCurrentIndex(0)

    # ---- public API --------------------------------------------------------

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

    # ---- geometry ----------------------------------------------------------

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
        self._runtime.shutdown()
        super().closeEvent(event)
