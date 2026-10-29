"""Dump frames and detections to disk when something does not match, so thresholds can be
tuned offline on the user's real camera, board and light (config ``save_error_frames``)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from chessoptic.core.config import data_dir

log = logging.getLogger(__name__)

MAX_DUMPS = 200


def debug_dir() -> Path:
    return data_dir() / "debug"


def dump(
    tag: str,
    raw: np.ndarray | None,
    rectified: np.ndarray | None,
    info: dict[str, Any],
) -> Path | None:
    """Write ``<tag>_<ts>.json`` plus the raw / rectified PNGs next to it. Never raises."""
    try:
        folder = debug_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if len(list(folder.glob("*.json"))) >= MAX_DUMPS:
            log.warning("debug folder full (%d dumps); not saving more", MAX_DUMPS)
            return None
        stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        base = folder / f"{tag}_{stamp}"
        if raw is not None:
            cv2.imwrite(str(base.with_name(base.name + "_raw.png")), raw)
        if rectified is not None:
            cv2.imwrite(str(base.with_name(base.name + "_rect.png")), rectified)
        base.with_suffix(".json").write_text(
            json.dumps({"tag": tag, **info}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return base
    except Exception:  # diagnostics must never break the driver
        log.exception("could not write debug dump")
        return None
