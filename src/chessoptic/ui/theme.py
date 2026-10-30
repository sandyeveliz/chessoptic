"""Design tokens (docs/UI.md §2) → Qt Style Sheet, plus fonts and the user override."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

from chessoptic.core.config import config_dir

log = logging.getLogger(__name__)

USER_THEME_FILE = "theme.qss"


@dataclass(frozen=True)
class Tokens:
    bg: str = "#F2F4F7"
    surface: str = "#FFFFFF"
    line: str = "#DCE1E8"
    line_strong: str = "#C3CBD6"
    ink: str = "#1D2330"
    muted: str = "#5B6474"
    turn: str = "#1172B3"
    brand_light: str = "#1E96D7"
    ok: str = "#17663A"
    ok_bg: str = "#E3F4EA"
    warn: str = "#8A5A0B"
    warn_bg: str = "#FDF1DC"
    err: str = "#A12A23"
    err_bg: str = "#FBE4E2"
    idle: str = "#4A5262"
    idle_bg: str = "#E8EBF0"
    square_light: str = "#EAEEF3"
    square_dark: str = "#C7D1DD"
    hl_origin: str = "#F3D3A1"
    hl_destination: str = "#8EC4EA"
    hl_error: str = "#F0AFA9"
    font_display: str = "Sora"
    font_sans: str = "IBM Plex Sans"
    font_mono: str = "IBM Plex Mono"


TOKENS = Tokens()


def load_fonts() -> Tokens:
    """Register the bundled fonts; fall back to system families if any is missing."""
    families: dict[str, str] = {}
    fonts_dir = resources.files("chessoptic.assets") / "fonts"
    for entry in fonts_dir.iterdir():
        if not entry.name.lower().endswith((".ttf", ".otf")):
            continue
        with resources.as_file(entry) as path:
            font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            log.warning("could not load font %s", entry.name)
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            families[family] = family

    def pick(wanted: str, generic: QFont.StyleHint) -> str:
        if wanted in families:
            return wanted
        fallback = QFont()
        fallback.setStyleHint(generic)
        log.warning("font %s not available; using %s", wanted, fallback.defaultFamily())
        return fallback.defaultFamily()

    return Tokens(
        font_display=pick(TOKENS.font_display, QFont.StyleHint.SansSerif),
        font_sans=pick(TOKENS.font_sans, QFont.StyleHint.SansSerif),
        font_mono=pick(TOKENS.font_mono, QFont.StyleHint.Monospace),
    )


QSS_TEMPLATE = """
/* ---- base ---- */
QMainWindow, QWidget#root, QStackedWidget, QWidget#page {{
  background: {bg};
}}
QWidget {{
  color: {ink};
  font-family: "{font_sans}";
  font-size: 13px;
}}
QLabel#muted {{ color: {muted}; }}
QLabel#error {{ color: {err}; font-size: 12px; }}
QLabel#sectionLabel {{
  color: {muted}; font-size: 11px; font-weight: 600; letter-spacing: 1px;
}}
QLabel#mono {{ font-family: "{font_mono}"; }}

/* ---- header ---- */
QWidget#header {{
  background: {surface};
  border-bottom: 1px solid {line};
}}
QLabel#brand {{
  font-family: "{font_display}"; font-size: 15px; font-weight: 600;
}}
QLabel#brandAccent {{
  font-family: "{font_display}"; font-size: 15px; font-weight: 600; color: {turn};
}}

/* ---- health pill ---- */
HealthPill {{
  border-radius: 11px; padding: 4px 10px; font-size: 12px; font-weight: 600;
  background: {idle_bg}; color: {idle};
}}
HealthPill[level="ok"]   {{ background: {ok_bg};   color: {ok}; }}
HealthPill[level="warn"] {{ background: {warn_bg}; color: {warn}; }}
HealthPill[level="err"]  {{ background: {err_bg};  color: {err}; }}
HealthPill[level="idle"] {{ background: {idle_bg}; color: {idle}; }}

/* ---- cards ---- */
QFrame#card {{
  background: {surface};
  border: 1px solid {line};
  border-radius: 8px;
}}

/* ---- buttons ---- */
QPushButton {{
  min-height: 40px; padding: 0 14px; border-radius: 8px;
  border: 1px solid {line_strong}; background: {surface}; color: {ink}; font-weight: 600;
}}
QPushButton:hover {{ background: {bg}; }}
QPushButton:disabled {{ color: {muted}; border-color: {line}; }}
QPushButton[primary="true"] {{ background: {turn}; border-color: {turn}; color: #FFFFFF; }}
QPushButton[primary="true"]:disabled {{ background: {line}; border-color: {line}; color: {muted}; }}
QPushButton[primary="true"]:hover {{ background: {brand_light}; border-color: {brand_light}; }}

/* ---- inputs ---- */
QComboBox, QLineEdit {{
  min-height: 38px; padding: 0 10px; border: 1px solid {line_strong}; border-radius: 8px;
  background: {surface};
}}
QComboBox::drop-down {{ border: none; width: 28px; }}

/* ---- bottom nav ---- */
QWidget#navBar {{
  background: {surface};
  border-top: 1px solid {line};
}}
QToolButton#navButton {{
  border: none; background: transparent; color: {muted};
  font-size: 11px; padding: 8px 0 10px 0;
}}
QToolButton#navButton:checked {{ color: {turn}; font-weight: 600; }}
QToolButton#navButton:hover {{ color: {ink}; }}

QScrollBar:vertical {{ width: 8px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {line_strong}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def build_qss(tokens: Tokens) -> str:
    return QSS_TEMPLATE.format(**asdict(tokens))


def user_theme_path() -> Path:
    return config_dir() / USER_THEME_FILE


def load_user_qss() -> str:
    """Optional user override, appended after the default sheet so it wins."""
    path = user_theme_path()
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("could not read %s: %s", path, exc)
        return ""


def full_stylesheet(tokens: Tokens) -> str:
    return build_qss(tokens) + "\n" + load_user_qss()
