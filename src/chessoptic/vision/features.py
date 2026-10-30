"""Per-square feature vectors from the rectified image."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from chessoptic.capture.source import Image
from chessoptic.vision.squares import sample_region, square_cells

FEATURE_COUNT = 6
Features = NDArray[np.float64]  # shape (64, FEATURE_COUNT), rows in chess.SQUARES order


def extract_features(rectified: Image, a1_corner: str) -> Features:
    """For each square: mean L/a/b, std L, edge energy (log Laplacian var), mean saturation."""
    lab = cv2.cvtColor(rectified, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV).astype(np.float32)
    gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)

    out = np.zeros((64, FEATURE_COUNT), dtype=np.float64)
    for i, cell in enumerate(square_cells(a1_corner)):
        x, y, w, h = sample_region(cell)
        region = lab[y : y + h, x : x + w]
        mean = region.reshape(-1, 3).mean(axis=0)
        std_l = float(region[:, :, 0].std())
        edge = float(np.log1p(lap[y : y + h, x : x + w].var()))
        sat = float(hsv[y : y + h, x : x + w, 1].mean())
        out[i] = (mean[0], mean[1], mean[2], std_l, edge, sat)
    return out
