"""Application configuration and on-disk locations."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import platformdirs

log = logging.getLogger(__name__)

APP_NAME = "ChessOptic"
CONFIG_DIR_ENV = "CHESSOPTIC_CONFIG_DIR"
DATA_DIR_ENV = "CHESSOPTIC_DATA_DIR"


def config_dir() -> Path:
    """Where config.json, camera profiles and the optional theme.qss live."""
    override = os.environ.get(CONFIG_DIR_ENV)
    path = Path(override) if override else Path(platformdirs.user_config_dir(APP_NAME, False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Where logs, exported games and saved error frames live."""
    override = os.environ.get(DATA_DIR_ENV)
    path = Path(override) if override else Path(platformdirs.user_data_dir(APP_NAME, False))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class WindowConfig:
    always_on_top: bool = False
    compact: bool = False
    x: int | None = None
    y: int | None = None
    width: int = 380
    height: int | None = None


@dataclass
class AppConfig:
    language: str = "es"
    provider: str = "tracking"
    camera: str | None = None
    stability_ms: int = 750
    save_error_frames: bool = True
    sound_on_errors: bool = False
    stockfish_path: str | None = None
    stockfish_level: int = 4  # 1-8, see adapters/local/stockfish.py
    my_color: str = "white"  # colour against a local engine
    promotion_default: str = "ask"
    window: WindowConfig = field(default_factory=WindowConfig)


def _from_dict[T](cls: type[T], data: Any) -> T:
    """Build a dataclass from a dict, ignoring unknown keys and filling defaults."""
    if not isinstance(data, dict):
        return cls()
    kwargs: dict[str, Any] = {}
    for f in fields(cls):  # type: ignore[arg-type]
        if f.name not in data:
            continue
        value = data[f.name]
        if is_dataclass(f.type) and isinstance(f.type, type):
            kwargs[f.name] = _from_dict(f.type, value)
        else:
            kwargs[f.name] = value
    return cls(**kwargs)


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("config.json unreadable (%s); using defaults", exc)
        return AppConfig()
    return _from_dict(AppConfig, raw)


def save_config(config: AppConfig) -> None:
    path = config_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- camera profiles


@dataclass
class CameraProfile:
    """Everything the setup wizard learned about one camera + board combination."""

    camera_key: str
    calibration: dict[str, Any]
    classifier: dict[str, Any] | None = None
    check_level: str | None = None
    updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


def profiles_dir() -> Path:
    path = config_dir() / "cameras"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_path(camera_key: str) -> Path:
    return profiles_dir() / f"{camera_key}.json"


def load_profile(camera_key: str) -> CameraProfile | None:
    path = profile_path(camera_key)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _from_dict(CameraProfile, raw)
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
        log.warning("camera profile %s unreadable (%s)", path, exc)
        return None


def save_profile(profile: CameraProfile) -> None:
    profile.updated = datetime.now(UTC).isoformat(timespec="seconds")
    path = profile_path(profile.camera_key)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
