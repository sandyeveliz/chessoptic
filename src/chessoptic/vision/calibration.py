"""Board calibration: four corners in the raw image + where a1 is → rectified 8×8 view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import cv2
import numpy as np

from chessoptic.capture.source import Image

RECTIFIED_SIZE = 512
CELL = RECTIFIED_SIZE // 8

Corner = tuple[float, float]

# Where the a1 square sits in the rectified image, as the user sees it.
A1_CORNERS: tuple[str, ...] = ("bottom-left", "top-left", "top-right", "bottom-right")
A1_LABELS: dict[str, str] = {
    "bottom-left": "Abajo a la izquierda",
    "top-right": "Arriba a la derecha",
    "top-left": "Arriba a la izquierda",
    "bottom-right": "Abajo a la derecha",
}


@dataclass(frozen=True)
class Calibration:
    corners: tuple[Corner, Corner, Corner, Corner]  # tl, tr, br, bl in raw-image pixels
    a1_corner: str = "bottom-left"
    image_size: tuple[int, int] = (0, 0)

    def homography(self, out_size: int = RECTIFIED_SIZE) -> np.ndarray:
        src = np.array(self.corners, dtype=np.float32)
        s = float(out_size)
        dst = np.array([[0, 0], [s, 0], [s, s], [0, s]], dtype=np.float32)
        matrix: np.ndarray = cv2.getPerspectiveTransform(src, dst)
        return matrix

    def warp(self, image: Image, out_size: int = RECTIFIED_SIZE) -> Image:
        warped = cv2.warpPerspective(
            image, self.homography(out_size), (out_size, out_size), flags=cv2.INTER_LINEAR
        )
        return cast(Image, warped)

    def to_dict(self) -> dict[str, Any]:
        return {
            "corners": [list(c) for c in self.corners],
            "a1_corner": self.a1_corner,
            "image_size": list(self.image_size),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Calibration:
        corners = tuple((float(x), float(y)) for x, y in data["corners"])
        assert len(corners) == 4
        size = data.get("image_size", [0, 0])
        return Calibration(
            corners=(corners[0], corners[1], corners[2], corners[3]),
            a1_corner=str(data.get("a1_corner", "bottom-left")),
            image_size=(int(size[0]), int(size[1])),
        )


def default_corners(image_size: tuple[int, int]) -> tuple[Corner, Corner, Corner, Corner]:
    """A centered square covering ~70 % of the shorter side: a starting point to drag from."""
    w, h = image_size
    side = 0.7 * min(w, h)
    cx, cy = w / 2, h / 2
    half = side / 2
    return (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    )
