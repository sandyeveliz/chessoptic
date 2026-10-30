"""Occupancy classifier trained from the initial position, nearest-centroid per square colour."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import chess
import numpy as np

from chessoptic.board.occupancy import STARTPOS, Grid, Occupancy, square_is_dark
from chessoptic.vision.features import FEATURE_COUNT, Features

CLASSES = (int(Occupancy.EMPTY), int(Occupancy.WHITE), int(Occupancy.BLACK))
PARITIES = (0, 1)  # 0 = light square, 1 = dark square


def _parity(square: int) -> int:
    return 1 if square_is_dark(square) else 0


@dataclass
class OccupancyClassifier:
    # centroids[parity][class] -> feature vector
    centroids: dict[int, dict[int, np.ndarray]] = field(default_factory=dict)
    scale: np.ndarray = field(default_factory=lambda: np.ones(FEATURE_COUNT))
    trained: bool = False

    # ---- training ------------------------------------------------------

    def fit_initial(self, features: Features) -> None:
        """Fit from the start position: ranks 1-2 white, 7-8 black, 3-6 empty."""
        self.fit_labeled(features, STARTPOS)

    def fit_labeled(self, features: Features, grid: Grid) -> None:
        self.scale = features.std(axis=0) + 1e-6
        self.centroids = {}
        for parity in PARITIES:
            self.centroids[parity] = {}
            for cls in CLASSES:
                rows = [
                    features[sq]
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
                self.centroids[parity][cls] = (1 - alpha) * centroid + alpha * features[sq]

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
            dists = self._distances(features[sq], _parity(sq))
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
        clf.scale = np.array(data.get("scale", [1.0] * FEATURE_COUNT), dtype=np.float64)
        clf.trained = bool(data.get("trained", False))
        return clf
