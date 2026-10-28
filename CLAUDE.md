# CLAUDE.md — ChessOptic

Contexto completo del proyecto y decisiones: **lee `docs/PLAN.md` antes de cualquier tarea.**
Especificación de la interfaz (pantallas, estados, tokens): `docs/UI.md`; mockups de referencia en `docs/design/`.

## Resumen en una línea
ChessOptic es el driver de un tablero electrónico de ajedrez cuyo sensor es una webcam: ve el tablero físico, mantiene la posición y la entrega a plataformas (Lichess, Chessconnect → chess.com, Stockfish local) mediante adaptadores. Python + OpenCV + python-chess + PySide6. Open source (Apache-2.0), multiplataforma.

## Convenciones
- Idioma: **español** en docs y textos de UI; **inglés** en código, identificadores, comentarios y commits (Conventional Commits).
- Python 3.12+, gestión con `uv`; layout `src/chessoptic/`.
- Calidad: `ruff` (lint + format), type hints en todo, `pytest`. CI en Windows, macOS y Linux.
- Toda lógica de visión y del BoardModel debe ser testeable **sin cámara**: inyectar `FrameSource`; usar fixtures en `tests/fixtures/` (Git LFS para videos).
- La UI (PySide6) no contiene lógica de negocio: consume eventos/estado del núcleo.
- Las salidas a plataformas viven solo en `src/chessoptic/adapters/` y cumplen la interfaz `OutputAdapter`.
- Nada específico de un SO fuera de módulos aislados con fallback claro; `chessoptic doctor` debe explicar lo que falte.
- No automatizar el DOM de sitios web ni crear extensiones de navegador (decisión cerrada, ver PLAN §2).

## Forma de trabajo
- Trabajar por etapas (PLAN §6). No empezar una etapa sin cumplir la aceptación de la anterior.
- Al cerrar tareas: tests verdes y actualizar checkboxes en `docs/PLAN.md` en el mismo PR.
- Si una decisión cambia, actualizar `docs/PLAN.md` (sección Decisiones) en el mismo PR.
