# ChessOptic — Plan de implementación v1 (Etapas 0 a 3)

> Complementa a [`PLAN.md`](PLAN.md) (qué y por qué) y a [`UI.md`](UI.md) (cómo se ve).
> Este documento dice **en qué orden se construye, en qué archivos, cómo se prueba cada parte sin cámara,
> cuál es el criterio de aceptación y qué tiene que preparar el autor en casa antes de cada etapa**.
> Si algo acá contradice al código, actualizá este documento en el mismo PR.

Alcance: **v1 = Etapas 0, 1, 2 y 3 del PLAN** (base del repo, visión + BoardModel, modo local con Stockfish, Lichess).
Chessconnect (Etapa 4), protocolo nativo y detector de piezas (Etapa 5) e instaladores (Etapa 6) quedan afuera,
salvo las preparaciones que conviene arrancar en paralelo (ver §7.6).

---

## 0. Cómo leer este documento

| Sección | Para qué |
|---|---|
| §1 | Decisiones transversales: layout final, hilos, contrato de eventos, configuración, estrategia de tests sin cámara. Todas las etapas las asumen. |
| §2–§5 | Etapas 0 a 3: tareas en orden, archivos, cómo se testea cada parte, aceptación, PRs sugeridos. |
| §6 | Mapeo de cada pantalla y estado de `UI.md` a widgets PySide6 y a los eventos del núcleo. |
| §7 | "Para hacer en casa": instalar, armar, grabar, cuentas. En orden, por etapa. |
| §8 | Riesgos y decisiones pendientes que necesitan respuesta del autor. |

---

## 1. Decisiones transversales de implementación

### 1.1 Layout final del paquete al cierre de la v1

Extiende el árbol de PLAN §3.1 con dos paquetes nuevos (`core/` y `game/`). **El PR de la Etapa 0 debe actualizar PLAN §3.1** para reflejarlo.

```
chessoptic/
├── pyproject.toml                 # uv + hatchling; extras: [dev]
├── .github/workflows/ci.yml       # matriz windows / macos / ubuntu
├── .gitattributes                 # tests/fixtures/** → Git LFS
├── assets/
│   ├── logo.png
│   ├── icons/                     # SVG monocromos (cámara, tablero, enlace, alerta, ok…)
│   └── fonts/                     # Sora, IBM Plex Sans, IBM Plex Mono (OFL, empaquetadas)
├── src/chessoptic/
│   ├── __init__.py                # __version__
│   ├── __main__.py                # python -m chessoptic
│   ├── cli.py                     # argparse: (sin args) → UI · doctor · replay · calibrate
│   ├── doctor.py
│   ├── core/
│   │   ├── events.py              # dataclasses congeladas: OccupancyFrame, BoardEvent*, AdapterEvent*, snapshots
│   │   ├── bus.py                 # EventBus mínimo (subscribe/publish, sin Qt)
│   │   ├── config.py              # AppConfig (dataclass) + load/save JSON + rutas platformdirs
│   │   ├── health.py              # HealthAggregator: cámara/tablero/enlace → HealthState + nivel del semáforo
│   │   └── runtime.py             # CoreRuntime: arma hilos, loop asyncio, conecta pipeline → session → adapters
│   ├── capture/
│   │   ├── source.py              # Frame, FrameSource (Protocol), ListSource, ImageSequenceSource
│   │   ├── webcam.py              # WebcamSource (cv2.VideoCapture, backend por SO), enumeración de cámaras
│   │   └── video.py               # VideoFileSource (con o sin ritmo real)
│   ├── vision/
│   │   ├── calibration.py         # Calibration (4 esquinas + a1), warp(), load/save por cámara
│   │   ├── squares.py             # recorte de las 64 celdas, región central, mapeo índice ↔ chess.Square
│   │   ├── features.py            # vector de features por celda (color relativo, textura, brillo)
│   │   ├── occupancy.py           # OccupancyClassifier: fit(initial) / predict / refine, confianza
│   │   ├── stability.py           # StabilityDetector: movimiento/mano, ventana de estabilidad
│   │   └── pipeline.py            # VisionPipeline: source → warp → stability → classifier → OccupancyFrame
│   ├── board/
│   │   ├── model.py               # BoardModel: chess.Board + inferencia por jugadas legales
│   │   ├── occupancy.py           # Occupancy (enum), OccupancyGrid (8×8), diff, from_board()
│   │   └── tracker.py             # BoardTracker: consume OccupancyFrame estable → BoardEvent
│   ├── game/
│   │   ├── session.py             # GameSession: máquina de estados standby/partida (docs/STATES.md)
│   │   ├── clock.py               # TurnClock: tiempos medidos por el driver cuando el cliente no los da
│   │   └── pgn.py                 # exportar PGN con cabeceras (plataforma, color, resultado)
│   ├── adapters/
│   │   ├── base.py                # OutputAdapter (Protocol), AdapterStatus, AdapterRunner (hilo asyncio)
│   │   ├── none.py                # NullAdapter: "solo seguimiento" (sin salida), para Etapa 1 y pruebas
│   │   ├── local_engine.py        # LocalEngineAdapter (Stockfish vía chess.engine)
│   │   └── lichess.py             # LichessAdapter (Board API, httpx + ndjson)
│   └── ui/
│       ├── app.py                 # QApplication, fuentes, QSS, arranque
│       ├── bridge.py              # CoreBridge(QObject): eventos del núcleo → Signals Qt (hilo GUI)
│       ├── controller.py          # acciones de la UI → CoreRuntime (pausar, recalibrar, resincronizar…)
│       ├── theme.py               # tokens de UI.md §2 → QSS
│       ├── main_window.py         # ventana 380 px, QStackedWidget, nav inferior, siempre arriba, compacto
│       ├── views/                 # live.py, camera.py, log.py, settings.py, wizard/, compact.py
│       └── widgets/               # health_pill.py, health_strip.py, camera_view.py, state_block.py,
│                                  # moves_list.py, nav_bar.py, stepper.py, corner_editor.py
├── tests/
│   ├── conftest.py                # fixtures comunes, markers, helpers
│   ├── helpers/
│   │   ├── synthetic_board.py     # render FEN → imagen (ver §1.5)
│   │   └── scripted.py            # secuencias (fen, n_frames, mano) → ListSource
│   ├── fixtures/                  # videos y fotos reales (Git LFS) + manifest.json por clip
│   ├── unit/                      # sin IO: board, game, vision sobre sintético, adapters con fakes
│   ├── qt/                        # pytest-qt, QT_QPA_PLATFORM=offscreen
│   └── fixtures_real/             # tests parametrizados sobre tests/fixtures/*/manifest.json
└── docs/
    ├── PLAN.md · UI.md · IMPLEMENTATION.md
    ├── STATES.md                  # se escribe en Etapa 2 (máquina de estados detallada)
    ├── CALIBRATION.md             # se escribe en Etapa 1 (guía de cámara/luz/encuadre para usuarios)
    └── FIXTURES.md                # se escribe en Etapa 1 (cómo grabar y registrar fixtures)
```

### 1.2 Hilos y flujo de eventos

Reglas:

1. **El núcleo no importa Qt.** `core/`, `capture/`, `vision/`, `board/`, `game/`, `adapters/` se testean con pytest puro.
2. **Un solo hilo muta el estado de la partida.** `GameSession` vive en el hilo del loop asyncio (`AdapterRunner`), junto con los adaptadores. La visión le entrega `OccupancyFrame` con `loop.call_soon_threadsafe`. Así no hay locks en la lógica.
3. **La UI recibe snapshots inmutables** (dataclasses `frozen=True`) por Signals Qt. `CoreBridge` se suscribe al bus desde cualquier hilo y emite señales; Qt las encola al hilo GUI (conexión automática entre hilos).
4. **La visión corre en su propio `threading.Thread`** a ~10–15 fps de análisis; la UI recibe el frame rectificado ya convertido a `QImage` como máximo a 15 fps.

```
 hilo visión                      hilo núcleo (asyncio)                        hilo GUI (Qt)
 ───────────                      ─────────────────────                        ─────────────
 FrameSource.read()
   → Calibration.warp()
   → StabilityDetector            GameSession ◄── AdapterEvent ── LichessAdapter / LocalEngineAdapter
   → OccupancyClassifier             │  ▲                               ▲
   → OccupancyFrame ─ call_soon ────►│  │ BoardTracker.on_occupancy     │ on_board_event(MoveDetected)
                                     │  └── BoardModel                  │
                                     ▼                                  │
                                 EventBus.publish(snapshots) ───────────┴──► CoreBridge (Signals) ──► vistas
                                     ▲
 Controller (acciones UI) ── call_soon_threadsafe ──┘
```

Alternativa descartada: `qasync` (asyncio dentro del loop de Qt). Funciona, pero ata el núcleo a Qt y complica los tests. Si en Etapa 2 el cruce de hilos resulta molesto, se revisa (ver §8.2, pregunta 13).

### 1.3 Contrato de eventos (`core/events.py`)

Todo lo que cruza entre módulos es una dataclass congelada con `ts: float` (`time.monotonic()`).

**De la visión al núcleo**

- `OccupancyFrame(grid: OccupancyGrid, confidence: tuple[float, ...64], stable: bool, motion: float, frame_index: int)`.
- `CameraStatus(state: ok | no_permission | disconnected | low_fps, fps: float, device: str)`.
- `BoardStatus(state: ok | occluded | low_confidence | moved, detail: str)`.

**Del BoardTracker al núcleo (`BoardEvent`)**

- `InitialPositionCheck(white: int, black: int, missing: tuple[Square], extra: tuple[Square], complete: bool)`.
- `MoveDetected(move: chess.Move, san: str, fen_before: str, fen_after: str)`.
- `MoveAmbiguous(candidates: tuple[chess.Move, ...])` — solo promoción.
- `PositionMismatch(squares: tuple[SquareIssue, ...])` con `SquareIssue(square, expected: Occupancy, seen: Occupancy)`.
- `PositionMatched(fen: str)` — la ocupación volvió a coincidir (verificación de jugada rival o resincronización).
- `HandDetected()` / `BoardStable()`.

**De los adaptadores al núcleo (`AdapterEvent`)**

- `LinkStatus(state: inactive | announcing | connected | lost, client: str, detail: str)`.
- `GameStarted(game_id, my_color: chess.Color, platform: str, time_control: str | None, initial_fen: str)`.
- `OpponentMove(move: chess.Move, san: str)`.
- `MoveAccepted(move)` / `MoveRejected(move, reason)`.
- `ClockUpdate(white_ms: int | None, black_ms: int | None)`.
- `GameOver(result: str, reason: str)`.
- `AdapterError(message, recoverable: bool)`.

**Snapshots hacia la UI** (exactamente los de UI.md §5)

- `HealthState(camera, board, link, level: ok | warn | err | idle, pill_text: str)`.
- `DriverState(phase: Standby | InGame, state: <enum de §6.4>)`.
- `GameInfo(my_color, platform, white_ms, black_ms, clock_source: client | driver | None, moves: tuple[MoveRecord], result)`.
- `OccupancyView(grid, confidence, highlights: tuple[Highlight(square, kind: origin | destination | error | missing)], a1_corner)`.
- `PendingOpponentMove(san, piece, from_square, to_square, special: castle | en_passant | promotion | None, human_text)`.
- `LogEntry(ts_wall, kind: move | event | error, text, frame_path: str | None)`.

### 1.4 Configuración y persistencia (`core/config.py`)

Con `platformdirs`:

| Qué | Dónde |
|---|---|
| `config.json` (AppConfig: salida elegida, promoción por defecto, estabilidad ms, siempre arriba, compacto, sonido, idioma, ruta a Stockfish, nivel) | `user_config_dir("ChessOptic")` |
| `calibrations/<camera_key>.json` (esquinas, a1, resolución, fecha) | `user_config_dir("ChessOptic")` |
| `errors/<ts>.png` (frames guardados en errores), `games/<ts>.pgn`, `logs/chessoptic.log` | `user_data_dir("ChessOptic")` |
| Token de Lichess | `keyring` (llavero del SO) con fallback a `secrets.json` 0600 — **a confirmar**, §8.2 pregunta 4 |

`camera_key` = nombre del dispositivo + resolución (los índices de OpenCV cambian al enchufar cosas).

### 1.5 Estrategia de tests sin cámara: tres capas

1. **Sintético** (`tests/helpers/synthetic_board.py`): `render(fen, *, square_px=64, light=(234,238,243), dark=(199,209,221), white_piece=(245,245,240), black_piece=(30,35,48), piece_radius=0.32, noise=0.0, brightness=1.0, perspective: Homography | None, hand: Blob | None, seed=0) -> np.ndarray`. Las piezas son discos; la ocupación es lo único que v1 necesita. Permite: entrenar el clasificador con la posición inicial, probar generalización a otros FEN, variar luz/ruido, simular una mano, generar la imagen cruda con perspectiva para probar calibración y warp.
2. **Secuencias guionadas** (`tests/helpers/scripted.py`): lista de pasos `(fen, n_frames, hand=False)` → `ListSource`. Con esto se recorre todo el pipeline (`VisionPipeline → BoardTracker → GameSession`) sobre una partida completa en milisegundos, incluyendo estados transitorios (pieza levantada, captura a medio hacer, enroque en dos tiempos).
3. **Fixtures reales** (`tests/fixtures/<clip>/`, Git LFS): video + `manifest.json` con esquinas, a1, FEN inicial, jugadas esperadas (UCI) y notas. `tests/fixtures_real/` se parametriza sobre todos los manifests y se **saltea** si el archivo es un puntero LFS no descargado (`pytest.skip`).

Markers de pytest: `unit` (default, siempre en CI), `qt` (pytest-qt, `QT_QPA_PLATFORM=offscreen`), `fixtures` (requiere LFS), `stockfish` (requiere binario), `lichess_live` (requiere `LICHESS_TOKEN`, nunca en CI).

Formato de `manifest.json`:

```json
{
  "video": "game_short_01.mp4",
  "camera": "Logitech C920", "resolution": [1280, 720], "fps": 30,
  "corners": {"tl": [212, 88], "tr": [1070, 92], "br": [1098, 648], "bl": [184, 652]},
  "a1": "bottom-left",
  "start_fen": "startpos",
  "expected_moves": ["e2e4", "e7e5", "g1f3"],
  "tolerated_false_positives": 0,
  "notes": "luz de día, lámpara apagada, manos normales"
}
```

Las esquinas se completan después de grabar con `chessoptic calibrate --video <clip> --out corners.json` (Etapa 1).

---

## 2. Etapa 0 — Base del repo

Objetivo: paquete instalable, CI en tres SO, `doctor`, ventana vacía con la forma final.

### 2.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea |
|---|---|---|---|
| 0.1 | `pyproject.toml`: `uv` + `hatchling`, `requires-python >= 3.12`, deps runtime: `numpy`, `opencv-python-headless`, `chess`, `PySide6`, `platformdirs`, `httpx`, `keyring`; extras `dev`: `ruff`, `mypy`, `pytest`, `pytest-qt`, `pytest-asyncio`, `pytest-cov`. Scripts: `chessoptic = "chessoptic.cli:main"`. Config de ruff (line-length 100, `select = ["E","F","I","UP","B","SIM","RUF"]`), mypy `strict` en `src/`, pytest `qt_api = pyside6`, markers. | `pyproject.toml`, `src/chessoptic/__init__.py`, `__main__.py`, `cli.py` | `uv sync`, `uv run chessoptic --version`, `uv run python -m chessoptic --version` |
| 0.2 | **Usar `opencv-python-headless`, no `opencv-python`**: el wheel normal trae su propio Qt5 y rompe PySide6 en Linux. Documentarlo en el pyproject. | `pyproject.toml` | test que importa `cv2` y `PySide6` en el mismo proceso |
| 0.3 | `core/config.py`: `AppConfig` dataclass con defaults de UI.md (estabilidad 750 ms, promoción "preguntar", idioma es), `load()`/`save()` JSON, rutas por `platformdirs`, directorio sobreescribible con `CHESSOPTIC_CONFIG_DIR` (para tests y CI). | `core/config.py` | round-trip en `tmp_path`; defaults; archivo corrupto → defaults + warning |
| 0.4 | `core/events.py` y `core/bus.py`: las dataclasses de §1.3 y un `EventBus` con `subscribe(type, cb)` / `publish(event)`, thread-safe. | `core/events.py`, `core/bus.py` | publish/subscribe, suscripción por tipo y por clase base, desuscripción |
| 0.5 | `chessoptic doctor`: Python ≥ 3.12; imports de `cv2`, `chess`, `PySide6`; cámaras (enumerar índices 0–5 con backend por SO: `CAP_DSHOW` en Windows, `CAP_AVFOUNDATION` en macOS, `CAP_V4L2` en Linux; timeout por índice); Stockfish (`shutil.which("stockfish")` o ruta en config, y versión por UCI `uci`/`uciok`); permisos por SO (macOS: aviso de que la primera apertura pide permiso de cámara y a quién se lo da; Linux: `/dev/video*` y grupo `video`); Bluetooth: en v1 solo informa "no evaluado (Etapa 4)". Salida en texto con ✓ / ✗ / – y sugerencia por ítem; `--json` para CI. | `doctor.py` | cada check es una función `-> CheckResult`; se testean con monkeypatch (sin cámara: `cv2.VideoCapture` falso; sin Stockfish: `which` → `None`) |
| 0.6 | Fuentes y tema: copiar Sora + IBM Plex Sans + IBM Plex Mono a `assets/fonts/` (OFL, con sus licencias), `ui/theme.py` con los tokens de UI.md §2 y una plantilla QSS; `QFontDatabase.addApplicationFont` al arrancar con fallback a la sans/mono del sistema. | `assets/fonts/`, `ui/theme.py`, `ui/app.py` | test `qt`: la QSS compila (no hay warnings de parseo), las fuentes se cargan o se cae al fallback sin excepción |
| 0.7 | Ventana vacía con la forma final: `MainWindow(QMainWindow)` 380 px de ancho, alto de pantalla, `QStackedWidget` con 4 placeholders, `NavBar` inferior (4 `QToolButton` checkables), header con marca + `HealthPill` en estado idle "Iniciando", toggle "siempre arriba" (`Qt.WindowStaysOnTopHint`, re-`show()` al cambiar), posición recordada en config. | `ui/main_window.py`, `ui/widgets/nav_bar.py`, `ui/widgets/health_pill.py` | pytest-qt offscreen: se instancia, el nav cambia la página, la pill cambia texto/color por nivel, el flag always-on-top se refleja en `windowFlags()` |
| 0.8 | CI: `.github/workflows/ci.yml` con matriz `windows-latest`, `macos-latest`, `ubuntu-latest`; `astral-sh/setup-uv`; `uv sync --all-extras`; `ruff check` + `ruff format --check`; `mypy`; `pytest -m "not fixtures and not stockfish and not lichess_live"` con `QT_QPA_PLATFORM=offscreen`; en Ubuntu instalar libs de Qt (§7.1). Job extra `smoke`: `uv tool install .` y `chessoptic doctor --json` y `chessoptic --smoke` (abre la ventana offscreen 1 s y sale con 0). | `.github/workflows/ci.yml`, flag `--smoke` en `cli.py` | el propio CI |
| 0.9 | README: instalación con `uv tool install` / `pipx`, `chessoptic doctor`, estado del proyecto, link a los docs. Actualizar PLAN §3.1 con `core/` y `game/`. | `README.md`, `docs/PLAN.md` | — |

### 2.2 Aceptación (PLAN §6, Etapa 0)

- CI verde en los tres SO con lint, tipos y tests.
- `uv tool install .` (o `pipx install .`) y `chessoptic` abren la ventana con la forma del panel en los tres SO. En CI se verifica con `--smoke` offscreen; a mano, el autor lo prueba en Windows (su máquina) y en lo que tenga de macOS/Linux (ver §8.2, pregunta 9).
- `chessoptic doctor` lista cámara(s), Stockfish y permisos, y explica qué falta.

### 2.3 PRs sugeridos

1. `build: project skeleton with uv, ruff, mypy, pytest and CI matrix` (0.1, 0.2, 0.8 sin smoke).
2. `feat(core): config, events and bus` (0.3, 0.4).
3. `feat(doctor): environment checks per OS` (0.5).
4. `feat(ui): empty side-panel window with theme, fonts and nav` (0.6, 0.7, smoke en CI).
5. `docs: install instructions and plan layout update` (0.9).

---

## 3. Etapa 1 — Visión + BoardModel

Objetivo: de un video (o la webcam) a una lista de jugadas, con la UI "En vivo" mostrando cámara, overlay, salud y log. Sin adaptadores todavía: se usa `NullAdapter` ("solo seguimiento") para poder jugar ambos bandos y probar.

### 3.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea sin cámara |
|---|---|---|---|
| 1.1 | `capture/source.py`: `Frame(image: np.ndarray BGR, ts, index)`, `FrameSource` Protocol (`read() -> Frame | None`, `fps`, `size`, `close()`), `ListSource`, `ImageSequenceSource` (carpeta de JPG/PNG ordenada). | `capture/source.py` | unit: `ListSource` entrega en orden y termina con `None`; `ImageSequenceSource` sobre `tmp_path` |
| 1.2 | `capture/video.py`: `VideoFileSource(path, realtime: bool)`; con `realtime=False` entrega lo más rápido posible (tests y `replay`), con `True` respeta el fps original (demo). `capture/webcam.py`: `WebcamSource(device, width, height, backend por SO)`, `list_cameras()`, reconexión si `read()` falla N veces → `CameraStatus(disconnected)`. | `capture/video.py`, `capture/webcam.py` | video: generar un MP4 corto con `cv2.VideoWriter` desde frames sintéticos en `tmp_path` y leerlo; webcam: `cv2.VideoCapture` monkeypatcheado |
| 1.3 | `board/occupancy.py`: `Occupancy` (`EMPTY`, `WHITE`, `BLACK`), `OccupancyGrid` (tupla de 64 en orden `chess.SQUARES`), `from_board(chess.Board)`, `diff(a, b) -> frozenset[Square]`, `counts()`. | `board/occupancy.py` | unit puro |
| 1.4 | `tests/helpers/synthetic_board.py` (§1.5) y `tests/helpers/scripted.py`. Determinista por `seed`. Incluye `with_perspective()` que aplica una homografía conocida y devuelve también las esquinas verdaderas. | `tests/helpers/` | se testea a sí mismo: `render(startpos)` tiene 32 discos; `with_perspective` → `warp` recupera la imagen (PSNR alto) |
| 1.5 | `vision/calibration.py`: `Calibration(corners: 4×(x,y) en orden tl,tr,br,bl de la imagen, a1_corner: "bottom-left" | "top-right" | "top-left" | "bottom-right", image_size)`, `homography()` (`cv2.getPerspectiveTransform`), `warp(frame) -> 512×512`, `square_rect(sq)`, `load/save(camera_key)`. La orientación convierte índice de celda ↔ `chess.Square`. | `vision/calibration.py`, `vision/squares.py` | unit: warp de la imagen sintética con perspectiva ≈ imagen plana; `square_rect(chess.A1)` cae en la esquina correcta para las 4 orientaciones; round-trip JSON |
| 1.6 | `vision/features.py`: por celda, sobre la **región central** (50 % interior) de la celda rectificada: media y desvío en Lab (L, a, b), energía de bordes (Laplaciano) y **diferencia contra la referencia de casilla vacía del mismo color de casilla** (clara/oscura). Vector de ~8 floats normalizados. | `vision/features.py` | unit sintético: vacía vs blanca vs negra separables; invariante a `brightness` dentro de ±30 % |
| 1.7 | `vision/occupancy.py`: `OccupancyClassifier` sin sklearn (numpy): centroides por clase y por color de casilla, con normalización por feature; `fit_initial(rectified)` usa las 64 etiquetas de la posición inicial (las 32 vacías de las filas 3–6 dan la referencia de "vacía" clara/oscura; filas 1, 2, 7, 8 dan "blanca" y "negra"); `predict(rectified) -> (grid, confidence)` con confianza = margen entre la mejor y la segunda clase mapeado a 0–1; `refine(rectified, grid_confirmada)` con media móvil (peso configurable) tras cada posición confirmada. Serializable a JSON junto con la calibración. | `vision/occupancy.py` | unit sintético: fit en `startpos`, predict en 50 FEN aleatorios (python-chess jugando random) ≥ 99 % de celdas correctas; con `noise=0.05` y `brightness=0.8/1.2` ≥ 98 %; `refine` mejora la confianza media |
| 1.8 | `vision/stability.py`: `StabilityDetector(window_ms, motion_threshold)`: `absdiff` entre rectificados consecutivos (gris, blur), `motion` = fracción de píxeles sobre umbral; `hand` si `motion > threshold`; `stable` cuando hubo `window_ms` seguidos sin movimiento. Expone `motion` para la UI. | `vision/stability.py` | unit: secuencia guionada con `hand=True` en el medio → `HandDetected` y luego `BoardStable` después de `window_ms`; sin movimiento nunca se dispara |
| 1.9 | `vision/pipeline.py`: `VisionPipeline(source, calibration, classifier, stability, analysis_fps=12)`: salta frames para respetar `analysis_fps`, publica `OccupancyFrame` (solo marca `stable=True` cuando corresponde), `CameraStatus` (fps medidos, desconexión), `BoardStatus` (`low_confidence` si la confianza media < umbral; `occluded` si `motion` alto > 3 s; `moved` si el borde del tablero rectificado cambió respecto de la calibración). Métodos: `run()` en hilo, `run_sync()` para tests y `replay`. También emite el rectificado para la UI a ≤ 15 fps. | `vision/pipeline.py` | unit: `run_sync` sobre `ListSource` guionado produce la secuencia esperada de `OccupancyFrame` estables; fps medido ≈ `analysis_fps` |
| 1.10 | `board/model.py`: `BoardModel(board: chess.Board)` con `expected_occupancy()`, `verify_initial(grid) -> InitialPositionCheck`, `resolve(grid) -> Resolution` donde `Resolution = NoChange | Move(move) | Ambiguous(moves) | Transient | Mismatch(issues)`. Algoritmo: (a) igual a la actual → `NoChange`; (b) coincide exactamente con `board.after(m)` para una sola jugada legal del bando al que le toca → `Move`; varias → `Ambiguous` (solo promoción, mismo origen/destino); (c) el conjunto de celdas que cambiaron es **subconjunto** del cambio de alguna jugada legal (pieza levantada, captura a medio hacer, rey movido antes que la torre) → `Transient`; (d) si no → `Mismatch` con las celdas que difieren de la posición actual. Modo `both_sides=True` (para `NullAdapter`): candidatos de ambos bandos. `push(move)`, `set_board(fen)` (resincronizar). | `board/model.py` | unit exhaustivo sin imágenes: cada tipo de jugada (simple, captura, O-O, O-O-O, al paso, promoción con las 4 piezas → `Ambiguous`), transitorios de cada una, mismatches, both_sides, `verify_initial` con faltantes/sobrantes |
| 1.11 | `board/tracker.py`: `BoardTracker(model, mismatch_grace_ms=2000)`: recibe solo `OccupancyFrame` con `stable=True`; `Transient` → espera; `Move` → `MoveDetected` y `push`; `Ambiguous` → `MoveAmbiguous` (la sesión decide); `Mismatch` sostenido más de `grace` → `PositionMismatch` (y guarda el frame si está activado); cuando vuelve a coincidir → `PositionMatched`. Modo `verify_target(board_after)` para el estado "Reproducí la jugada": compara contra la posición esperada y reporta progreso. | `board/tracker.py` | unit: secuencias de grids (sin imagen) → eventos esperados; grace evita falsos `Mismatch` durante un enroque lento |
| 1.12 | `core/health.py`: `HealthAggregator` combina `CameraStatus`, `BoardStatus`, `LinkStatus` y la fase (`in_game`) en `HealthState` con el nivel del semáforo y el texto de la pill (reglas en §6.4). | `core/health.py` | unit: tabla de combinaciones → nivel/texto |
| 1.13 | `core/runtime.py` + `adapters/none.py` + `game/session.py` **mínimo**: `CoreRuntime` arma hilos y conecta; `GameSession` en Etapa 1 solo cubre standby (`Starting → Uncalibrated → VerifyingBoard → Ready`) y un modo "solo seguimiento" con `NullAdapter` que acepta cualquier jugada legal de ambos bandos y la loguea. La máquina completa se hace en Etapa 2. | `core/runtime.py`, `adapters/none.py`, `game/session.py` | unit: eventos guionados → `DriverState`/`LogEntry` esperados; `run_sync` de punta a punta sobre una partida sintética produce la lista de SAN esperada |
| 1.14 | CLI: `chessoptic replay <manifest.json | video> [--corners corners.json] [--a1 ...] [--show]` imprime jugadas detectadas, falsos positivos contra `expected_moves` y confianza media; `chessoptic calibrate --video <clip> --frame N --out corners.json` abre el editor de esquinas Qt sobre un frame y guarda el JSON. `replay` es el **banco de pruebas** de la etapa y de todas las grabaciones nuevas. | `cli.py` | unit: `replay` sobre un MP4 sintético generado en el test; `calibrate` con pytest-qt |
| 1.15 | UI Etapa 1: `CoreBridge`, `Controller`, `CameraView` (rectificado + overlay, §6.5), `HealthStrip`, `MovesList`, `LiveView` con bloque de estado para standby, `CornerEditor` (imagen cruda con 4 manijas arrastrables, `QGraphicsView`), asistente pasos 1–4 (cámara, encuadre, esquinas + a1, verificar posición inicial), pestaña **Cámara** (dispositivo, exposición/enfoque si el backend lo permite, recalibrar, cruda/rectificada, confianza por casilla), pestaña **Log** básica. | `ui/` | pytest-qt offscreen alimentando el `CoreBridge` con snapshots falsos (ver §6.8) |
| 1.16 | Fixtures reales: grabar (§7.2), registrar manifests, Git LFS, `tests/fixtures_real/test_manifests.py` parametrizado; `docs/FIXTURES.md` y `docs/CALIBRATION.md`. | `tests/fixtures/`, `docs/` | `pytest -m fixtures` local; en CI con `lfs: true` si la cuota lo permite (§8.2, pregunta 5) |

### 3.2 Aceptación (PLAN §6, Etapa 1)

- `chessoptic replay` reconstruye **sin errores** la partida completa de `game_full_01` y los clips de jugadas especiales (`expected_moves` exactos, 0 falsos positivos).
- En vivo con luz normal: ≤ 1 falsa detección cada 50 jugadas. Se mide con `replay` sobre `noise_hands_01` y con una sesión real anotando a mano.
- Asistente de primer uso pasos 1–4 completos y calibración persistida por cámara; al reabrir con la misma cámara no pide recalibrar.
- Tests `unit` + `qt` verdes en CI; `fixtures` verdes localmente.

### 3.3 PRs sugeridos

1. `feat(capture): frame sources for webcam, video and image lists` (1.1, 1.2).
2. `feat(vision): calibration, warp and synthetic board helpers` (1.3, 1.4, 1.5).
3. `feat(vision): occupancy classifier trained from the initial position` (1.6, 1.7).
4. `feat(vision): stability detector and pipeline` (1.8, 1.9).
5. `feat(board): board model with legal-move inference and tracker` (1.10, 1.11).
6. `feat(core): health aggregation, runtime and tracking-only session` (1.12, 1.13).
7. `feat(cli): replay and calibrate commands` (1.14).
8. `feat(ui): live view, camera overlay, corner editor and wizard steps 1-4` (1.15, puede partirse en 2–3 PRs).
9. `test: real board fixtures and manifests` (1.16).

---

## 4. Etapa 2 — Modo local (Stockfish)

Objetivo: jugar una partida completa contra Stockfish solo con piezas físicas, con todos los estados de partida de la UI.

### 4.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea sin cámara |
|---|---|---|---|
| 2.1 | `adapters/base.py`: `OutputAdapter` Protocol de PLAN §4, `AdapterStatus`, `AdapterRunner` (hilo con loop asyncio, `submit(coro)`, `call_soon`, cierre ordenado). | `adapters/base.py` | unit con un `FakeAdapter` que graba lo que recibe |
| 2.2 | `game/clock.py`: `TurnClock` (tiempo del turno medido por el driver; opcional control de tiempo `base+inc` local). Fuente de reloj inyectable. | `game/clock.py` | unit con reloj falso |
| 2.3 | `game/session.py` **completa** + `docs/STATES.md`: estados de §6.4; entradas: `BoardEvent`, `AdapterEvent`, acciones (`resync`, `pause`, `reconnect`, `set_promotion`, `new_game`); salidas: `DriverState`, `GameInfo`, `PendingOpponentMove`, `OccupancyView.highlights`, `LogEntry`. Reglas clave: en `MyTurn` un `MoveDetected` se manda al adaptador y pasa a `OpponentTurn` solo con `MoveAccepted`; `MoveRejected` → `Mismatch` con instrucción de deshacer; `OpponentMove` → `Replay` con `tracker.verify_target`; `PositionMatched` → `MyTurn`; `MoveAmbiguous` → según `promotion_default` (`ask` → estado `Promotion`); `LinkStatus(lost)` en partida → `LinkLost` sin perder el estado anterior; `GameOver` → `GameOver` y después `VerifyingBoard` con progreso x/32. | `game/session.py`, `docs/STATES.md` | unit: cada transición de STATES.md es un test; secuencias completas (partida entera con fakes) |
| 2.4 | `adapters/local_engine.py`: `LocalEngineAdapter(engine_path, skill_level 0–20, move_time_ms | depth, my_color, time_control | None)`; usa `chess.engine` asíncrono (`popen_uci`); emite `LinkStatus(connected, "Stockfish 17")`, `GameStarted`, `MoveAccepted` (valida legalidad), `OpponentMove`, `ClockUpdate` desde `TurnClock`, `GameOver` (mate, tablas, abandono desde la UI). Detrás de un `EngineProtocol` (`play(board) -> Move`) para poder inyectar `ScriptedEngine`/`RandomEngine`. | `adapters/local_engine.py` | unit con `ScriptedEngine`; `@stockfish` con el binario real (CI Ubuntu instala `stockfish` con apt; en Windows/macOS se saltea) |
| 2.5 | `game/pgn.py`: exportar PGN con cabeceras (`Event`, `Site` = plataforma, `White`/`Black`, `Result`, `Date`, `TimeControl`) y comentarios opcionales con hora. | `game/pgn.py` | unit: PGN re-parseable por python-chess, igual a la lista de jugadas |
| 2.6 | Guardado de frames de error: cuando `PositionMismatch` o `MoveRejected`, el tracker guarda el rectificado y el crudo en `errors/` si `save_error_frames`; `LogEntry.frame_path`. | `board/tracker.py`, `core/config.py` | unit con `tmp_path` |
| 2.7 | UI estados de partida: `StateBlock` con variantes `MyTurn`, `Moving`, `OpponentTurn`, `Replay`, `Promotion`, `Mismatch`, `LinkLost` (§6.3); vista `FinPartida`; `Log` con filtros y exportar PGN/log; `Ajustes` completo (salida, promoción, estabilidad, frames, ventana, idioma, diagnóstico); **modo compacto**; sonido en errores (`QSoundEffect`); asistente pasos 5–6 con salida "Stockfish local" (nivel, color) y prueba. | `ui/views/`, `ui/widgets/state_block.py` | pytest-qt con snapshots: por cada `DriverState` se verifica texto, color de fondo/borde del bloque, botones visibles |
| 2.8 | `doctor`: chequeo de Stockfish con versión; Ajustes permite elegir la ruta a mano. | `doctor.py`, `ui/views/settings.py` | monkeypatch |

### 4.2 Aceptación (PLAN §6, Etapa 2)

- Partida completa contra Stockfish usando solo piezas físicas, sin tocar la UI salvo para arrancar: tus jugadas se detectan, las del motor se muestran grandes y se verifican al reproducirlas, el fin de partida lleva a "Reordená el tablero" y vuelve a listo.
- Todas las transiciones de `docs/STATES.md` cubiertas por tests `unit`; todas las variantes de `StateBlock` cubiertas por tests `qt`.
- Simulación completa sin cámara: `pytest tests/unit/test_full_game_local.py` juega una partida guionada con `ScriptedEngine` y `ListSource` sintético.

### 4.3 PRs sugeridos

1. `feat(adapters): adapter protocol, runner and local Stockfish adapter` (2.1, 2.4).
2. `feat(game): full game session state machine and clocks` (2.2, 2.3, STATES.md).
3. `feat(game): PGN export and error frame capture` (2.5, 2.6).
4. `feat(ui): in-game state blocks, game over, log filters and settings` (2.7, 2.8; partible).
5. `feat(ui): compact mode and wizard output steps`.

---

## 5. Etapa 3 — Lichess

Objetivo: partida real en Lichess desde el tablero físico, con relojes y jugada del rival por la Board API.

### 5.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea sin cámara ni red |
|---|---|---|---|
| 3.1 | `adapters/lichess.py` transporte: cliente `httpx.AsyncClient` con `Authorization: Bearer`, lector ndjson robusto (líneas vacías = keep-alive), reconexión con backoff, respeto de `429` (pausa 60 s). Endpoints: `GET /api/account` (validar token, nombre de usuario), `GET /api/account/playing` (retomar partida en curso al arrancar), `GET /api/stream/event` (`gameStart`, `gameFinish`), `GET /api/board/game/stream/{id}` (`gameFull`, `gameState` con `moves`, `wtime`, `btime`, `status`, `winner`), `POST /api/board/game/{id}/move/{uci}`, `POST .../resign`, `POST .../abort`, `POST .../draw/{yes|no}`. | `adapters/lichess.py` | unit con `httpx.MockTransport` y ndjson grabados en `tests/fixtures/lichess/*.ndjson`; test de reconexión y de 429 |
| 3.2 | `adapters/lichess.py` lógica: mapear a `AdapterEvent`: `LinkStatus(connected, "Lichess · <user>")`, `GameStarted(my_color, time_control, initial_fen)`, `OpponentMove` (diferencia de la lista `moves`), `MoveAccepted` cuando el `gameState` siguiente incluye nuestra jugada / `MoveRejected` ante 400, `ClockUpdate(wtime, btime)`, `GameOver(result, status)`. Promoción: la Board API necesita la pieza en el UCI (`e7e8q`) → se resuelve con `promotion_default` o con el estado `Promotion` de la UI (**decisión**, §8.2 pregunta 3). Solo variante `standard`; otras → `AdapterError`. | `adapters/lichess.py` | unit: secuencias de `gameState` → eventos; partida guionada completa con el fake |
| 3.3 | Token: Ajustes → "Conectar con Lichess": pegar token, validar con `/api/account`, guardar en `keyring`; mostrar usuario conectado y botón "Olvidar". Link directo a la página de creación de tokens con el scope pre-cargado (§7.4). | `ui/views/settings.py`, `core/secrets.py` | pytest-qt con `keyring` falso en memoria |
| 3.4 | UI: salida "Lichess" en el asistente (paso 5) y en `EsperandoCliente` ("Abrí una partida en lichess.org; ChessOptic la toma solo"); `Conectado` muestra el usuario; `GameInfo.platform = "lichess.org"`; relojes desde el cliente (`clock_source = client`). | `ui/` | snapshots qt |
| 3.5 | `doctor`: conectividad a `https://lichess.org/api/account` si hay token (opcional, `--online`). | `doctor.py` | monkeypatch |
| 3.6 | Test en vivo opcional `@lichess_live`: con `LICHESS_TOKEN`, crea un desafío contra la IA de Lichess (`POST /api/challenge/ai`, requiere scope `challenge:write`) y juega 2 jugadas guionadas; nunca en CI. | `tests/live/test_lichess_live.py` | manual |

### 5.2 Aceptación (PLAN §6, Etapa 3)

- Partida real en Lichess (casual, contra la IA o contra una persona) jugada completa desde el tablero físico: jugadas enviadas y aceptadas, jugadas del rival reproducidas y verificadas, relojes de Lichess en el bloque de turno, fin de partida con resultado.
- Si se corta internet a mitad de partida, la UI pasa a `EnlacePerdido`, reconecta sola y manda la jugada pendiente.
- Tests `unit` del adaptador con fakes verdes en CI.

### 5.3 PRs sugeridos

1. `feat(adapters): lichess board api transport with ndjson streams` (3.1).
2. `feat(adapters): lichess game events, clocks and promotion` (3.2).
3. `feat(ui): lichess token settings and connection flow` (3.3, 3.4, 3.5).
4. `test: optional live lichess test` (3.6).

---

## 6. Mapeo UI → PySide6 y eventos del núcleo

### 6.1 Arquitectura del paquete `ui/`

- `CoreBridge(QObject)`: una `Signal(object)` por snapshot: `health_changed`, `driver_state_changed`, `game_info_changed`, `occupancy_changed`, `pending_move_changed`, `frame_ready(QImage)`, `log_entry`, `cameras_changed`, `calibration_changed`. Se suscribe al `EventBus` y emite desde el hilo que sea; Qt entrega en el hilo GUI.
- `Controller`: métodos síncronos que la UI llama (`select_camera`, `set_corners`, `set_a1`, `confirm_calibration`, `set_output`, `start_local_game`, `connect_lichess(token)`, `resync`, `pause`, `resume`, `reconnect`, `set_promotion(piece)`, `export_pgn(path)`, `export_log(path)`, `toggle_always_on_top`, `toggle_compact`). Cada uno despacha al hilo del núcleo con `call_soon_threadsafe`.
- Las vistas **solo** leen snapshots y llaman al `Controller`. Nada de `chess` ni `cv2` en `ui/` salvo la conversión `np.ndarray → QImage` en `bridge.py`.

### 6.2 Shell (`main_window.py`)

| Elemento de UI.md | Widget |
|---|---|
| Ventana 380 × alto, redimensionable, mínimo 300 | `QMainWindow` con `setMinimumWidth(300)`, ancho inicial 380, alto = pantalla disponible; geometría persistida |
| Siempre arriba | `Qt.WindowStaysOnTopHint` (se re-aplica con `show()`) |
| Modo compacto 380 × 260 | `QStackedWidget` raíz con dos páginas: `FullShell` y `CompactView`; cambia tamaño fijo y vuelve |
| Header: marca + pill | `QWidget#header` con `QLabel` (ícono SVG + "ChessOptic" en Sora 600) y `HealthPill` |
| Nav inferior 4 pestañas | `NavBar(QWidget)` con 4 `QToolButton` checkables en `QButtonGroup`, íconos SVG + texto; oculto durante el asistente |
| Pestañas | `QStackedWidget` central: `LiveView`, `CameraTab`, `LogTab`, `SettingsTab`, `WizardView` |

### 6.3 Pantallas y estados → widgets → eventos → acciones

**Vista "En vivo"** (`views/live.py`), de arriba hacia abajo: `HealthStrip` → `StateBlock` → `CameraView` → `MovesList`.

| Pantalla (UI.md) | `DriverState.state` | `StateBlock` variante y estilo | Datos que consume | Acciones (→ `Controller`) |
|---|---|---|---|---|
| Tu turno (`Main`) | `InGame.MyTurn` | `MyTurnBlock`: fondo `turn`, texto blanco, "Tu turno", color propio + plataforma, relojes Vos (destacado)/Rival en Plex Mono, "Última jugada del rival: …" | `GameInfo` (color, plataforma, relojes, última jugada), `OccupancyView` con destino de la última jugada en `#8EC4EA` | — |
| Moviendo (no dibujado) | `InGame.Moving` | `MyTurnBlock` con `QProgressBar` indeterminada o puntos animados y texto "Detectando…" | `BoardEvent.HandDetected` → sesión → estado | — |
| Turno del rival (`TurnoRival`) | `InGame.OpponentTurn` | `OpponentTurnBlock`: fondo `surface`, borde `line-strong` 2 px, "Turno del rival · Esperando…", reloj rival destacado, "Tu jugada: X · enviada y aceptada" | `GameInfo` | — |
| Reproducí la jugada (`Reproducir`) | `InGame.Replay` | `ReplayBlock`: borde `brand-light` 3 px, etiqueta "Rival jugó · reproducila en el tablero", SAN grande (Plex Mono 28–32 px), frase humana, "Esperando que la cámara vea la jugada · tu reloj corre" + reloj | `PendingOpponentMove` (san, human_text, from/to), `OccupancyView` con origen `#F3D3A1` y destino `#8EC4EA` | — |
| Verificando reproducción | `InGame.Verifying` | `ReplayBlock` con indicador de actividad hasta `PositionMatched` | igual | — |
| Promoción | `InGame.Promotion` | `PromotionBlock`: "Elegí la pieza" con 4 botones (D, T, A, C) o aviso "elegí la pieza en la plataforma" según adaptador | `MoveAmbiguous` | `set_promotion(piece)` |
| Posición no coincide (`NoCoincide`) | `InGame.Mismatch` | `MismatchBlock`: borde `err` 2 px, ícono alerta, lista de `SquareIssue` en texto humano ("d6 tiene una pieza que no debería estar"), botones **Resincronizar** / **Ver frame** | `PositionMismatch`, `OccupancyView` con casillas en `#F0AFA9`, `LogEntry.frame_path` | `resync()`, abrir frame |
| Enlace perdido (`EnlacePerdido`) | `InGame.LinkLost` | `LinkLostCard` (`err-bg`): "<cliente> se desconectó", reloj corriendo, instrucción por adaptador, **Reconectar** / **Ver detalle**; debajo una fila compacta con el turno y la última jugada | `LinkStatus(lost)`, `GameInfo` | `reconnect()`, ir a Log |
| Fin de partida (`FinPartida`) | `InGame.GameOver` → `Standby.VerifyingBoard` | `GameOverCard`: resultado grande, resumen (jugadas, duración, errores), **Exportar PGN** / **Ver log**; abajo `ResetBoardCard` con progreso x/32 y texto | `GameOver`, `GameInfo`, `InitialPositionCheck` | `export_pgn()`, ir a Log |
| Inicio (`Inicio`) | `Standby.Starting` | `WizardView` paso 1: checklist de 4 ítems (`StepRow` con ícono de estado), `QComboBox` de cámaras, `CameraView` cruda como preview, **Usar esta cámara**, ayuda con `chessoptic doctor` | `cameras_changed`, `CameraStatus` | `select_camera(key)` |
| Encuadre (paso 2, no dibujado) | `Standby.Uncalibrated` | `WizardView` paso 2: preview cruda + consejos de `docs/CALIBRATION.md` (altura, luz, todo el tablero visible) | `frame_ready` | siguiente |
| Calibración (`Calibrar`) | `Standby.Uncalibrated` | `WizardView` paso 3: `Stepper` (6 segmentos), `CornerEditor` (`QGraphicsView` con `QGraphicsPixmapItem` + 4 `QGraphicsEllipseItem` arrastrables + `QGraphicsPolygonItem`), 4 `CornerStatus` chips, `QRadioButton` × 2 para a1, **Atrás** / **Confirmar esquinas** | `frame_ready`, calibración guardada | `set_corners`, `set_a1`, `confirm_calibration()` |
| Verificar tablero (`VerificarTablero`) | `Standby.VerifyingBoard` | `WizardView` paso 4 (y también `StateBlock` fuera del asistente): contadores Blancas/Negras x/16, texto de faltantes, `CameraView` con faltantes en `#F3D3A1`, **Recalibrar** / **Empezar desde otra posición** (deshabilitado en v1, tooltip "v2") | `InitialPositionCheck`, `OccupancyView` | `recalibrate()` |
| Esperando cliente (`EsperandoCliente`) | `Standby.WaitingClient` | `WizardView` paso 5 / `StateBlock`: `QComboBox` de salida, tarjeta "Anunciándose como …" (Chessconnect, Etapa 4) o "Esperando partida en Lichess como <user>" o "Stockfish local · nivel N" con **Empezar partida**, pasos numerados por salida | `LinkStatus(announcing)`, `AppConfig.output` | `set_output`, `start_local_game`, `connect_lichess` |
| Conectado sin partida (`Conectado`) | `Standby.ConnectedIdle` | `ReadyBlock`: "Listo para jugar", instrucción, "Conectado vía … hace N min", `CameraView` con 32/32 | `LinkStatus(connected)`, `OccupancyView` | — |
| Modo compacto (`Compacto`) | cualquiera | `CompactView`: header con pill corta + botón expandir, `StateBlock` reducido (turno, relojes, última jugada), `CameraView` miniatura | los mismos snapshots | `toggle_compact()` |

**Otras pestañas**

| Pestaña | Widgets | Datos / acciones |
|---|---|---|
| Cámara (`views/camera.py`) | `QComboBox` dispositivo; `QSlider` exposición y enfoque (solo si `cv2.CAP_PROP_*` responde; si no, deshabilitados con tooltip); **Recalibrar**; `QRadioButton` cruda/rectificada; `CameraView` grande; `ConfidenceGrid` (8×8 con número por casilla) | `frame_ready`, `OccupancyView.confidence`, `CameraStatus` → `select_camera`, `set_camera_prop`, `recalibrate` |
| Log (`views/log.py`) | `QButtonGroup` de filtros (Todo / Jugadas / Eventos / Errores · N); `QListView` con `LogModel(QAbstractListModel)` y delegate (hora mono, punto de color por tipo, texto, detalle); **Exportar PGN** / **Exportar log** | `log_entry` → `export_pgn`, `export_log`, abrir `frame_path` |
| Ajustes (`views/settings.py`) | Grupos `SettingsGroup` con `SettingsRow`: Salida (`QComboBox` plataforma, `QComboBox` promoción), Lichess (token, usuario, Conectar/Olvidar), Stockfish (ruta, nivel `QSlider` 0–20, tiempo por jugada), Detección (`QSlider` estabilidad 250–2000 ms con texto "Espera N ms…", `QCheckBox` guardar frames), Ventana (`QCheckBox` siempre arriba, compacto en partida, sonido, `QComboBox` idioma), Diagnóstico (3 tarjetas fps/latencia/protocolo + **Ver tráfico del protocolo**, en v1 muestra el log de Lichess) | `AppConfig` ↔ `Controller.update_config(...)`; `Diagnostics` snapshot (fps análisis, latencia detección→UI) |

### 6.4 Estados del `DriverState` y reglas del semáforo

Estados (los nombres son los del código; el texto de la UI está en español):

- `Standby`: `Starting`, `Uncalibrated`, `VerifyingBoard`, `WaitingClient`, `ConnectedIdle`, `Paused`.
- `InGame`: `MyTurn`, `Moving`, `OpponentTurn`, `Replay`, `Verifying`, `Promotion`, `Mismatch`, `LinkLost`, `GameOver`.

`HealthAggregator` (nivel y texto de la pill), en orden de prioridad:

| Condición | Nivel | Pill |
|---|---|---|
| `Paused` o sin cámara elegida | `idle` | "Pausado" / "Iniciando" |
| Sin calibración | `idle` | "Sin calibrar" |
| Cámara `disconnected` o `no_permission` | `err` | "Sin cámara" |
| Enlace `lost` **en partida** | `err` | "Enlace perdido" |
| Tablero `occluded` > 3 s **en partida** o `moved` | `err` | "Tablero perdido" |
| Tablero `low_confidence` o `Mismatch` o `VerifyingBoard` incompleto | `warn` | "Revisar tablero" / "Tablero incompleto" |
| Cámara `low_fps` (< 6 fps de análisis) | `warn` | "Cámara lenta" |
| Enlace `announcing` / `inactive` con salida elegida | `warn` | "Esperando cliente" |
| Todo bien | `ok` | "Driver OK" |

El turno **nunca** cambia el semáforo: se comunica solo con el `StateBlock` (azul = mi turno, borde = rival).

### 6.5 `CameraView` (overlay de ocupación)

- `QWidget` con `paintEvent`: dibuja el `QImage` rectificado escalado al ancho disponible (cuadrado), encima las 64 celdas con relleno semitransparente opcional, círculos por ocupación (blanco con borde `line-strong` = pieza blanca; `ink` = negra), resaltados por tipo (`origin` `#F3D3A1`, `destination` `#8EC4EA`, `error` `#F0AFA9`, `missing` `#F3D3A1`), coordenadas a–h / 1–8 según `a1_corner`, etiqueta superior ("Cámara · vista rectificada" + confianza o resumen).
- Recibe `frame_ready(QImage)` y `occupancy_changed(OccupancyView)` por separado; repinta como máximo a 15 fps (`QTimer` de coalescencia).
- Modo "cruda" (pestaña Cámara y asistente): muestra el frame original con el cuadrilátero de calibración.
- Conversión `np.ndarray BGR → QImage` en `bridge.py` con copia explícita (`QImage(...).copy()`) para no apuntar a memoria del hilo de visión.

### 6.6 Tema y tipografía

- `theme.py`: `Tokens` dataclass con los valores de UI.md §2; `build_qss(tokens)` genera la hoja con selectores por `objectName` y propiedades dinámicas (`level="ok|warn|err|idle"`, `variant="my_turn|opponent|replay|mismatch|link_lost"`), re-polish al cambiar propiedades.
- Fuentes en `assets/fonts/` cargadas con `QFontDatabase.addApplicationFont`; `QApplication.setFont(IBM Plex Sans 13)`; Sora para marca y títulos; Plex Mono para jugadas, relojes y log.
- Íconos SVG monocromos propios en `assets/icons/` pintados con `QIcon` y color por `level` (regla "color + ícono siempre").

### 6.7 Idioma

Todos los textos pasan por `self.tr()` desde el primer widget y se extraen con `pyside6-lupdate` a `ui/i18n/chessoptic_es.ts` y `chessoptic_en.ts`. **La v1 se publica en español**; el `.ts` en inglés queda vacío hasta que haya traducción (§8.2, pregunta 6). El selector "Idioma" de Ajustes muestra solo los idiomas con `.qm` compilado.

### 6.8 Tests de UI (pytest-qt, offscreen)

- `tests/qt/conftest.py`: fixture `bridge` (un `CoreBridge` sin núcleo) y `window(qtbot, bridge)`.
- Por cada estado de §6.3: emitir los snapshots falsos y verificar `StateBlock.property("variant")`, textos visibles, botones habilitados, color de la pill.
- `CornerEditor`: arrastrar manijas con `qtbot.mouseMove/Press/Release` y verificar que `set_corners` se llama con las coordenadas en píxeles de la imagen (no del widget).
- `CameraView`: renderizar a `QPixmap` y comparar con imagen de referencia con tolerancia (solo en Linux para evitar diferencias de antialiasing; en los otros SO, solo que no lance).

---

## 7. Para hacer en casa

Checklist en orden. Lo marcado con ★ es bloqueante para la etapa.

### 7.0 Resumen

| Antes de | Qué |
|---|---|
| Etapa 0 | ★ uv + Python 3.12, ★ Git LFS, libs de Qt (Linux), bajar fuentes, ★ Stockfish (lo chequea `doctor`) |
| Etapa 1 | ★ cámara + soporte, ★ tablero y piezas con contraste, luz, ★ grabar fixtures (§7.2.4) |
| Etapa 2 | ★ Stockfish en PATH o ruta conocida; pieza extra para promoción |
| Etapa 3 | ★ cuenta Lichess + token `board:play` (+ `challenge:write`), segunda cuenta o rival para probar |
| En paralelo | Primer contacto con el autor de Chessconnect (Etapa 4, no bloquea la v1) |

### 7.1 Antes de la Etapa 0: instalar

**Todos los SO**

| Qué | Cómo |
|---|---|
| `uv` (trae Python) | Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` · macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` · después `uv python install 3.12` |
| Git LFS | Windows: `winget install GitHub.GitLFS` · macOS: `brew install git-lfs` · Debian/Ubuntu: `sudo apt install git-lfs` · después, una vez: `git lfs install` |
| Fuentes (solo bajar, se empaquetan en `assets/fonts/`, no hace falta instalarlas) | Sora: https://fonts.google.com/specimen/Sora (botón "Get font" → zip, usar los TTF estáticos 400/600/700) · IBM Plex Sans y Plex Mono: https://github.com/IBM/plex/releases (zips "IBM-Plex-Sans" y "IBM-Plex-Mono", TTF 400/600). Guardar también los `OFL.txt`. |
| Stockfish | Windows: https://stockfishchess.org/download/ → zip "Windows x86-64 AVX2" (o la variante que indique para tu CPU), descomprimir y agregar la carpeta al PATH o anotar la ruta para Ajustes · macOS: `brew install stockfish` · Debian/Ubuntu: `sudo apt install stockfish` (versión del repo; alcanza para v1) |

**Windows 11 (tu máquina)**: nada más. Si la cámara no abre con `doctor`, probar en Configuración → Privacidad → Cámara que las apps de escritorio tengan permiso.

**macOS**: Xcode Command Line Tools (`xcode-select --install`) por si algún wheel compila. La primera vez que se abre la cámara, macOS pide permiso **a la app que lanza el proceso** (Terminal, iTerm, VS Code): aceptarlo ahí.

**Linux (Debian/Ubuntu)**:

```bash
sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libegl1 libgl1 libdbus-1-3 \
  libfontconfig1 v4l-utils
sudo usermod -aG video "$USER"   # cerrar sesión y volver a entrar
v4l2-ctl --list-devices          # para ver la cámara
```

**No hace falta para la v1** (son de la Etapa 4, no instalar todavía): librerías BLE (`bleak`, `bless`), com0com, `socat`, drivers de puertos virtuales, extensión Chessconnect.

### 7.2 Antes de la Etapa 1: hardware, armado y fixtures

#### 7.2.1 Modelos o pesos a bajar

**Ninguno.** La v1 no usa redes neuronales: el clasificador de ocupación se entrena solo con la posición inicial en cada sesión. Stockfish trae su red NNUE embebida en el binario. Los pesos de un detector de piezas son Etapa 5.

#### 7.2.2 Cámara

- Cualquier webcam UVC 1080p sirve; ideal una que permita **fijar enfoque y exposición** (Logitech C920/C922/Brio o similar). El autoenfoque y la autoexposición "respirando" son la primera causa de falsos positivos.
- Alternativa válida: el celular como webcam (iPhone con Continuity Camera en macOS; Android/iPhone con Camo, Iriun o DroidCam en Windows/Linux). Para fixtures también sirve grabar directo con el celular, siempre que quede **fijo**.
- Soporte: brazo articulado con clamp al escritorio o trípode con brazo horizontal. El requisito es que **no se mueva entre la calibración y la partida**.

#### 7.2.3 Altura, ángulo, luz, tablero

| Variable | Recomendación v1 | Por qué |
|---|---|---|
| Ángulo | **Cenital** (90°, mirando hacia abajo) o lo más cercano posible (≥ 60° de elevación). Si es oblicua, desde el lado del rival o desde un costado, nunca desde tu lado (la mano tapa el tablero). | Con cámara baja las piezas altas ocultan la casilla de atrás; la v1 clasifica el centro de cada casilla y necesita verlo. |
| Altura | La que haga que el tablero ocupe **≥ 60 % del encuadre** con margen de ~2 casillas alrededor. Con un tablero de 50 cm y lente de webcam, suele ser 60–80 cm sobre el tablero. | Más píxeles por casilla = mejor clasificación. |
| Resolución / fps | 1280×720 a 30 fps (la app analiza a 10–15). | Suficiente y liviano. |
| Luz | Difusa, pareja, desde arriba o desde el frente. Evitar: ventana de fondo (contraluz), lámpara puntual que proyecte sombras largas de las piezas, luz que cambie durante la partida. Fijar en la cámara anti-parpadeo 50 Hz. | Sombras largas se confunden con piezas negras; cambios de luz corren la referencia de "casilla vacía". |
| Tablero | Tablero de torneo **mate**, casillas 50–57 mm, buen contraste claro/oscuro (ej. arce/nogal, no "dos tonos de marrón parecidos"). Sin brillo ni laca espejada. | Reflejos y bajo contraste bajan la confianza. |
| Piezas | Staunton con contraste fuerte entre bandos y contra **ambas** casillas: blancas marfil/boj claro, negras ébano/negro. Evitar piezas de madera oscura rojiza sobre casillas oscuras del mismo tono. | La v1 distingue vacía/blanca/negra por color y textura del centro de la casilla. |
| Marca de a1 | Pegar una marca pequeña fuera de la zona de juego donde está a1 (no cambia la detección, sirve para no equivocarse al calibrar y al grabar). | — |

Si tu tablero/piezas actuales no cumplen el contraste, decilo en §8.2 pregunta 2 antes de grabar fixtures: es más barato cambiar el tablero que luchar con el clasificador.

#### 7.2.4 Videos y fotos a grabar como fixtures

Reglas generales:

- **Cámara fija** durante toda la sesión de grabación; si se mueve, empezar una sesión nueva (las esquinas van por sesión en el manifest).
- Formato: **MP4 (H.264), 1280×720, 30 fps**, sin estabilización digital, enfoque y exposición **fijos**. Audio no hace falta.
- Empezar cada sesión con 10 s de **posición inicial sin manos** (sirve para calibrar y entrenar).
- Entre jugadas, retirar la mano del encuadre y esperar **≥ 1 s** (salvo en el clip de "manos/errores", que es a propósito).
- Jugar ambos bandos. Anotar las jugadas en papel o seguirlas en una app de ajedrez a la vez para no perder el PGN.
- Nombrar: `tests/fixtures/<sesion>_<clip>/video.mp4` + `manifest.json` (las esquinas se completan después con `chessoptic calibrate`).

| Clip | Duración | Contenido | Para qué |
|---|---|---|---|
| `s1_static_initial` | 10–15 s | Posición inicial, nadie toca nada | Calibración, entrenamiento, verificación 32/32 |
| `s1_missing_pieces` | 30 s | Posición inicial con 1 pieza faltante (d1), después 2 (d1 y g8), después una pieza blanca en una casilla equivocada; pausas de 5 s entre cambios | `InitialPositionCheck`, pantalla "Verificar tablero" |
| `s1_game_short_01` | 1–2 min | Mate del pastor: `1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7#` | Primer test de punta a punta |
| `s1_en_passant` | 30 s | `1. e4 Nf6 2. e5 d5 3. exd6` | Captura al paso (3 casillas cambian) |
| `s1_castle_short` | 45 s | `1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. O-O Nf6 5. d3 O-O` | Enroque corto de ambos; hacerlo como en vivo (rey primero, torre después) |
| `s1_castle_long` | 45 s | `1. d4 d5 2. Nc3 Nc6 3. Bf4 Bf5 4. Qd2 Qd7 5. O-O-O O-O-O` | Enroque largo de ambos |
| `s1_promotion` | 45 s | `1. a4 b5 2. axb5 a6 3. bxa6 Nf6 4. a7 Nd5 5. axb8=Q` | Promoción con captura (el peón de a7 toma el caballo de b8); poner una **dama extra** (o torre invertida; para la v1 vale cualquier pieza blanca) |
| `s1_game_full_01` | 10–20 min | Partida completa, 25–40 jugadas, ritmo normal, con al menos una captura, un enroque y jaque mate o rey ahogado | **Aceptación de la Etapa 1** |
| `s1_noise_hands_01` | 3–4 min | Partida corta "sucia": mano que duda sobre el tablero, pieza levantada y devuelta a la misma casilla, pieza tocada/ajustada sin mover, pieza volteada y vuelta a parar, jugada hecha y deshecha antes de soltar, piezas descentradas, el brazo cruzando el tablero | Estabilidad, transitorios, medición de falsos positivos |
| `s1_reset_board` | 1 min | Desde una posición final, reordenar las 32 piezas a la inicial | Progreso x/32 de "Fin de partida" |
| `s2_light_*` (sesión 2) | 15 s cada uno + 1 min | Posición inicial con: luz de día, lámpara encendida, lámpara + día, sombra parcial (tu cuerpo entre la luz y el tablero). Más un clip de 1 min jugando mientras se apaga y prende la lámpara | Robustez a luz; define el umbral de "baja confianza" |
| `s3_oblique_*` (sesión 3, opcional) | repetir `static_initial`, `game_short_01` y `castle_short` | Cámara a ~45° de elevación desde el lado del rival | Saber cuánto se degrada fuera del cenital (respuesta a la pregunta 1 de §8.2) |

Fotos (JPG, misma cámara fija, sin manos), en `tests/fixtures/photos/` con un `positions.json` que mapea archivo → FEN:

- 10–20 posiciones distintas de partidas reales (anotá el FEN con una app o Lichess "Editor de tablero").
- Las mismas 3–4 posiciones bajo las variantes de luz de la sesión 2.

Volumen estimado: 25–35 min de video, ~1,5–2,5 GB en 720p. Ver §8.2 pregunta 5 sobre dónde alojarlo.

### 7.3 Antes de la Etapa 2

- Stockfish instalado y visible: `chessoptic doctor` lo tiene que marcar ✓. Si no está en PATH, anotar la ruta para cargarla en Ajustes.
- Tener a mano la pieza extra para promociones.
- Opcional: parlantes para el sonido de error.

### 7.4 Antes de la Etapa 3: cuentas y tokens

- Cuenta en https://lichess.org (gratis). Conviene una **cuenta de prueba** aparte para no ensuciar el rating; se puede jugar casual contra la IA de Lichess sin rival humano.
- Token personal con los scopes pre-cargados: https://lichess.org/account/oauth/token/create?scopes[]=board:play&scopes[]=challenge:write&description=ChessOptic
  - `board:play`: jugar con la Board API (obligatorio).
  - `challenge:write`: crear desafíos contra la IA desde el test en vivo (opcional, solo para probar).
  - Guardarlo en un gestor de contraseñas; para desarrollo exportarlo como `LICHESS_TOKEN`. Nunca al repo.
- Para probar contra una persona: una segunda cuenta en otro navegador o un amigo. La Board API no admite bullet; usar rapid (10+0) o blitz lento para las pruebas.
- **Chessconnect: nada para la v1.** No hace falta cuenta ni instalar la extensión todavía.
- chess.com: nada para la v1.

### 7.5 Cómo validar lo que preparaste (antes de abrir el primer PR de cada etapa)

| Etapa | Chequeo |
|---|---|
| 0 | `uv --version`, `git lfs version`, `stockfish` responde a `uci` con `uciok`, carpeta `fonts/` con 7–8 TTF + licencias |
| 1 | `chessoptic doctor` ve la cámara; los clips abren en VLC; cada clip tiene su `manifest.json` con `expected_moves`; después del PR de `calibrate`, todos los manifests tienen `corners` |
| 2 | `chessoptic doctor` marca Stockfish ✓ |
| 3 | `curl -H "Authorization: Bearer $LICHESS_TOKEN" https://lichess.org/api/account` devuelve tu usuario |

### 7.6 En paralelo (no bloquea la v1): primer contacto con Chessconnect

PLAN §4.2 pide consultar al autor **antes** de escribir el CompatAdapter. La respuesta puede tardar semanas, así que conviene mandar el mensaje durante la Etapa 1. Un borrador corto en inglés, a info@chessconnect.de o en el Discord del proyecto: quién sos, qué es ChessOptic (tablero por cámara, open source), que querés saber si aceptaría (a) un protocolo abierto nuevo o (b) que ChessOptic hable como un tablero ya soportado (DGT por serie o Chessnut por BLE), y qué tablero recomendaría emular. Registrar la respuesta en PLAN §6, Etapa 4.

---

## 8. Riesgos y decisiones pendientes

### 8.1 Riesgos técnicos (además de PLAN §7)

| Riesgo | Impacto | Mitigación en este plan |
|---|---|---|
| `opencv-python` y PySide6 pelean por Qt en Linux | La app no abre | Usar `opencv-python-headless` (tarea 0.2) y un test que importa ambos |
| Cuota de Git LFS en GitHub (1 GB de almacenamiento y 1 GB/mes de bajada gratis) con ~2 GB de video | CI no puede bajar fixtures; el repo se vuelve caro de clonar | Decidir en §8.2 pregunta 5; opción recomendada: fixtures en GitHub Releases + script de descarga con caché, LFS solo para fotos |
| Oclusión con cámara oblicua | La casilla detrás de una pieza alta se clasifica mal | Recomendar cenital; sesión 3 de fixtures mide la degradación; si es grave, v1 documenta "solo cenital" |
| Autoenfoque / autoexposición de la webcam | Falsos positivos y baja confianza | Fijar desde la pestaña Cámara cuando el backend lo permite; documentar en CALIBRATION.md |
| Enumeración lenta de cámaras en Windows (MSMF) | `doctor` y el asistente tardan segundos | `CAP_DSHOW` primero, timeout por índice, enumeración en hilo |
| Promoción sin reconocimiento de piezas | Ambigüedad entre 4 jugadas | Default configurable + estado `Promotion` en la UI; en Lichess hay que decidir (pregunta 3) |
| Reconexión de la Board API y `429` | Partida perdida por tiempo | Backoff, cola de la jugada pendiente, `EnlacePerdido` visible |
| Rendimiento del pipeline en equipos modestos | Latencia detección → UI alta | Análisis a 10–15 fps, rectificado 512×512, features vectorizados en numpy; diagnóstico muestra fps y latencia |
| Posición "rara" sin jugada legal (pieza caída que rueda) | Mismatch falso | Grace de 2 s antes de `Mismatch`; "Resincronizar" siempre disponible |
| Fuentes: licencias y tamaño del paquete | — | OFL permite empaquetar; ~1,5 MB en total |

### 8.2 Decisiones que necesito que respondas

1. **Ángulo de cámara que vas a usar de verdad**: ¿cenital (recomendado) u oblicua? Cambia el diseño de features (en oblicua hay que mirar la base de la casilla, no el centro) y qué fixtures priorizar.
2. **Tu tablero y piezas**: ¿color de casillas y de piezas, tamaño de casilla, acabado mate o brillante? Mandá una foto. Si el contraste es flojo, mejor cambiarlo antes de grabar.
3. **Promoción en Lichess**: la Board API necesita la pieza en la jugada. ¿Default "siempre dama" con opción de elegir en Ajustes, o estado "Promoción" en la UI con 4 botones (recomendado: default dama + botones solo si el default está en "preguntar")?
4. **Dónde guardar el token de Lichess**: `keyring` (llavero del SO, una dependencia más, en Linux necesita un backend como GNOME Keyring/KWallet) o archivo `secrets.json` con permisos 0600 (simple, menos seguro). Recomendación: `keyring` con fallback a archivo si no hay backend.
5. **Alojamiento de fixtures**: Git LFS en GitHub (simple; cuota gratis chica; los clones bajan todo) o assets de GitHub Releases + script `scripts/fetch_fixtures.py` con caché (más pasos, sin cuota). Recomendación: Releases para video, LFS para fotos.
6. **Idiomas de la v1**: ¿solo español, o también inglés desde el principio (traducir ~150 cadenas antes de publicar)? Recomendación: estructura i18n lista desde el día uno, publicar en español, inglés cuando haya tiempo.
7. **Stockfish**: ¿basta con exigirlo instalado (lo chequea `doctor` y Ajustes permite la ruta), o la app debe ofrecer descargarlo? Recomendación v1: exigirlo; descarga automática en Etapa 6 con los instaladores.
8. **Reloj en modo local**: ¿jugar contra Stockfish con control de tiempo (ej. 10+0 medido por el driver) o sin reloj (solo tiempo de turno informativo)? Recomendación: sin reloj por defecto, opcional en Ajustes.
9. **Máquinas para probar**: ¿tenés acceso a una Mac y/o a un Linux de escritorio con cámara además de Windows, o la aceptación "abre en los tres SO" se valida solo con CI offscreen y un voluntario?
10. **Modo "solo seguimiento"** (`NullAdapter`): ¿lo dejamos visible para usuarios en la v1 (como "Sin salida: solo seguir la partida y exportar PGN") o solo para desarrollo? Recomendación: visible; es útil para anotar partidas presenciales y no cuesta nada.
11. **Pieza extra para promoción**: ¿tenés una segunda dama de cada color? Si no, en v1 cualquier pieza del mismo bando sirve físicamente, pero conviene que las fixtures reflejen lo que vas a hacer en una partida real.
12. **Resolución de a1 en el asistente**: UI.md ofrece 2 opciones (abajo izq. / arriba der.). Con cámara desde un costado hacen falta las 4 esquinas. ¿Dejamos las 4 (recomendado, es trivial) o solo las 2 del diseño?
13. **Loop asyncio en hilo propio** (§1.2) vs. `qasync`: la propuesta es hilo propio para mantener el núcleo libre de Qt. ¿Objeción?
14. **Nombre de la carpeta de configuración y del app id**: `ChessOptic` en `platformdirs` (→ `%APPDATA%\ChessOptic`, `~/Library/Application Support/ChessOptic`, `~/.config/ChessOptic`). ¿OK?
15. **Partida ya en curso al arrancar** (Lichess): si hay una partida activa en tu cuenta cuando abrís ChessOptic, ¿la retoma automáticamente (requiere que el tablero físico esté en esa posición: en v1 no lo podemos verificar sin detector de piezas, solo la ocupación) o pide confirmación ("Tablero en la posición de la jugada 14? Confirmar")? Recomendación: pedir confirmación y verificar por ocupación.
