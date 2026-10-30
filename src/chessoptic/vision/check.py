"""Setup check: does this camera + board + light combination work? Explains why not."""

from __future__ import annotations

import cv2
import numpy as np

from chessoptic.capture.source import Image
from chessoptic.core.events import CheckLevel, Finding, SetupCheckReport
from chessoptic.vision.features import extract_features
from chessoptic.vision.occupancy import OccupancyClassifier

SEPARABILITY_POOR = 1.0
SEPARABILITY_FAIR = 2.0
BLUR_THRESHOLD = 25.0
DARK_THRESHOLD = 60.0
BRIGHT_THRESHOLD = 205.0
UNEVEN_THRESHOLD = 55.0
LOW_CONFIDENCE = 0.25


def _quadrants(gray: np.ndarray) -> dict[str, np.ndarray]:
    h, w = gray.shape
    return {
        "arriba izq.": gray[: h // 2, : w // 2],
        "arriba der.": gray[: h // 2, w // 2 :],
        "abajo izq.": gray[h // 2 :, : w // 2],
        "abajo der.": gray[h // 2 :, w // 2 :],
    }


def run_setup_check(
    frames: list[Image], classifier: OccupancyClassifier, a1_corner: str
) -> SetupCheckReport:
    """`frames` are recent stable rectified frames of the initial position (≥ 1)."""
    findings: list[Finding] = []
    if not frames or not classifier.trained:
        return SetupCheckReport(
            CheckLevel.POOR,
            (
                Finding(
                    "untrained",
                    CheckLevel.POOR,
                    "Todavía no hay una posición inicial reconocida.",
                    "Armá las 32 piezas y esperá a que la cámara se estabilice.",
                ),
            ),
            0.0,
            (),
        )

    last = frames[-1]
    gray = cv2.cvtColor(last, cv2.COLOR_BGR2GRAY)

    # 1. Class separability per square colour.
    sep = classifier.separability()
    for parity, label in ((0, "claras"), (1, "oscuras")):
        value = sep.get(parity, 0.0)
        if value < SEPARABILITY_POOR:
            findings.append(
                Finding(
                    f"low_contrast_{label}",
                    CheckLevel.POOR,
                    f"En las casillas {label} las piezas y la casilla vacía se ven casi iguales.",
                    "Más luz de frente o piezas con más contraste contra el tablero. "
                    "Si el tablero es brillante, cambiá el ángulo para evitar reflejos.",
                )
            )
        elif value < SEPARABILITY_FAIR:
            findings.append(
                Finding(
                    f"fair_contrast_{label}",
                    CheckLevel.FAIR,
                    f"El contraste en las casillas {label} es justo.",
                    "Probá con un poco más de luz pareja. Funciona, pero puede fallar con sombras.",
                )
            )

    # 2. Flicker: the same still position must classify the same across frames.
    predictions = [classifier.predict(extract_features(f, a1_corner)) for f in frames]
    grids = [g for g, _ in predictions]
    flicker = tuple(sq for sq in range(64) if any(g[sq] != grids[0][sq] for g in grids[1:]))
    if flicker:
        level = CheckLevel.POOR if len(flicker) > 4 else CheckLevel.FAIR
        findings.append(
            Finding(
                "flicker",
                level,
                f"{len(flicker)} casilla(s) cambian de estado sin que nadie toque el tablero.",
                "Suele ser autoexposición o luz que parpadea: fijá exposición y enfoque en la "
                "pestaña Cámara y evitá lámparas que titilen.",
                flicker,
            )
        )

    # 3. Sharpness per quadrant.
    quads = _quadrants(gray)
    sharp = {k: float(cv2.Laplacian(v, cv2.CV_64F).var()) for k, v in quads.items()}
    best = max(sharp.values()) if sharp else 0.0
    blurry = [k for k, v in sharp.items() if v < BLUR_THRESHOLD and v < 0.5 * best]
    if blurry:
        findings.append(
            Finding(
                "blur_region",
                CheckLevel.FAIR,
                f"La zona {', '.join(blurry)} está fuera de foco.",
                "Fijá el enfoque de la cámara en el tablero (desactivá el autoenfoque).",
            )
        )
    elif best < BLUR_THRESHOLD:
        findings.append(
            Finding(
                "blur",
                CheckLevel.FAIR,
                "La imagen del tablero está poco nítida.",
                "Enfocá la cámara en el tablero y limpiá la lente.",
            )
        )

    # 4. Exposure.
    mean = float(gray.mean())
    if mean < DARK_THRESHOLD:
        findings.append(
            Finding(
                "too_dark",
                CheckLevel.POOR,
                "La imagen está muy oscura.",
                "Más luz sobre el tablero o subí la exposición en la pestaña Cámara.",
            )
        )
    elif mean > BRIGHT_THRESHOLD:
        findings.append(
            Finding(
                "too_bright",
                CheckLevel.POOR,
                "La imagen está quemada.",
                "Menos luz directa o bajá la exposición en la pestaña Cámara.",
            )
        )
    means = [float(v.mean()) for v in quads.values()]
    if means and max(means) - min(means) > UNEVEN_THRESHOLD:
        darkest = min(quads, key=lambda k: float(quads[k].mean()))
        findings.append(
            Finding(
                "uneven_light",
                CheckLevel.FAIR,
                f"La luz es despareja: la zona {darkest} está mucho más oscura.",
                "Mové la lámpara o la cámara para que no haya sombras de un lado.",
            )
        )

    # 5. Confidence of the last frame.
    _, confidence = predictions[-1]
    mean_confidence = float(np.mean(confidence))
    suspicious = tuple(sq for sq, c in enumerate(confidence) if c < LOW_CONFIDENCE)
    if len(suspicious) > 8:
        findings.append(
            Finding(
                "low_confidence",
                CheckLevel.FAIR,
                f"{len(suspicious)} casillas se reconocen con poca seguridad.",
                "Revisá luz y contraste; las casillas marcadas son las dudosas.",
                suspicious,
            )
        )

    level = CheckLevel.GOOD
    if any(f.level == CheckLevel.POOR for f in findings):
        level = CheckLevel.POOR
    elif any(f.level == CheckLevel.FAIR for f in findings):
        level = CheckLevel.FAIR
    return SetupCheckReport(level, tuple(findings), mean_confidence, suspicious)
