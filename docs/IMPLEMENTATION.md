# ChessOptic — Plan de implementación v1

> Complementa a [`PLAN.md`](PLAN.md) (qué y por qué) y a [`UI.md`](UI.md) (cómo se ve).
> Este documento dice **en qué orden se construye, en qué archivos, cómo se prueba cada parte sin cámara,
> cuál es el criterio de aceptación de cada hito y qué tiene que preparar el autor en casa**.
> Si algo acá contradice al código, actualizá este documento en el mismo PR.

---

## 0. Cómo leer este documento y qué lo ordena

### 0.1 Decisiones del autor (2026-10-29) que fijan el orden

Estas respuestas reemplazan a las preguntas abiertas de la primera versión de este documento:

| Tema | Decisión |
|---|---|
| **Orden de trabajo** | MVP primero y en este orden: (1) correr el paquete y que levante la UI, (2) **flujo de setup completo** (cámara → esquinas → chequeo de detección), (3) estados de la UI sobre ese flujo, (4) partida contra Stockfish **sin reloj**: yo muevo, él mueve. Todo lo demás viene después, planteado por etapas. |
| **Cámara** | No importa cuál ni desde qué ángulo. El usuario elige **cualquier cámara**, mueve las esquinas con el mouse y ChessOptic **chequea** si con esa cámara, ese tablero y esas piezas detecta bien. Este flujo de setup merece más trabajo que el resto de la UI. Soporte de celular como cámara y mejoras de carga: después. |
| **Tablero y piezas** | No se exige un tablero concreto: el **chequeo de detección** del setup le dice al usuario si lo que tiene sirve y qué ajustar. |
| **Proveedores (contra quién se juega)** | Arquitectura de **proveedores enchufables**: locales (Stockfish primero; otros motores, modelos propios o lo que alguien quiera agregar por PR) y online (Lichess, chess.com vía Chessconnect, otros). El MVP solo trae Stockfish local. |
| **Modos de juego** | Patrón Strategy: el modo base es **sin reloj**. Bullet/blitz/rápidas y cualquier otro modo con su propia configuración vienen después. No se diseñan ahora. |
| **Lichess, token, promoción, Chessconnect** | **Pendientes**, fuera del MVP. El destino que importa es chess.com, que todavía no está investigado. |
| **Modo "solo seguimiento"** | Visible para usuarios (seguir una partida presencial y exportar PGN). |
| **Dama extra para promoción** | No depender de eso. Problema de más adelante. |
| **Plataforma base** | Windows 11. Tiene que seguir funcionando en macOS y Linux (CI en los tres). |
| **Estilos de la UI** | PySide6 con **QSS (Qt Style Sheets, sintaxis tipo CSS)**. Tokens del diseño en código y una hoja de estilo que el usuario puede sobreescribir. |
| **Código** | Buenas prácticas, patrones de diseño, escalable desde el primer PR aunque el MVP sea chico. |
| **Alcance real: POC, no MVP** (2026-10-29, segunda ronda) | Lo que sigue es una **prueba de concepto**: si la v1 funciona bien, recién ahí se arma un MVP con lo demás. Consecuencias: (a) **sin tests por ahora**; la estrategia de §2.6 y las columnas "Cómo se testea" quedan como plan para después del POC, la verificación es manual corriendo la app; (b) **arquitectura mínima pero extensible**: se definen las interfaces (adaptadores, motores, fuentes, modos) y se implementa **solo lo que el POC usa**; nada de registros de plugins, entry points ni formularios generados hasta que haga falta un segundo proveedor; (c) CI solo con lint y tipos. |
| **Carpeta de configuración** | `ChessOptic`. |
| **Asyncio en hilo propio** (no `qasync`) | OK. |

### 0.2 Mapa del documento

| Sección | Para qué |
|---|---|
| §1 | Hitos del MVP y cómo se mapean a las etapas del PLAN. |
| §2 | Decisiones transversales: layout, patrones, hilos, contrato de eventos, configuración, tests sin cámara, extensibilidad. |
| §3–§6 | Hitos 0 a 3: tareas en orden, archivos, cómo se testea sin cámara, aceptación, PRs sugeridos. |
| §7 | Lo que viene después del MVP, planteado por etapas sin detallar. |
| §8 | Mapeo de pantallas y estados de `UI.md` a widgets PySide6 y eventos del núcleo. |
| §9 | "Para hacer en casa": instalar, hardware, grabaciones, en orden. |
| §10 | Riesgos y lo que sigue pendiente. |

---

## 1. Hitos del MVP

> **Estado al 2026-10-29**: H0, H1, H2 y H3 implementados (PRs #2, #3, #4 y #5, uno por hito, cada uno sobre el anterior). Falta probar H1–H3 con la cámara y el tablero reales del autor y ajustar umbrales (ver §10.2). Documentos nuevos: `docs/SETUP.md`, `docs/STATES.md`, `docs/EXTENDING.md`.

| Hito | Qué se puede hacer al terminarlo | Etapa del PLAN |
|---|---|---|
| **H0 — Corre** | `uv run chessoptic` abre la ventana lateral con el aspecto final (vacía), `chessoptic doctor` dice qué falta. CI verde en Windows, macOS y Linux. | Etapa 0 |
| **H1 — Setup** | Flujo de primer uso completo: elegir cámara, encuadrar, marcar esquinas y a1, **chequeo de detección** (posición inicial reconocida 32/32, prueba de una jugada) con confirmación del usuario y diagnóstico si falla. Perfil de cámara guardado. | Etapa 1 (visión) |
| **H2 — Estados** | La vista "En vivo" refleja la máquina de estados completa (standby y partida) y el modo **solo seguimiento** detecta jugadas de ambos bandos y exporta PGN. | Etapa 1 (BoardModel + UI) |
| **H3 — Stockfish** | Partida completa contra Stockfish local, sin reloj, solo con piezas físicas: mis jugadas se detectan, las suyas se muestran y se verifican al reproducirlas. | Etapa 2 |
| Después | Modos con reloj, proveedores online (Lichess, chess.com/Chessconnect), promoción, celular como cámara, calibración automática, instaladores. | Etapas 3–6 |

Consecuencia para `PLAN.md` (actualizar en el PR de H0): la Etapa 3 (Lichess) deja de ser parte de la v1 mínima; §2 "Decisiones" gana dos filas (proveedores enchufables, modos de juego como Strategy); §3.1 gana `core/`, `game/` y la estructura de `adapters/`.

---

## 2. Decisiones transversales de implementación

### 2.1 Layout del paquete

```
chessoptic/
├── pyproject.toml                 # uv + hatchling; extras: [dev]; entry points para plugins
├── .github/workflows/ci.yml       # matriz windows / macos / ubuntu
├── assets/
│   ├── logo.png
│   ├── icons/                     # SVG monocromos
│   └── fonts/                     # Sora, IBM Plex Sans, IBM Plex Mono (OFL)
├── src/chessoptic/
│   ├── __init__.py                # __version__
│   ├── __main__.py                # python -m chessoptic
│   ├── cli.py                     # argparse: (sin args) → UI · doctor · replay · calibrate
│   ├── doctor.py
│   ├── core/
│   │   ├── events.py              # dataclasses congeladas: eventos y snapshots (§2.4)
│   │   ├── bus.py                 # EventBus (Observer) sin Qt
│   │   ├── config.py              # AppConfig + perfiles de cámara, load/save JSON (platformdirs)
│   │   ├── health.py              # HealthAggregator → semáforo
│   │   ├── registry.py            # Registry genérico + carga de entry points (plugins)
│   │   └── runtime.py             # CoreRuntime (Facade): hilos, loop asyncio, cableado
│   ├── capture/
│   │   ├── source.py              # Frame, FrameSource (Protocol), ListSource, ImageSequenceSource
│   │   ├── webcam.py              # WebcamSource + enumeración; backend por SO
│   │   ├── video.py               # VideoFileSource
│   │   └── registry.py            # tipos de fuente registrables ("webcam", "video"; después "celular")
│   ├── vision/
│   │   ├── calibration.py         # Calibration (4 esquinas + a1), warp(), persistencia por cámara
│   │   ├── squares.py             # 64 celdas, región de muestreo, índice ↔ chess.Square
│   │   ├── features.py            # features por celda, relativas a la propia casilla
│   │   ├── occupancy.py           # OccupancyClassifier: fit_initial / predict / refine / diagnose
│   │   ├── stability.py           # StabilityDetector (mano / estable)
│   │   ├── check.py               # SetupCheck: chequeo de detección del asistente (§4)
│   │   └── pipeline.py            # VisionPipeline: source → warp → stability → classifier
│   ├── board/
│   │   ├── occupancy.py           # Occupancy, OccupancyGrid, diff, from_board
│   │   ├── model.py               # BoardModel: chess.Board + inferencia por jugadas legales
│   │   └── tracker.py             # BoardTracker: OccupancyFrame estable → BoardEvent
│   ├── game/
│   │   ├── session.py             # GameSession (State): standby / partida (docs/STATES.md)
│   │   ├── modes.py               # GameMode (Strategy): FreePlay en MVP; con reloj después
│   │   └── pgn.py                 # exportar PGN
│   ├── adapters/                  # "proveedores" en la UI; OutputAdapter de PLAN §4
│   │   ├── base.py                # OutputAdapter (Protocol), AdapterInfo, AdapterStatus, AdapterRunner
│   │   ├── registry.py            # registro de proveedores: built-in + entry points `chessoptic.adapters`
│   │   ├── tracking.py            # TrackingAdapter: "solo seguimiento" (visible al usuario)
│   │   ├── local/
│   │   │   ├── engine.py          # EngineProtocol + UciEngine (cualquier motor UCI)
│   │   │   └── stockfish.py       # StockfishAdapter: UciEngine con presets de nivel
│   │   └── online/
│   │       └── README.md          # dónde van Lichess / Chessconnect cuando lleguen (§7)
│   └── ui/
│       ├── app.py                 # QApplication, fuentes, QSS, arranque
│       ├── bridge.py              # CoreBridge(QObject): eventos del núcleo → Signals Qt
│       ├── controller.py          # acciones de la UI → CoreRuntime
│       ├── theme.py               # tokens de UI.md §2 → QSS + override del usuario
│       ├── main_window.py         # ventana 380 px, QStackedWidget, nav inferior, siempre arriba, compacto
│       ├── views/                 # live.py, camera.py, log.py, settings.py, compact.py, wizard/
│       └── widgets/               # health_pill, health_strip, camera_view, state_block, moves_list,
│                                  # nav_bar, stepper, corner_editor, confidence_grid
├── tests/
│   ├── conftest.py
│   ├── helpers/                   # synthetic_board.py, scripted.py
│   ├── fixtures/                  # grabaciones reales (ver §2.6 y §9.3) + manifest.json
│   ├── unit/ · qt/ · fixtures_real/
└── docs/
    ├── PLAN.md · UI.md · IMPLEMENTATION.md
    ├── STATES.md                  # H2: máquina de estados detallada
    ├── SETUP.md                   # H1: guía de cámara / luz / encuadre para usuarios (reemplaza CALIBRATION.md del PLAN)
    ├── FIXTURES.md                # H1: cómo grabar y registrar grabaciones de prueba
    └── EXTENDING.md               # H3: cómo agregar un proveedor, un motor, una fuente de cámara o un modo
```

### 2.2 Patrones y dónde viven

| Patrón | Dónde | Para qué |
|---|---|---|
| **Protocol / Adapter** | `FrameSource`, `OutputAdapter`, `EngineProtocol` | Cada cosa externa (cámara, plataforma, motor) entra por una interfaz chica y se puede falsear en tests. |
| **Registry + plugins** | `core/registry.py`, `adapters/registry.py`, `capture/registry.py` | Los proveedores, motores y fuentes se registran por nombre. Los built-in se registran al importar; los externos por entry points en `pyproject.toml` (grupo `chessoptic.adapters`, `chessoptic.engines`, `chessoptic.sources`). Un tercero agrega un proveedor con un paquete pip o con un PR que suma un archivo. |
| **Strategy** | `game/modes.py` (`GameMode`) | El modo decide reloj, qué pasa al agotarse el tiempo, si hay revancha automática, etc. MVP: `FreePlay` (sin reloj). |
| **State** | `game/session.py` (`GameSession`) | Un objeto por estado con `on_event()`; las transiciones se documentan en `docs/STATES.md` y cada una tiene un test. |
| **Observer** | `core/bus.py`, Signals Qt en `ui/bridge.py` | Núcleo y UI desacoplados; la UI nunca llama al núcleo salvo por `Controller`. |
| **Facade** | `core/runtime.py` | Un punto de arranque/parada para CLI, UI y tests. |
| **Snapshots inmutables** | `core/events.py` | La UI recibe dataclasses `frozen=True`; no hay estado compartido mutable entre hilos. |
| **Inyección de dependencias por constructor** | en todo el núcleo | Nada instancia `cv2.VideoCapture` ni abre Stockfish dentro de una clase de lógica; se recibe por parámetro. |

### 2.3 Hilos y flujo de eventos

1. **El núcleo no importa Qt.** `core/`, `capture/`, `vision/`, `board/`, `game/`, `adapters/` se testean con pytest puro.
2. **Un solo hilo muta el estado de la partida.** `GameSession` vive en el hilo del loop asyncio (`AdapterRunner`) junto con los adaptadores. La visión le entrega `OccupancyFrame` con `loop.call_soon_threadsafe`.
3. **La UI recibe snapshots por Signals Qt.** `CoreBridge` se suscribe al bus desde cualquier hilo y emite; Qt encola al hilo GUI.
4. **La visión corre en su propio `threading.Thread`** a 10–15 fps de análisis; manda el frame rectificado a la UI a ≤ 15 fps.

```
 hilo visión                      hilo núcleo (asyncio)                        hilo GUI (Qt)
 ───────────                      ─────────────────────                        ─────────────
 FrameSource.read()
   → Calibration.warp()
   → StabilityDetector            GameSession ◄── AdapterEvent ── StockfishAdapter / (online después)
   → OccupancyClassifier             │  ▲                               ▲
   → OccupancyFrame ─ call_soon ────►│  │ BoardTracker.on_occupancy     │ on_board_event(MoveDetected)
                                     │  └── BoardModel · GameMode       │
                                     ▼                                  │
                                 EventBus.publish(snapshots) ───────────┴──► CoreBridge (Signals) ──► vistas
                                     ▲
 Controller (acciones UI) ── call_soon_threadsafe ──┘
```

### 2.4 Contrato de eventos (`core/events.py`)

Dataclasses congeladas con `ts: float` (`time.monotonic()`).

**Visión → núcleo**: `OccupancyFrame(grid, confidence[64], stable, motion, frame_index)`, `CameraStatus(state: ok | no_permission | disconnected | low_fps, fps, device)`, `BoardStatus(state: ok | occluded | low_confidence | moved, detail)`.

**BoardTracker → núcleo (`BoardEvent`)**: `InitialPositionCheck(white, black, missing, extra, complete)`, `MoveDetected(move, san, fen_before, fen_after)`, `MoveAmbiguous(candidates)` (solo promoción), `PositionMismatch(issues)`, `PositionMatched(fen)`, `HandDetected`, `BoardStable`.

**Adaptadores → núcleo (`AdapterEvent`)**: `LinkStatus(state: inactive | announcing | connected | lost, client, detail)`, `GameStarted(game_id, my_color, platform, mode, initial_fen)`, `OpponentMove(move, san)`, `MoveAccepted(move)`, `MoveRejected(move, reason)`, `ClockUpdate(white_ms | None, black_ms | None)`, `GameOver(result, reason)`, `AdapterError(message, recoverable)`.

**Snapshots → UI** (los de UI.md §5): `HealthState`, `DriverState`, `GameInfo`, `OccupancyView` (grid, confianza, resaltados origen/destino/error/faltante, esquina de a1), `PendingOpponentMove`, `LogEntry`, más `SetupCheckReport` (§4) y `Diagnostics` (fps, latencia).

### 2.5 Configuración y persistencia (`core/config.py`)

Con `platformdirs`, app `ChessOptic`:

| Qué | Dónde |
|---|---|
| `config.json`: `AppConfig` (proveedor elegido y su config, modo de juego, estabilidad ms, guardar frames de error, siempre arriba, compacto, sonido, idioma, ruta a Stockfish) | `user_config_dir` |
| `cameras/<camera_key>.json`: perfil de cámara = esquinas, a1, resolución, propiedades fijadas (exposición/enfoque si se pudo), **clasificador entrenado** del último setup, fecha, resultado del último chequeo | `user_config_dir` |
| `theme.qss`: override opcional del usuario (§8.6) | `user_config_dir` |
| `errors/<ts>.png`, `games/<ts>.pgn`, `logs/chessoptic.log` | `user_data_dir` |

`camera_key` = nombre del dispositivo + resolución (los índices de OpenCV cambian al enchufar cosas). `CHESSOPTIC_CONFIG_DIR` sobreescribe la carpeta (tests y CI).

### 2.6 Tests sin cámara: tres capas (plan para después del POC)

> Durante el POC no se escriben tests (§0.1). Lo que sigue describe cómo se van a probar las cosas cuando la v1 funcione; mientras tanto, el código se diseña para que sea posible (fuentes de frames inyectables, núcleo sin Qt) y se verifica a mano.

La regla de `CLAUDE.md` es que toda la visión y el BoardModel se prueben **sin cámara**. Para eso hacen falta imágenes de algún lado. Tres fuentes, de la más barata a la más fiel:

1. **Sintético** (`tests/helpers/synthetic_board.py`): `render(fen, *, square_px, colores, piece_radius, noise, brightness, perspective, hand, seed) -> np.ndarray`. Dibuja un tablero y discos por pieza a partir de un FEN. Cubre el 90 % de los tests: clasificador, calibración, estabilidad, pipeline completo, UI con overlay. Es determinista y corre en CI.
2. **Secuencias guionadas** (`tests/helpers/scripted.py`): lista `(fen, n_frames, hand)` → frames sintéticos. Recorre una partida entera por el pipeline en milisegundos, con transitorios (pieza levantada, enroque en dos tiempos).
3. **Grabaciones reales** (`tests/fixtures/`): clips **cortos** del tablero de verdad con la jugada esperada en un `manifest.json`. Son la única forma de saber si el clasificador funciona con luz, sombras y manos reales **sin estar sentado frente a la cámara**, y de volver a probar lo mismo después de cada cambio. Sin ellas, cada ajuste de la visión se valida a mano.

Cómo se mantienen chicas las grabaciones (ver §9.3): clips de 10–60 s a 720p, 15–20 clips, **~150–300 MB en total**, no 2 GB. Al principio viven solo en la máquina del autor (carpeta `tests/fixtures/` ignorada por git salvo los manifests); los tests que las usan se saltean si no están. Dónde alojarlas para que CI y otros colaboradores las tengan se decide cuando haga falta (§10.2).

Markers: `unit` (default), `qt` (pytest-qt, `QT_QPA_PLATFORM=offscreen`), `fixtures` (necesita grabaciones), `stockfish` (necesita el binario).

Formato de `manifest.json`:

```json
{
  "video": "video.mp4",
  "camera": "Logitech C920", "resolution": [1280, 720], "fps": 30,
  "corners": {"tl": [212, 88], "tr": [1070, 92], "br": [1098, 648], "bl": [184, 652]},
  "a1": "bottom-left",
  "start_fen": "startpos",
  "expected_moves": ["e2e4", "e7e5", "g1f3"],
  "notes": "luz de día, lámpara apagada"
}
```

Las esquinas se completan después de grabar con `chessoptic calibrate --video <clip>` (H1).

### 2.7 Extensibilidad desde el primer PR (`docs/EXTENDING.md` en H3)

- **Proveedor** (contra quién/dónde se juega): clase que implementa `OutputAdapter` + `AdapterInfo(name, kind: local | online, label, settings_schema)`; se registra con `@adapters.register("stockfish")` o por entry point. La UI arma el selector y el formulario de Ajustes a partir de `settings_schema` (dataclass con metadatos), así un proveedor nuevo no toca la UI.
- **Motor local**: `EngineProtocol` (`start`, `play(board, limit) -> Move`, `stop`). `UciEngine(path)` ya cubre cualquier motor UCI (Stockfish, Leela, Komodo…); Stockfish es un preset. Un motor que no hable UCI (modelo propio, servicio) implementa el Protocol.
- **Fuente de cámara**: `FrameSource` registrada por nombre; "celular", "RTSP", etc. se agregan sin tocar el pipeline.
- **Modo de juego**: subclase de `GameMode` registrada; expone su configuración como dataclass.

---

## 3. Hito 0 — Corre y levanta la UI (Etapa 0 del PLAN)

> **Modo POC** (§0.1): en las tablas de §3 a §6 la columna "Cómo se testea" es la referencia para cuando se agreguen tests. Durante el POC la verificación es `uv run chessoptic` y mirar. Se omiten: `pytest` y sus plugins, el job `smoke`, `core/registry.py`, `capture/registry.py`, `adapters/registry.py`, entry points y `settings_schema`; los proveedores del POC (seguimiento y Stockfish) se listan a mano en la UI.

### 3.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea |
|---|---|---|---|
| 0.1 | `pyproject.toml`: `uv` + `hatchling`, `requires-python >= 3.12`; runtime: `numpy`, `opencv-python-headless`, `chess`, `PySide6`, `platformdirs`; extra `dev`: `ruff`, `mypy`, `pytest`, `pytest-qt`, `pytest-asyncio`, `pytest-cov`. Script `chessoptic = "chessoptic.cli:main"`. Ruff (line-length 100, `E F I UP B SIM RUF`), mypy `strict` en `src/`, pytest `qt_api = pyside6` + markers. | `pyproject.toml`, `__init__.py`, `__main__.py`, `cli.py` | `uv sync`, `uv run chessoptic --version`, `uv run python -m chessoptic --version` |
| 0.2 | **`opencv-python-headless`, nunca `opencv-python`**: el wheel normal trae su propio Qt5 y rompe PySide6 en Linux. Comentario en el pyproject + test que importa `cv2` y `PySide6` en el mismo proceso. | `pyproject.toml`, `tests/unit/test_imports.py` | el test |
| 0.3 | `core/config.py`: `AppConfig` con defaults de UI.md (estabilidad 750 ms, idioma es), `CameraProfile`, `load/save` JSON, rutas por `platformdirs`, `CHESSOPTIC_CONFIG_DIR`. | `core/config.py` | round-trip en `tmp_path`; defaults; archivo corrupto → defaults + warning |
| 0.4 | `core/events.py`, `core/bus.py`, `core/registry.py` (registro genérico por nombre + `load_entry_points(group)`). | `core/` | publish/subscribe por tipo y por clase base; registro duplicado → error claro; entry point falso vía `importlib.metadata` monkeypatcheado |
| 0.5 | `chessoptic doctor`: Python ≥ 3.12; imports; cámaras (índices 0–5 con backend por SO: `CAP_DSHOW` Windows, `CAP_AVFOUNDATION` macOS, `CAP_V4L2` Linux; timeout por índice; en hilo); Stockfish (`which` o ruta en config, versión por `uci`/`uciok`); permisos por SO (macOS: aviso de a qué app se le da el permiso de cámara; Linux: `/dev/video*` y grupo `video`); Bluetooth: "no evaluado (proveedores online)". Salida con ✓ ✗ – y sugerencia por ítem; `--json`. | `doctor.py` | cada check es una función `-> CheckResult`; monkeypatch de `cv2.VideoCapture` y `shutil.which` |
| 0.6 | Fuentes y tema: Sora + IBM Plex Sans + Plex Mono en `assets/fonts/` con licencias; `ui/theme.py` con `Tokens` (UI.md §2) y `build_qss(tokens)`; carga de `theme.qss` del usuario **después** del default (§8.6); `QFontDatabase.addApplicationFont` con fallback. | `assets/fonts/`, `ui/theme.py`, `ui/app.py` | test `qt`: la QSS compila sin warnings; fuentes cargan o caen al fallback sin excepción; un `theme.qss` en `tmp_path` cambia un color |
| 0.7 | Ventana vacía con la forma final: `MainWindow` 380 px de ancho, alto de pantalla, mínimo 300; `QStackedWidget` con 4 placeholders; `NavBar` (4 `QToolButton` checkables); header con marca + `HealthPill` en "Iniciando"; "siempre arriba" (`Qt.WindowStaysOnTopHint`); geometría persistida. | `ui/main_window.py`, `ui/widgets/nav_bar.py`, `ui/widgets/health_pill.py` | pytest-qt offscreen: el nav cambia la página; la pill cambia texto/color por nivel; el flag se refleja en `windowFlags()` |
| 0.8 | CI: matriz `windows-latest`, `macos-latest`, `ubuntu-latest`; `astral-sh/setup-uv`; `uv sync --all-extras`; `ruff check` + `ruff format --check`; `mypy`; `pytest -m "not fixtures and not stockfish"` con `QT_QPA_PLATFORM=offscreen`; Ubuntu instala libs de Qt (§9.1). Job `smoke`: `uv tool install .`, `chessoptic doctor --json`, `chessoptic --smoke` (abre la ventana offscreen 1 s y sale 0). | `.github/workflows/ci.yml`, `--smoke` en `cli.py` | el CI |
| 0.9 | README (instalación `uv tool install` / `pipx`, `doctor`, estado) y actualización de `PLAN.md` (§1 de este doc). | `README.md`, `docs/PLAN.md` | — |

### 3.2 Aceptación

- CI verde en los tres SO con lint, tipos y tests.
- `uv tool install .` y `chessoptic` abren la ventana en Windows (a mano) y en los tres SO offscreen (`--smoke` en CI).
- `chessoptic doctor` lista cámara(s), Stockfish y permisos y explica qué falta.

### 3.3 PRs sugeridos

1. `build: project skeleton with uv, ruff, mypy, pytest and CI matrix` (0.1, 0.2, 0.8 sin smoke).
2. `feat(core): config, events, bus and registry` (0.3, 0.4).
3. `feat(doctor): environment checks per OS` (0.5).
4. `feat(ui): empty side-panel window with theme, fonts and nav` (0.6, 0.7, smoke).
5. `docs: install instructions and plan update` (0.9).

---

## 4. Hito 1 — Flujo de setup completo (Etapa 1, visión)

Es la parte del producto que decide si ChessOptic funciona con **tu** cámara, **tu** tablero y **tu** luz. Por eso el asistente no solo calibra: **verifica y diagnostica**.

### 4.1 El flujo (7 pasos; reemplaza a los 6 de UI.md §4, que se actualiza en este hito)

> Implementado con **6 pasos**: los pasos 2 (encuadre) y 3 (esquinas) de esta tabla se fusionaron en uno solo con manijas arrastrables, a pedido del autor al probarlo con la cámara real. La elección de a1 es solo posicional; el color del usuario se elige en el paso de proveedor.

| Paso | Pantalla | Qué hace el usuario | Qué hace ChessOptic | Mockup |
|---|---|---|---|---|
| 1 | Cámara | Elige una cámara de la lista (cualquiera: USB, integrada, celular que el SO vea como webcam) y ve la vista previa en vivo. **Usar esta cámara**. | Enumera dispositivos, abre el elegido, mide fps, carga el perfil guardado si existe (y ofrece saltar al paso 6). | `Inicio.dc.html` |
| 2 | Encuadre | Acomoda la cámara mirando la vista previa con una guía superpuesta (zona donde debería caer el tablero, ≥ 60 % del encuadre, los 64 centros visibles). **Continuar**. | Muestra consejos cortos (altura, luz, sin contraluz). Si la imagen está muy oscura o quemada lo dice ya. | nuevo: `Encuadre.dc.html` |
| 3 | Esquinas y a1 | Arrastra las 4 manijas sobre la imagen cruda; elige dónde está a1 (**4 opciones**, no 2: la cámara puede estar en cualquier lado). **Confirmar esquinas**. | Muestra **al lado y en vivo** la vista rectificada 8×8 para que el usuario vea el resultado mientras ajusta. | `Calibrar.dc.html` (ajustar a 4 opciones + rectificado en vivo) |
| 4 | Posición inicial | Pone las 32 piezas y saca la mano. | Cuando la imagen está estable, **autoentrena** el clasificador con las 64 etiquetas conocidas y muestra el overlay: piezas detectadas, contador Blancas/Negras x/16, confianza por casilla. | `VerificarTablero.dc.html` |
| 5 | **Chequeo de detección** | Mira la cámara con el overlay y responde: **Sí, coincide** / **No coincide**. Si no coincide, puede tocar las casillas mal detectadas para marcarlas. | Corre `SetupCheck` (§4.2) y muestra el reporte: nivel (bien / justo / insuficiente), casillas dudosas, y **una causa probable con una acción concreta** ("las casillas oscuras con piezas negras se confunden: más luz frontal o piezas más claras", "e4–h4 fuera de foco: fijá el enfoque", "sombra sobre a–c: mové la lámpara"). Botones **Reintentar**, **Volver a esquinas**, **Continuar igual** (si es "justo"). | nuevo: `ChequeoDeteccion.dc.html` |
| 6 | Prueba de jugada | Mueve e2–e4 y espera; luego vuelve el peón a e2. | Detecta `e2e4`, lo muestra grande, detecta la vuelta, mide latencia y estabilidad reales. Si no detecta en 10 s, diagnostica (mano no sale del encuadre, estabilidad muy exigente, confianza baja en e2/e4). **Listo** / **Reintentar**. | nuevo: `PruebaJugada.dc.html` |
| 7 | Proveedor | Elige con quién jugar: **Solo seguimiento** o **Stockfish local** (nivel). Los online aparecen deshabilitados con "próximamente". **Empezar**. | Guarda el perfil de cámara (esquinas, a1, clasificador, propiedades) y la config. Pasa a "En vivo". | `EsperandoCliente.dc.html` (ajustado a "Elegí proveedor") |

Se puede volver al asistente desde la pestaña Cámara ("Recalibrar") o repetir solo el chequeo ("Verificar detección").

### 4.2 `SetupCheck` (`vision/check.py`)

Entrada: el rectificado estable de la posición inicial, el clasificador recién entrenado y una ventana de 2–3 s de frames. Salida: `SetupCheckReport(level: good | fair | poor, per_square_confidence, suspicious_squares, findings: tuple[Finding(code, squares, message, action)])`. Chequeos:

- **Separabilidad**: distancia entre centroides vacía/blanca/negra por color de casilla vs. dispersión intra-clase. Baja → `low_contrast_dark_squares` / `low_contrast_light_squares`.
- **Estabilidad de la predicción**: la misma posición clasificada en 20 frames seguidos debe dar el mismo grid; si parpadea → `flicker` (autoexposición, luz pulsante, fps bajos).
- **Nitidez** por zona (varianza del Laplaciano) → `blur_region`.
- **Exposición**: histograma global y por cuadrante → `too_dark`, `too_bright`, `uneven_light` (sombra de un lado).
- **Geometría**: celdas con área proyectada muy chica (cámara muy oblicua) → `too_oblique` con la fila afectada.
- **Oclusión por altura**: en oblicua, el centro de la casilla detrás de una pieza alta puede quedar tapado. Se estima con la perspectiva y las filas 1/8 → `occlusion_risk`.

Cada `Finding` tiene un texto en español pensado para alguien que no sabe de visión. Ninguno bloquea: el usuario siempre puede **Continuar igual**; el semáforo quedará en amarillo si el nivel es `fair`.

### 4.3 Independencia del ángulo de cámara

Para que "no importe la cámara" el clasificador no asume cenital:

- Las **features son relativas a la propia casilla**: cada celda se compara con su referencia de "vacía" del mismo color de casilla, aprendida en el paso 4. La perspectiva afecta a todas las muestras por igual.
- La **región de muestreo** por celda no es un cuadrado fijo en el centro: se calcula a partir de la homografía como la zona de la casilla que queda más cerca de la cámara (en cenital coincide con el centro; en oblicua se corre hacia la base de la pieza). `squares.py` lo expone como `sample_region(square, calibration)`.
- El chequeo (§4.2) mide y avisa en lugar de prohibir. Las grabaciones de §9.3 incluyen una sesión oblicua para medir cuánto se degrada.

### 4.4 Tareas en orden

| # | Tarea | Archivos | Cómo se testea sin cámara |
|---|---|---|---|
| 1.1 | `capture/source.py`: `Frame`, `FrameSource`, `ListSource`, `ImageSequenceSource`; `capture/registry.py`. | `capture/` | unit |
| 1.2 | `capture/video.py` (`VideoFileSource(path, realtime)`), `capture/webcam.py` (`WebcamSource`, `list_cameras()`, propiedades exposición/enfoque si el backend las acepta, reconexión → `CameraStatus(disconnected)`). | `capture/` | MP4 sintético generado con `cv2.VideoWriter` en `tmp_path`; `cv2.VideoCapture` monkeypatcheado |
| 1.3 | `board/occupancy.py`: `Occupancy`, `OccupancyGrid`, `from_board`, `diff`, `counts`. | `board/occupancy.py` | unit puro |
| 1.4 | `tests/helpers/synthetic_board.py` y `scripted.py` (§2.6), con `with_perspective()` que devuelve las esquinas verdaderas. | `tests/helpers/` | se prueba a sí mismo (32 discos en `startpos`; warp recupera la imagen) |
| 1.5 | `vision/calibration.py` (`Calibration`, `homography`, `warp` 512×512, `load/save` en el perfil) y `vision/squares.py` (`square_rect`, `sample_region`, 4 orientaciones de a1). | `vision/` | warp de sintético con perspectiva ≈ plano; `A1` cae en la esquina correcta en las 4 orientaciones; round-trip JSON |
| 1.6 | `vision/features.py`: por celda sobre `sample_region`: media/desvío en Lab, energía de bordes, diferencia contra la referencia de vacía del mismo color. ~8 floats normalizados. | `vision/features.py` | sintético: clases separables; invariante a brillo ±30 % |
| 1.7 | `vision/occupancy.py`: `OccupancyClassifier` en numpy (centroides por clase y color de casilla, normalización por feature); `fit_initial`, `predict -> (grid, confidence)`, `refine` tras cada posición confirmada, `diagnose()` (separabilidad por clase para `SetupCheck`), serialización al perfil. | `vision/occupancy.py` | sintético: fit en `startpos`, predict en 50 FEN aleatorios ≥ 99 % de celdas; con ruido y brillo ≥ 98 %; sin perspectiva y con perspectiva de 45° |
| 1.8 | `vision/stability.py`: `StabilityDetector(window_ms, threshold)`; `motion`, `hand`, `stable`. | `vision/stability.py` | guionado con `hand=True` en el medio |
| 1.9 | `vision/check.py`: `SetupCheck` (§4.2). | `vision/check.py` | sintético con cada defecto inyectado (bajo contraste, blur en una región, brillo desparejo, perspectiva extrema) → el `Finding` esperado y ninguno de más en el caso limpio |
| 1.10 | `vision/pipeline.py`: `VisionPipeline(source, calibration, classifier, stability, analysis_fps=12)`; `run()` en hilo, `run_sync()` para tests y `replay`; `CameraStatus`, `BoardStatus`, rectificado para la UI. | `vision/pipeline.py` | `run_sync` sobre `ListSource` guionado → secuencia esperada de `OccupancyFrame` estables |
| 1.11 | CLI: `chessoptic replay <manifest | video> [--corners] [--a1] [--show]` (jugadas detectadas vs. esperadas, falsos positivos, confianza; **banco de pruebas** de cada grabación); `chessoptic calibrate --video <clip> --frame N --out corners.json` (editor de esquinas Qt sobre un frame); `chessoptic check --video <clip>` (corre `SetupCheck` sobre una grabación). | `cli.py` | `replay` sobre MP4 sintético; `calibrate` con pytest-qt |
| 1.12 | UI del asistente: `WizardView` con `Stepper` de 7 pasos; `CornerEditor` (`QGraphicsView`, 4 manijas arrastrables, polígono) con rectificado en vivo al lado; `CameraView` (§8.5); `ConfidenceGrid`; `SetupCheckView` (reporte + acciones); `MoveTestView`; selector de proveedor armado desde el registro. `CoreBridge`, `Controller`, pestaña **Cámara**. | `ui/` | pytest-qt alimentando el `CoreBridge` con snapshots falsos (§8.8); el editor de esquinas con `qtbot.mouse*` |
| 1.13 | `docs/SETUP.md` (guía para usuarios: altura, luz, encuadre, qué significa cada hallazgo del chequeo) y `docs/FIXTURES.md`; actualizar `UI.md` §4 con los 7 pasos y las 3 pantallas nuevas; agregar los 3 mockups a `docs/design/` y al canvas. | `docs/` | — |
| 1.14 | Grabaciones reales (§9.3), manifests, `tests/fixtures_real/test_manifests.py` parametrizado y salteable. | `tests/` | `pytest -m fixtures` local |

### 4.5 Aceptación

- Con una cámara cualquiera y el tablero del autor, el asistente completo lleva de "sin configurar" a "Listo" sin tocar un archivo; el paso 5 reporta `good` o explica qué cambiar; el paso 6 detecta e2–e4 y la vuelta.
- Al reabrir con la misma cámara, no pide recalibrar; con otra cámara, arranca el asistente.
- `chessoptic replay` sobre las grabaciones de posición inicial y jugadas sueltas (§9.3) da las jugadas esperadas y 0 falsos positivos.
- Tests `unit` + `qt` verdes en CI; `fixtures` verdes localmente.

### 4.6 PRs sugeridos

1. `feat(capture): frame sources for webcam, video and image lists` (1.1, 1.2).
2. `feat(vision): calibration, warp and synthetic board helpers` (1.3, 1.4, 1.5).
3. `feat(vision): occupancy classifier trained from the initial position` (1.6, 1.7).
4. `feat(vision): stability detector, setup check and pipeline` (1.8, 1.9, 1.10).
5. `feat(cli): replay, calibrate and check commands` (1.11).
6. `feat(ui): setup wizard with corner editor, detection check and move test` (1.12, partible en 2–3).
7. `docs: setup guide, fixtures guide and UI spec update` (1.13).
8. `test: real board recordings and manifests` (1.14).

---

## 5. Hito 2 — Estados sobre la UI y modo "solo seguimiento" (Etapa 1, BoardModel + UI)

### 5.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea sin cámara |
|---|---|---|---|
| 2.1 | `board/model.py`: `BoardModel` con `expected_occupancy()`, `verify_initial(grid)`, `resolve(grid) -> NoChange | Move | Ambiguous | Transient | Mismatch`. Algoritmo: igual → `NoChange`; coincide con `board.after(m)` para una sola jugada legal del bando que mueve → `Move`; varias (promoción) → `Ambiguous`; las celdas cambiadas son subconjunto del cambio de alguna legal → `Transient`; si no → `Mismatch`. `both_sides=True` para solo seguimiento. `push`, `set_board(fen)`. | `board/model.py` | unit exhaustivo sin imágenes: simple, captura, O-O, O-O-O, al paso, promoción (4 candidatos), transitorios, mismatches, both_sides |
| 2.2 | `board/tracker.py`: `BoardTracker(model, mismatch_grace_ms=2000)`: solo frames `stable`; `Transient` espera; `Move` → `MoveDetected`; `Ambiguous` → `MoveAmbiguous`; `Mismatch` sostenido → `PositionMismatch` (+ frame guardado si está activado); `verify_target(board_after)` para "Reproducí la jugada". | `board/tracker.py` | secuencias de grids → eventos; el grace evita falsos `Mismatch` en un enroque lento |
| 2.3 | `game/modes.py`: `GameMode` (Strategy) con `FreePlay` (sin reloj; `clock_source = None`; fin solo por mate/tablas/abandono). La interfaz deja lugar a `on_turn_start/on_turn_end`, `clock_snapshot()`, `on_flag()` para los modos con reloj de §7. | `game/modes.py` | unit |
| 2.4 | `game/session.py` + `docs/STATES.md`: estados de §8.4 como clases (State). Entradas: `BoardEvent`, `AdapterEvent`, acciones (`resync`, `pause`, `new_game`, `set_promotion`, `end_game`). Salidas: `DriverState`, `GameInfo`, `PendingOpponentMove`, resaltados, `LogEntry`. | `game/session.py`, `docs/STATES.md` | cada transición de STATES.md es un test; partida completa con fakes |
| 2.5 | `adapters/base.py` (`OutputAdapter`, `AdapterInfo`, `AdapterStatus`, `AdapterRunner`), `adapters/registry.py`, `adapters/tracking.py` (`TrackingAdapter`: acepta toda jugada legal de ambos bandos, nunca propone jugadas; `GameStarted` al detectar la primera jugada desde la posición inicial; fin manual o por mate). | `adapters/` | unit con `FakeAdapter`; registro con entry point falso |
| 2.6 | `core/health.py` (`HealthAggregator`, reglas de §8.4) y `core/runtime.py` (`CoreRuntime`: arma todo, `start/stop`, usado por CLI, UI y tests). | `core/` | tabla de combinaciones → nivel/texto; `run_sync` de punta a punta sobre una partida sintética → lista SAN esperada |
| 2.7 | `game/pgn.py`: exportar con cabeceras; guardado de frames de error. | `game/pgn.py`, `board/tracker.py` | PGN re-parseable; `tmp_path` |
| 2.8 | UI: `LiveView` completa (`HealthStrip`, `StateBlock` con todas las variantes de §8.3, `CameraView`, `MovesList`), `Log` con filtros y exportar, `Ajustes` (proveedor y su formulario desde `settings_schema`, detección, ventana, diagnóstico), modo compacto, sonido en errores. | `ui/` | snapshots por `DriverState`: texto, color de fondo/borde, botones |

### 5.2 Aceptación

- En modo solo seguimiento, una partida jugada a mano con ambos bandos se sigue completa, el log y el PGN coinciden con lo jugado, y "Posición no coincide" aparece y se resuelve al corregir las piezas.
- Todas las transiciones de `docs/STATES.md` tienen test; todas las variantes de `StateBlock` tienen test `qt`.
- `chessoptic replay` reconstruye la partida completa grabada (§9.3) sin errores; en vivo ≤ 1 falsa detección cada 50 jugadas con luz normal.

### 5.3 PRs sugeridos

1. `feat(board): board model with legal-move inference and tracker` (2.1, 2.2).
2. `feat(game): game modes, session state machine and STATES.md` (2.3, 2.4).
3. `feat(adapters): adapter protocol, registry and tracking-only adapter` (2.5).
4. `feat(core): health aggregation and runtime facade` (2.6, 2.7).
5. `feat(ui): live view states, log, settings and compact mode` (2.8, partible).

---

## 6. Hito 3 — Partida contra Stockfish sin reloj (Etapa 2 del PLAN)

### 6.1 Tareas en orden

| # | Tarea | Archivos | Cómo se testea sin cámara |
|---|---|---|---|
| 3.1 | `adapters/local/engine.py`: `EngineProtocol` y `UciEngine(path, options)` sobre `chess.engine` asíncrono (`popen_uci`), con `ScriptedEngine` y `RandomEngine` para tests. | `adapters/local/engine.py` | unit con fakes; `@stockfish` con el binario real (CI Ubuntu lo instala con apt; se saltea donde no está) |
| 3.2 | `adapters/local/stockfish.py`: `StockfishAdapter(engine, my_color, level 1–8 → `Skill Level` + tiempo por jugada)`; `settings_schema` (ruta, nivel, color); emite `LinkStatus(connected, "Stockfish 17")`, `GameStarted(mode=FreePlay)`, `MoveAccepted` (valida legalidad), `OpponentMove`, `GameOver`. Sin `ClockUpdate` en `FreePlay`. | `adapters/local/stockfish.py` | partida guionada completa con `ScriptedEngine` |
| 3.3 | Promoción en el MVP: si `MoveAmbiguous`, la sesión pasa a `Promotion` y la UI muestra 4 botones (D, T, A, C). Default configurable en Ajustes ("preguntar" / "siempre dama"). Es lo mínimo para que una partida no se trabe; el tema de piezas físicas extra queda para después. | `game/session.py`, `ui/widgets/state_block.py` | unit + qt |
| 3.4 | `doctor` y Ajustes: ruta a Stockfish a mano si no está en PATH; "Probar motor". | `doctor.py`, `ui/views/settings.py` | monkeypatch |
| 3.5 | `docs/EXTENDING.md`: cómo agregar proveedor, motor, fuente de cámara y modo; ejemplo mínimo de cada uno. | `docs/EXTENDING.md` | — |
| 3.6 | Test de punta a punta sin cámara: `tests/unit/test_full_game_stockfish.py` juega una partida guionada con `ScriptedEngine` + `ListSource` sintético y verifica estados, log y PGN. | `tests/` | el test |

### 6.2 Aceptación

- Partida completa contra Stockfish solo con piezas físicas: mis jugadas se detectan y se envían, las suyas se muestran grandes y se verifican al reproducirlas, el fin de partida lleva a "Reordená el tablero" y vuelve a listo.
- Un proveedor de ejemplo (`RandomEngine` empaquetado como plugin en `tests/plugin_example/`) aparece en el selector sin tocar código de la UI.

### 6.3 PRs sugeridos

1. `feat(adapters): UCI engine protocol and Stockfish provider` (3.1, 3.2).
2. `feat(game): promotion handling for providers without piece recognition` (3.3).
3. `feat(doctor): engine path and test button` (3.4).
4. `docs: extending guide and end-to-end game test` (3.5, 3.6).

---

## 7. Después del MVP (planteado, no detallado)

En orden tentativo; cada punto se detalla en este documento cuando se acerque.

| Etapa | Qué | Depende de |
|---|---|---|
| **Modos con reloj** | `TimedMode(base, increment)` con presets (bullet, blitz, rápida) y los que alguien quiera agregar; `ClockUpdate` medido por el driver; qué pasa al caer la bandera. Reloj visible en el bloque de turno. | H3 |
| **Proveedores online — investigación** | Entender Chessconnect de verdad (PLAN §4.1–4.3): transporte por SO, qué tablero emular, primer contacto con el autor. Y en paralelo, qué ofrece la Board API de Lichess. Resultado: decidir cuál se implementa primero. | H3 |
| **Lichess** | `adapters/online/lichess.py` con la Board API (streams ndjson, jugadas, relojes del cliente, fin), token `board:play` en Ajustes (dónde guardarlo), promoción en UCI, partida en curso al abrir. Lo que había en la primera versión de este doc se recupera del historial de git cuando toque. | investigación |
| **chess.com vía Chessconnect** | PoC de transporte (serie virtual / BLE), protocolo del tablero emulado, respuestas a PLAN §4.3. | investigación |
| **Cámaras** | Celular como cámara (apps y Continuity Camera), fuentes RTSP, mejoras en la carga/enumeración, calibración automática de esquinas. | H1 |
| **Promoción con piezas** | Qué hacer cuando el usuario tiene (o no) damas extra; configuración "cómo represento una promoción en el tablero físico". | H3 |
| **Detector de piezas (PLAN Etapa 5)** | Arrancar desde cualquier posición, resincronización automática. | grabaciones reales abundantes |
| **Instaladores (PLAN Etapa 6)** | PyInstaller/Briefcase, descarga asistida de Stockfish, idioma inglés. | todo lo anterior |

---

## 8. Mapeo UI → PySide6 y eventos del núcleo

### 8.1 Arquitectura del paquete `ui/`

- `CoreBridge(QObject)`: una `Signal(object)` por snapshot: `health_changed`, `driver_state_changed`, `game_info_changed`, `occupancy_changed`, `pending_move_changed`, `frame_ready(QImage)`, `log_entry`, `cameras_changed`, `calibration_changed`, `setup_check_changed`, `diagnostics_changed`.
- `Controller`: métodos síncronos que la UI llama (`select_camera`, `set_camera_prop`, `set_corners`, `set_a1`, `confirm_calibration`, `run_setup_check`, `start_move_test`, `select_provider(name, settings)`, `start_game`, `end_game`, `resync`, `pause`, `resume`, `set_promotion`, `export_pgn`, `export_log`, `toggle_always_on_top`, `toggle_compact`, `update_config`). Cada uno despacha al hilo del núcleo.
- Las vistas **solo** leen snapshots y llaman al `Controller`. Nada de `chess` ni `cv2` en `ui/` salvo la conversión `np.ndarray → QImage` en `bridge.py`.

### 8.2 Shell (`main_window.py`)

| Elemento de UI.md | Widget |
|---|---|
| Ventana 380 × alto, redimensionable, mínimo 300 | `QMainWindow`, `setMinimumWidth(300)`, geometría persistida |
| Siempre arriba | `Qt.WindowStaysOnTopHint`, re-`show()` al cambiar |
| Modo compacto 380 × 260 | `QStackedWidget` raíz con `FullShell` y `CompactView` |
| Header: marca + pill | `QWidget#header` con `QLabel` (ícono SVG + "ChessOptic" en Sora 600) y `HealthPill` |
| Nav inferior 4 pestañas | `NavBar` con 4 `QToolButton` checkables en `QButtonGroup`; oculto durante el asistente |
| Pestañas | `QStackedWidget` central: `LiveView`, `CameraTab`, `LogTab`, `SettingsTab`, `WizardView` |

### 8.3 Pantallas y estados → widgets → eventos → acciones

**Asistente** (`views/wizard/`): un `QWizard`-like propio (`WizardView` con `Stepper` y `QStackedWidget`), una página por paso de §4.1.

| Paso | Página | Widgets | Consume | Acciones |
|---|---|---|---|---|
| 1 Cámara | `CameraStep` (`Inicio.dc.html`) | checklist de 4 `StepRow`, `QComboBox` de cámaras, `CameraView` cruda, **Usar esta cámara**, ayuda `doctor` | `cameras_changed`, `CameraStatus`, `frame_ready` | `select_camera` |
| 2 Encuadre | `FramingStep` (nuevo) | `CameraView` cruda con guía, 3 consejos, aviso de exposición | `frame_ready`, `BoardStatus` | siguiente |
| 3 Esquinas | `CornersStep` (`Calibrar.dc.html`) | `CornerEditor` + `CameraView` rectificada en vivo, 4 chips de esquina, 4 `QRadioButton` de a1, **Atrás** / **Confirmar esquinas** | `frame_ready`, `calibration_changed` | `set_corners`, `set_a1`, `confirm_calibration` |
| 4 Posición inicial | `InitialPositionStep` (`VerificarTablero.dc.html`) | contadores x/16, texto de faltantes, `CameraView` con faltantes en `#F3D3A1`, `ConfidenceGrid` | `InitialPositionCheck`, `OccupancyView` | `recalibrate` |
| 5 Chequeo | `DetectionCheckStep` (nuevo) | `CameraView` con overlay, pregunta "¿Coincide con tu tablero?" + **Sí** / **No**, `SetupCheckReportView` (nivel con color + ícono, lista de hallazgos con acción), **Reintentar** / **Volver a esquinas** / **Continuar igual** | `SetupCheckReport`, `OccupancyView` | `run_setup_check`, marcar casillas |
| 6 Prueba | `MoveTestStep` (nuevo) | instrucción "Mové e2–e4", SAN grande al detectar, latencia medida, **Listo** / **Reintentar** | `MoveDetected`, `Diagnostics` | `start_move_test` |
| 7 Proveedor | `ProviderStep` (`EsperandoCliente.dc.html` ajustado) | `QComboBox` de proveedores desde el registro (online deshabilitados: "próximamente"), formulario generado desde `settings_schema`, **Empezar** | registro, `AppConfig` | `select_provider`, `start_game` |

**Vista "En vivo"** (`views/live.py`): `HealthStrip` → `StateBlock` → `CameraView` → `MovesList`.

| Pantalla (UI.md) | `DriverState.state` | `StateBlock` variante y estilo | Consume | Acciones |
|---|---|---|---|---|
| Tu turno (`Main`) | `InGame.MyTurn` | `MyTurnBlock`: fondo `turn`, "Tu turno", color propio + proveedor, última jugada del rival; relojes **solo si el modo los tiene** (en `FreePlay` no se muestran) | `GameInfo`, `OccupancyView` (destino en `#8EC4EA`) | — |
| Moviendo | `InGame.Moving` | `MyTurnBlock` + indicador de actividad | `HandDetected` | — |
| Turno del rival (`TurnoRival`) | `InGame.OpponentTurn` | `OpponentTurnBlock`: borde `line-strong` 2 px, "Turno del rival · Pensando…" (Stockfish) / "Esperando…" (online), "Tu jugada: X · aceptada" | `GameInfo` | — |
| Reproducí la jugada (`Reproducir`) | `InGame.Replay` | `ReplayBlock`: borde `brand-light` 3 px, SAN grande en Plex Mono, frase humana | `PendingOpponentMove`, `OccupancyView` (origen/destino) | — |
| Verificando | `InGame.Verifying` | `ReplayBlock` con actividad hasta `PositionMatched` | igual | — |
| Promoción | `InGame.Promotion` | `PromotionBlock`: "Elegí la pieza" + 4 botones | `MoveAmbiguous` | `set_promotion` |
| Posición no coincide (`NoCoincide`) | `InGame.Mismatch` | `MismatchBlock`: borde `err`, lista de `SquareIssue` en texto humano, **Resincronizar** / **Ver frame** | `PositionMismatch`, `OccupancyView` (`#F0AFA9`), `LogEntry.frame_path` | `resync`, abrir frame |
| Enlace perdido (`EnlacePerdido`) | `InGame.LinkLost` | `LinkLostCard` (`err-bg`), **Reconectar** / **Ver detalle**; fila compacta de turno | `LinkStatus(lost)` | `reconnect` (online; en local = "motor se cerró → Reiniciar") |
| Fin de partida (`FinPartida`) | `InGame.GameOver` → `Standby.VerifyingBoard` | `GameOverCard` (resultado, resumen, **Exportar PGN** / **Ver log**) + `ResetBoardCard` (x/32) | `GameOver`, `GameInfo`, `InitialPositionCheck` | `export_pgn` |
| Listo (`Conectado`) | `Standby.Ready` | `ReadyBlock`: "Listo para jugar" + instrucción según proveedor ("Hacé tu primera jugada" en Stockfish/seguimiento; "Abrí una partida en …" en online) | `LinkStatus`, `OccupancyView` | `start_game` |
| Verificar tablero (fuera del asistente) | `Standby.VerifyingBoard` | igual que el paso 4 | igual | `recalibrate` |
| Modo compacto (`Compacto`) | cualquiera | `CompactView`: pill corta + expandir, bloque reducido, miniatura | los mismos snapshots | `toggle_compact` |

**Otras pestañas**

| Pestaña | Widgets | Datos / acciones |
|---|---|---|
| Cámara (`views/camera.py`) | `QComboBox` dispositivo; `QSlider` exposición/enfoque (deshabilitados con tooltip si el backend no responde); **Recalibrar**; **Verificar detección** (repite el paso 5); cruda/rectificada; `CameraView` grande; `ConfidenceGrid` | `frame_ready`, `OccupancyView.confidence`, `CameraStatus` → `select_camera`, `set_camera_prop`, `recalibrate`, `run_setup_check` |
| Log (`views/log.py`) | filtros (Todo / Jugadas / Eventos / Errores · N); `QListView` con `LogModel(QAbstractListModel)` y delegate; **Exportar PGN** / **Exportar log** | `log_entry` → `export_pgn`, `export_log`, abrir frame |
| Ajustes (`views/settings.py`) | Grupos: **Proveedor** (`QComboBox` + formulario desde `settings_schema`), **Modo de juego** (solo `FreePlay` en MVP), **Detección** (estabilidad 250–2000 ms, guardar frames), **Ventana** (siempre arriba, compacto en partida, sonido, idioma), **Apariencia** (abrir `theme.qss`, recargar), **Diagnóstico** (fps, latencia, protocolo) | `AppConfig` ↔ `update_config`; `Diagnostics` |

### 8.4 Estados y reglas del semáforo

Estados: `Standby`: `Starting`, `Uncalibrated`, `VerifyingBoard`, `Ready`, `Paused`. `InGame`: `MyTurn`, `Moving`, `OpponentTurn`, `Replay`, `Verifying`, `Promotion`, `Mismatch`, `LinkLost`, `GameOver`. (`WaitingClient`/`ConnectedIdle` del PLAN quedan para los proveedores online; en local `Ready` los cubre.)

`HealthAggregator`, en orden de prioridad:

| Condición | Nivel | Pill |
|---|---|---|
| `Paused` o sin cámara elegida | `idle` | "Pausado" / "Iniciando" |
| Sin calibración o setup incompleto | `idle` | "Sin calibrar" |
| Cámara `disconnected` / `no_permission` | `err` | "Sin cámara" |
| Enlace `lost` en partida (online) o motor caído | `err` | "Enlace perdido" / "Motor detenido" |
| Tablero `occluded` > 3 s en partida o `moved` | `err` | "Tablero perdido" |
| Chequeo de setup `fair`, `low_confidence`, `Mismatch`, `VerifyingBoard` incompleto | `warn` | "Revisar tablero" / "Tablero incompleto" |
| Cámara `low_fps` (< 6 fps de análisis) | `warn` | "Cámara lenta" |
| Proveedor online anunciando/esperando | `warn` | "Esperando cliente" |
| Todo bien | `ok` | "Driver OK" |

El turno **nunca** cambia el semáforo: azul = mi turno, borde = rival.

### 8.5 `CameraView`

`QWidget` con `paintEvent`: `QImage` rectificado escalado (cuadrado), celdas, círculos por ocupación (blanco con borde `line-strong` / `ink`), resaltados (`origin` `#F3D3A1`, `destination` `#8EC4EA`, `error` `#F0AFA9`, `missing` `#F3D3A1`), coordenadas según `a1_corner`, etiqueta superior. Recibe `frame_ready` y `occupancy_changed` por separado; repinta a ≤ 15 fps (`QTimer` de coalescencia). Modo "cruda" con cuadrilátero y guía de encuadre. La conversión `np.ndarray → QImage` copia la memoria.

### 8.6 Estilos: QSS y override del usuario

- Qt usa **QSS**, una sintaxis tipo CSS (selectores por clase de widget, `#objectName`, `[propiedad="valor"]`, pseudo-estados `:hover`, `:checked`). No es CSS completo (sin flexbox, sin variables), por eso los **tokens viven en `theme.py`** y `build_qss(tokens)` los inyecta en una plantilla.
- Cada widget tiene `objectName` estable y propiedades dinámicas (`level`, `variant`) documentadas en `docs/UI.md`, para que la QSS pueda apuntarles.
- **Override del usuario**: si existe `theme.qss` en la carpeta de configuración, se carga **después** del default y gana. Ajustes → Apariencia tiene "Abrir theme.qss" y "Recargar". Así se puede retocar colores, bordes y tamaños sin tocar código.
- Lo que QSS no puede (dibujo del overlay, círculos, resaltados) toma los colores de `Tokens` para que el override también los afecte si redefine tokens en un bloque `/* tokens */` que `theme.py` parsea.

### 8.7 Idioma

Textos por `self.tr()` desde el primer widget; `.ts` para `es` y `en` con `pyside6-lupdate`. La v1 se publica en español; el inglés se agrega con los instaladores (§7).

### 8.8 Tests de UI (pytest-qt, offscreen)

Fixture `bridge` (un `CoreBridge` sin núcleo) y `window(qtbot, bridge)`. Por cada estado: emitir snapshots falsos, verificar `property("variant")`, textos, botones, color de la pill. `CornerEditor`: arrastre con `qtbot.mouse*` y coordenadas en píxeles de imagen. `CameraView`: render a `QPixmap` y comparación con tolerancia solo en Linux.

---

## 9. Para hacer en casa

Checklist en orden. ★ = bloqueante para el hito.

### 9.0 Resumen

| Antes de | Qué |
|---|---|
| H0 | ★ uv + Python 3.12, ★ Git, bajar fuentes, Stockfish (lo chequea `doctor`, no bloquea H0) |
| H1 | ★ cámara con soporte fijo, ★ tu tablero y piezas, ★ grabar el set corto de grabaciones (§9.3) |
| H2 | nada nuevo (la partida completa grabada ya está en §9.3) |
| H3 | ★ Stockfish en PATH o ruta conocida |
| Después | investigación de Chessconnect; cuentas y tokens cuando se decida el primer proveedor online |

### 9.1 Antes de H0: instalar

**Todos los SO**

| Qué | Cómo |
|---|---|
| `uv` (trae Python) | Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` · macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` · después `uv python install 3.12` |
| Fuentes (solo bajar, se empaquetan en `assets/fonts/`) | Sora: https://fonts.google.com/specimen/Sora (TTF estáticos 400/600/700) · IBM Plex Sans y Plex Mono: https://github.com/IBM/plex/releases (TTF 400/600). Guardar los `OFL.txt`. |
| Stockfish | Windows: https://stockfishchess.org/download/ → zip "Windows x86-64 AVX2", descomprimir y sumar la carpeta al PATH (o anotar la ruta para Ajustes) · macOS: `brew install stockfish` · Debian/Ubuntu: `sudo apt install stockfish` |

**Windows 11 (base)**: nada más. Si la cámara no abre con `doctor`: Configuración → Privacidad → Cámara → permitir apps de escritorio.

**macOS** (cuando haya una para probar): `xcode-select --install`. El permiso de cámara se le pide a la app que lanza el proceso (Terminal, VS Code).

**Linux (Debian/Ubuntu)**:

```bash
sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libegl1 libgl1 libdbus-1-3 \
  libfontconfig1 v4l-utils
sudo usermod -aG video "$USER"   # cerrar sesión y volver a entrar
```

**No hace falta para el MVP**: Git LFS, librerías BLE, com0com, `socat`, extensión Chessconnect, cuenta de Lichess. **Modelos o pesos: ninguno.** El clasificador se entrena solo con la posición inicial y Stockfish trae su red embebida.

### 9.2 Antes de H1: cámara, tablero, luz

No hay requisitos duros: el chequeo de detección (§4.2) te va a decir si tu combinación funciona. Lo que ayuda:

- **Cámara fija**: brazo articulado con clamp al escritorio o trípode. Si se mueve entre la calibración y la partida, hay que recalibrar. Si tu Logitech permite fijar enfoque y exposición, mejor (el autoenfoque "respirando" es la primera causa de falsos positivos; la pestaña Cámara intenta fijarlo).
- **Encuadre**: que el tablero ocupe ≥ 60 % de la imagen y se vean los 64 centros. Cenital es lo más fácil; oblicua funciona si no es muy baja (el chequeo avisa).
- **Luz**: pareja, sin ventana de fondo ni lámpara puntual que tire sombras largas. Que no cambie durante la partida.
- **Tablero y piezas**: cuanto más contraste entre piezas y casillas, mejor. Mate mejor que brillante. Si el chequeo da "insuficiente" y la causa es contraste, ahí sí conviene cambiar piezas o tablero.

### 9.3 Antes de H1: grabaciones de prueba (set corto)

Por qué (ver §2.6): son los tests de la visión con imágenes reales. Sin ellas, cada cambio al clasificador se prueba sentado frente a la cámara.

Reglas: cámara **fija** en toda la sesión; MP4 720p 30 fps; enfoque y exposición fijos si se puede; cada sesión arranca con 10 s de posición inicial sin manos; entre jugadas sacar la mano y esperar ≥ 1 s; jugar ambos bandos y anotar. Nombrar `tests/fixtures/<sesion>_<clip>/video.mp4`; el `manifest.json` lo armamos juntos con `chessoptic calibrate`.

| Clip | Duración | Contenido | Para qué |
|---|---|---|---|
| `s1_initial` | 10–15 s | Posición inicial sin manos | calibración, entrenamiento, 32/32, `SetupCheck` |
| `s1_missing` | 30 s | Inicial con 1 pieza faltante (d1), luego 2 (d1 y g8), luego una blanca en casilla equivocada; 5 s entre cambios | "Verificar tablero" |
| `s1_move_test` | 20 s | e2–e4, pausa, e4–e2 | paso 6 del asistente |
| `s1_scholar` | 1–2 min | `1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7#` | primer test de punta a punta |
| `s1_en_passant` | 30 s | `1. e4 Nf6 2. e5 d5 3. exd6` | captura al paso |
| `s1_castle_short` | 45 s | `1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. O-O Nf6 5. d3 O-O` | enroque corto; rey primero, torre después |
| `s1_castle_long` | 45 s | `1. d4 d5 2. Nc3 Nc6 3. Bf4 Bf5 4. Qd2 Qd7 5. O-O-O O-O-O` | enroque largo |
| `s1_promotion` | 45 s | `1. a4 b5 2. axb5 a6 3. bxa6 Nf6 4. a7 Nd5 5. axb8=Q` (coronar con cualquier pieza blanca que tengas a mano) | promoción con captura → `Ambiguous` |
| `s1_hands` | 2–3 min | Partida corta "sucia": mano que duda, pieza levantada y devuelta, pieza ajustada sin mover, jugada hecha y deshecha, brazo cruzando | estabilidad, transitorios, falsos positivos |
| `s1_game_full` | 10–15 min | Partida completa de 25–40 jugadas a ritmo normal con captura, enroque y final | aceptación de H2 |
| `s1_reset` | 1 min | De una posición final a la inicial | progreso x/32 |
| `s2_light_*` | 15 s × 3 | Inicial con luz de día / lámpara / sombra parcial | umbral de "baja confianza" y hallazgos del chequeo |
| `s3_oblique` (opcional) | `initial` + `scholar` | Cámara a ~45° desde el lado del rival | medir degradación fuera del cenital |

Total: ~20–25 min de video, **~150–300 MB**. Quedan en tu máquina; los manifests sí van al repo.

### 9.4 Antes de H3

- `chessoptic doctor` tiene que marcar Stockfish ✓ (o tener la ruta para Ajustes).

### 9.5 Cómo validar lo preparado

| Hito | Chequeo |
|---|---|
| H0 | `uv --version`; `stockfish` responde `uciok` a `uci`; carpeta con 7–8 TTF + licencias |
| H1 | `chessoptic doctor` ve la cámara; los clips abren en VLC; cada clip tiene su `manifest.json` con `expected_moves` |
| H3 | `chessoptic doctor` marca Stockfish ✓ |

---

## 10. Riesgos y pendientes

### 10.1 Riesgos técnicos (además de PLAN §7)

| Riesgo | Impacto | Mitigación |
|---|---|---|
| `opencv-python` y PySide6 pelean por Qt en Linux | la app no abre | `opencv-python-headless` (0.2) + test de imports |
| Oclusión con cámara oblicua baja | la casilla detrás de una pieza alta se clasifica mal | `sample_region` según perspectiva (§4.3), `occlusion_risk` en el chequeo, sesión oblicua de grabaciones para medir |
| Autoenfoque / autoexposición | falsos positivos y baja confianza | fijar desde la pestaña Cámara cuando el backend lo permite; `flicker` en el chequeo; `docs/SETUP.md` |
| Enumeración lenta de cámaras en Windows (MSMF) | `doctor` y el asistente tardan | `CAP_DSHOW` primero, timeout por índice, en hilo |
| Promoción sin reconocer piezas | ambigüedad entre 4 jugadas | `Promotion` con 4 botones + default; piezas físicas extra: después |
| Un proveedor externo mal hecho rompe la app | excepción en el loop del núcleo | `AdapterRunner` aísla excepciones por adaptador y emite `AdapterError`; el registro valida `AdapterInfo` al cargar |
| Rendimiento en equipos modestos | latencia detección → UI | análisis a 10–15 fps, rectificado 512×512, numpy vectorizado; diagnóstico visible |
| Posición "rara" sin jugada legal (pieza que rueda) | mismatch falso | grace de 2 s; "Resincronizar" siempre disponible |
| Grabaciones de prueba solo en la máquina del autor | otro colaborador o CI no puede correr `fixtures` | sintético cubre CI; alojamiento se decide cuando haya un segundo colaborador (§10.2) |

### 10.2 Pendientes (no bloquean el MVP)

1. **Alojamiento de las grabaciones reales** cuando haya que compartirlas: Git LFS (cuota gratis chica) vs. assets de GitHub Releases + script de descarga. Hoy quedan locales.
2. **Proveedores online**: cuál primero (Lichess directo vs. chess.com vía Chessconnect), después de la investigación de §7. Incluye dónde guardar tokens, promoción en UCI y retomar partidas en curso.
3. **Modos con reloj**: qué presets y qué pasa al caer la bandera; si Stockfish debería "pensar" con límite de tiempo acorde al modo.
4. **Promoción física**: configuración "tengo damas extra / uso torre invertida / otra".
5. **Inglés**: cuándo se traduce.
6. **Mockups nuevos**: Encuadre, Chequeo de detección y Prueba de jugada no están dibujados; se agregan al canvas y a `docs/design/` en H1 antes de implementar la UI del asistente.
7. **`PLAN.md`**: aplicar los cambios de §1 en el PR de H0.
