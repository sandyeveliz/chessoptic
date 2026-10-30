"""'Ajustes' tab: provider, detection, window. Writes straight to AppConfig."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from chessoptic.adapters import AVAILABLE
from chessoptic.core.config import save_config
from chessoptic.core.runtime import CoreRuntime
from chessoptic.ui.theme import user_theme_path

PROMOTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("ask", "Preguntar"),
    ("queen", "Siempre dama"),
)


def _group(parent: QWidget, title: str) -> tuple[QFrame, QVBoxLayout]:
    label = QLabel(title.upper(), parent)
    label.setObjectName("sectionLabel")
    frame = QFrame(parent)
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(8)
    parent.layout().addWidget(label)  # type: ignore[union-attr]
    parent.layout().addWidget(frame)  # type: ignore[union-attr]
    return frame, layout


def _row(layout: QVBoxLayout, label: str, widget: QWidget) -> None:
    row = QHBoxLayout()
    text = QLabel(label, widget.parentWidget())
    text.setStyleSheet("font-weight: 600;")
    row.addWidget(text)
    row.addStretch(1)
    row.addWidget(widget)
    layout.addLayout(row)


class SettingsTab(QWidget):
    always_on_top_changed = Signal(bool)
    provider_changed = Signal(str)

    def __init__(self, runtime: CoreRuntime, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runtime = runtime
        config = runtime.config
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        page = QWidget(self)
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # ---- provider
        _, provider_layout = _group(page, "Proveedor")
        self._provider = QComboBox(page)
        for info in AVAILABLE:
            self._provider.addItem(info.label, info.name)
        self._provider.addItem("Lichess (próximamente)", "lichess")
        model = self._provider.model()
        model.item(self._provider.count() - 1).setEnabled(False)  # type: ignore[attr-defined]
        current = self._provider.findData(config.provider)
        self._provider.setCurrentIndex(max(0, current))
        self._provider.currentIndexChanged.connect(self._on_provider)
        _row(provider_layout, "Plataforma", self._provider)
        self._promotion = QComboBox(page)
        for key, label in PROMOTION_OPTIONS:
            self._promotion.addItem(label, key)
        self._promotion.setCurrentIndex(max(0, self._promotion.findData(config.promotion_default)))
        self._promotion.currentIndexChanged.connect(self._on_promotion)
        _row(provider_layout, "Promoción", self._promotion)

        # ---- stockfish
        _, sf_layout = _group(page, "Stockfish")
        path_row = QHBoxLayout()
        self._sf_path = QLineEdit(page)
        self._sf_path.setPlaceholderText("stockfish (en el PATH) o ruta al ejecutable")
        self._sf_path.setText(config.stockfish_path or "")
        self._sf_path.editingFinished.connect(self._on_sf_path)
        browse = QPushButton("Buscar…", page)
        browse.clicked.connect(self._browse_stockfish)
        path_row.addWidget(self._sf_path, 1)
        path_row.addWidget(browse)
        sf_layout.addLayout(path_row)
        self._sf_status = QLabel("", page)
        self._sf_status.setObjectName("muted")
        self._sf_status.setWordWrap(True)
        sf_layout.addWidget(self._sf_status)
        self._sf_level = QSlider(Qt.Orientation.Horizontal, page)
        self._sf_level.setRange(1, 8)
        self._sf_level.setValue(config.stockfish_level)
        self._sf_level.setFixedWidth(140)
        self._sf_level.valueChanged.connect(self._on_sf_level)
        _row(sf_layout, "Nivel", self._sf_level)
        self._sf_level_hint = QLabel("", page)
        self._sf_level_hint.setObjectName("muted")
        sf_layout.addWidget(self._sf_level_hint)
        self._on_sf_level(config.stockfish_level)
        self._color = QComboBox(page)
        self._color.addItem("Blancas", "white")
        self._color.addItem("Negras", "black")
        self._color.setCurrentIndex(max(0, self._color.findData(config.my_color)))
        self._color.currentIndexChanged.connect(self._on_color)
        _row(sf_layout, "Jugás con", self._color)
        self._refresh_stockfish_status()

        # ---- detection
        _, detection_layout = _group(page, "Detección")
        self._stability = QSlider(Qt.Orientation.Horizontal, page)
        self._stability.setRange(250, 2000)
        self._stability.setSingleStep(50)
        self._stability.setValue(config.stability_ms)
        self._stability.setFixedWidth(140)
        _row(detection_layout, "Estabilidad", self._stability)
        self._stability_hint = QLabel("", page)
        self._stability_hint.setObjectName("muted")
        self._stability_hint.setWordWrap(True)
        detection_layout.addWidget(self._stability_hint)
        self._stability.valueChanged.connect(self._on_stability_preview)
        self._stability.sliderReleased.connect(self._on_stability)
        self._on_stability_preview(config.stability_ms)
        self._frames = QCheckBox("Guardar frames de errores", page)
        self._frames.setChecked(config.save_error_frames)
        self._frames.toggled.connect(self._on_frames)
        detection_layout.addWidget(self._frames)

        # ---- window
        _, window_layout = _group(page, "Ventana")
        self._on_top = QCheckBox("Siempre arriba", page)
        self._on_top.setChecked(config.window.always_on_top)
        self._on_top.toggled.connect(self.always_on_top_changed.emit)
        window_layout.addWidget(self._on_top)
        theme_row = QHBoxLayout()
        theme_label = QLabel(f"Tema: {user_theme_path()}", page)
        theme_label.setObjectName("muted")
        theme_label.setWordWrap(True)
        theme_row.addWidget(theme_label, 1)
        window_layout.addLayout(theme_row)
        hint = QLabel(
            "Creá ese archivo con reglas QSS (sintaxis tipo CSS) para sobreescribir el tema; "
            "se aplica al reiniciar.",
            page,
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        window_layout.addWidget(hint)

        # ---- diagnostics
        _, diag_layout = _group(page, "Diagnóstico")
        self._diag = QLabel("—", page)
        self._diag.setObjectName("mono")
        diag_layout.addWidget(self._diag)
        doctor = QPushButton("Abrir carpeta de configuración", page)
        doctor.clicked.connect(self._open_config_dir)
        diag_layout.addWidget(doctor)
        layout.addStretch(1)

    # ---- handlers ------------------------------------------------------------

    def set_diagnostics(self, text: str) -> None:
        self._diag.setText(text)

    def _on_provider(self, index: int) -> None:
        name = str(self._provider.itemData(index))
        self._runtime.config.provider = name
        save_config(self._runtime.config)
        self.provider_changed.emit(name)

    def _on_sf_path(self) -> None:
        text = self._sf_path.text().strip()
        self._runtime.config.stockfish_path = text or None
        save_config(self._runtime.config)
        self._refresh_stockfish_status()

    def _browse_stockfish(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ejecutable de Stockfish")
        if path:
            self._sf_path.setText(path)
            self._on_sf_path()

    def _refresh_stockfish_status(self) -> None:
        from chessoptic.adapters.local.stockfish import find_stockfish

        found = find_stockfish(self._runtime.config)
        self._sf_status.setText(
            f"Encontrado: {found}"
            if found
            else "No se encontró Stockfish. Instalalo o indicá la ruta."
        )

    def _on_sf_level(self, value: int) -> None:
        self._runtime.config.stockfish_level = int(value)
        save_config(self._runtime.config)
        labels = {
            1: "muy fácil",
            2: "fácil",
            3: "principiante",
            4: "club",
            5: "fuerte",
            6: "muy fuerte",
            7: "experto",
            8: "máximo",
        }
        self._sf_level_hint.setText(f"Nivel {value} · {labels.get(value, '')}")

    def _on_color(self, index: int) -> None:
        self._runtime.config.my_color = str(self._color.itemData(index))
        save_config(self._runtime.config)

    def _on_promotion(self, index: int) -> None:
        self._runtime.config.promotion_default = str(self._promotion.itemData(index))
        save_config(self._runtime.config)

    def _on_stability_preview(self, value: int) -> None:
        self._stability_hint.setText(
            f"Espera {value} ms sin movimiento antes de aceptar una jugada."
        )

    def _on_stability(self) -> None:
        self._runtime.set_stability_ms(int(self._stability.value()))

    def _on_frames(self, enabled: bool) -> None:
        self._runtime.config.save_error_frames = enabled
        save_config(self._runtime.config)

    def _open_config_dir(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from chessoptic.core.config import config_dir

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config_dir())))
