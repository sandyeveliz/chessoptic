"""Occupancy classifier trained from the initial position.

Each square's "empty" appearance is modelled as a plane over (file, rank) per square colour,
fitted on the empty squares of the training position. Features are then taken *relative* to
that per-square baseline, which absorbs vignetting, perspective brightness gradients and the
fact that border squares never look like the centre ones. Classes are nearest-centroid on the
residuals, per square colour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import chess
import numpy as np

from chessoptic.board.occupancy import STARTPOS, Grid, Occupancy, square_is_dark
from chessoptic.vision.features import FEATURE_COUNT, Features

CLASSES = (int(Occupancy.EMPTY), int(Occupancy.WHITE), int(Occupancy.BLACK))
BASELINE_TERMS = 3  # 1, file, rank
PARITIES = (0, 1)  # 0 = light square, 1 = dark square


def _parity(square: int) -> int:
    return 1 if square_is_dark(square) else 0


def _design(square: int) -> np.ndarray:
    return np.array([1.0, chess.square_file(square), chess.square_rank(square)])


def _fit_baseline(features: Features, grid: Grid) -> dict[int, np.ndarray]:
    """Least-squares plane of the empty squares' features, per parity: (3, FEATURE_COUNT)."""
    out: dict[int, np.ndarray] = {}
    for parity in PARITIES:
        squares = [
            sq for sq in chess.SQUARES if _parity(sq) == parity and grid[sq] == Occupancy.EMPTY
        ]
        coeffs = np.zeros((BASELINE_TERMS, FEATURE_COUNT))
        if len(squares) >= 4:
            a = np.stack([_design(sq) for sq in squares])
            b = np.stack([features[sq] for sq in squares])
            coeffs = np.linalg.lstsq(a, b, rcond=None)[0]
        elif squares:
            coeffs[0] = np.mean([features[sq] for sq in squares], axis=0)
        out[parity] = coeffs
    return out


@dataclass
class OccupancyClassifier:
    # centroids[parity][class] -> feature vector
    centroids: dict[int, dict[int, np.ndarray]] = field(default_factory=dict)
    baseline: dict[int, np.ndarray] = field(default_factory=dict)
    scale: np.ndarray = field(default_factory=lambda: np.ones(FEATURE_COUNT))
    trained: bool = False

    def _residual(self, features: Features, square: int) -> np.ndarray:
        coeffs = self.baseline.get(_parity(square))
        row = np.asarray(features[square], dtype=np.float64)
        if coeffs is None:
            return row
        return np.asarray(row - _design(square) @ coeffs, dtype=np.float64)

    # ---- training ------------------------------------------------------

    def fit_initial(self, features: Features) -> None:
        """Fit from the start position: ranks 1-2 white, 7-8 black, 3-6 empty."""
        self.fit_labeled(features, STARTPOS)

    def fit_labeled(self, features: Features, grid: Grid) -> None:
        self.baseline = _fit_baseline(features, grid)
        residuals = np.stack([self._residual(features, sq) for sq in chess.SQUARES])
        self.scale = residuals.std(axis=0) + 1e-6
        self.centroids = {}
        for parity in PARITIES:
            self.centroids[parity] = {}
            for cls in CLASSES:
                rows = [
                    residuals[sq]
                    for sq in chess.SQUARES
                    if _parity(sq) == parity and grid[sq] == cls
                ]
                if rows:
                    self.centroids[parity][cls] = np.mean(rows, axis=0)
        self.trained = all(len(self.centroids[p]) == len(CLASSES) for p in PARITIES)

    def refine(self, features: Features, grid: Grid, alpha: float = 0.1) -> None:
        """Move centroids towards a confirmed position (online refinement)."""
        if not self.trained:
            return
        for sq in chess.SQUARES:
            parity, cls = _parity(sq), grid[sq]
            centroid = self.centroids[parity].get(cls)
            if centroid is not None:
                self.centroids[parity][cls] = (1 - alpha) * centroid + alpha * self._residual(
                    features, sq
                )

    # ---- inference -----------------------------------------------------

    def _distances(self, vector: np.ndarray, parity: int) -> dict[int, float]:
        return {
            cls: float(np.linalg.norm((vector - centroid) / self.scale))
            for cls, centroid in self.centroids[parity].items()
        }

    def predict(self, features: Features) -> tuple[Grid, tuple[float, ...]]:
        if not self.trained:
            raise RuntimeError("classifier not trained")
        grid: list[int] = []
        confidence: list[float] = []
        for sq in chess.SQUARES:
            dists = self._distances(self._residual(features, sq), _parity(sq))
            ordered = sorted(dists.items(), key=lambda kv: kv[1])
            best, second = ordered[0], ordered[1]
            grid.append(best[0])
            margin = (second[1] - best[1]) / (second[1] + best[1] + 1e-9)
            confidence.append(float(min(1.0, max(0.0, margin * 2.0))))
        return tuple(grid), tuple(confidence)

    # ---- diagnostics ---------------------------------------------------

    def separability(self) -> dict[int, float]:
        """Per parity: smallest distance between class centroids (in scaled units)."""
        out: dict[int, float] = {}
        for parity in PARITIES:
            cents = self.centroids.get(parity, {})
            best = float("inf")
            keys = list(cents)
            for i, a in enumerate(keys):
                for b in keys[i + 1 :]:
                    d = float(np.linalg.norm((cents[a] - cents[b]) / self.scale))
                    best = min(best, d)
            out[parity] = best if best != float("inf") else 0.0
        return out

    # ---- persistence ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "centroids": {
                str(p): {str(c): v.tolist() for c, v in cls.items()}
                for p, cls in self.centroids.items()
            },
            "baseline": {str(p): v.tolist() for p, v in self.baseline.items()},
            "scale": self.scale.tolist(),
            "trained": self.trained,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OccupancyClassifier:
        clf = OccupancyClassifier()
        clf.centroids = {
            int(p): {int(c): np.array(v, dtype=np.float64) for c, v in cls.items()}
            for p, cls in data.get("centroids", {}).items()
        }
        clf.baseline = {
            int(p): np.array(v, dtype=np.float64) for p, v in data.get("baseline", {}).items()
        }
        clf.scale = np.array(data.get("scale", [1.0] * FEATURE_COUNT), dtype=np.float64)
        clf.trained = bool(data.get("trained", False))
        return clf
