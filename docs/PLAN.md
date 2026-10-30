# ChessOptic — Plan del proyecto

> Documento de contexto y planificación para quien trabaje en el repo (personas o agentes como Claude Code).
> Resume las decisiones tomadas en la etapa de diseño. Si algo acá contradice al código, actualizá este documento en el mismo PR.

---

## 1. Qué es ChessOptic

**ChessOptic es un tablero electrónico de ajedrez cuyo sensor es una webcam.**

Ponés un tablero de madera común frente al monitor, apuntás la cámara y ChessOptic se comporta como un tablero electrónico (tipo DGT o Chessnut): detecta las jugadas que hacés con las piezas reales y las entrega a la plataforma donde estás jugando (Lichess, chess.com, etc.).

No es una app de ajedrez. **Es el driver de un tablero virtual.** El ajedrez se ve y se juega en la plataforma; ChessOptic solo:

1. Ve el tablero físico.
2. Sabe qué pieza hay en cada casilla.
3. Reporta los cambios por una salida (adaptador) hacia la plataforma.
4. Muestra un panel de diagnóstico para que sepas, de reojo, que todo funciona.

### Uso típico

```
┌──────────────────────────────────────────┬──────────────┐
│                                          │  ChessOptic  │
│   Navegador: chess.com / lichess.org     │  (panel      │
│   (3/4 de la pantalla)                   │   lateral    │
│                                          │   ≤ 1/4)     │
│                                          │              │
└──────────────────────────────────────────┴──────────────┘
              ▲ webcam apuntando al tablero físico
```

### Principios

- **Open source** (Apache-2.0) y **multiplataforma**: Windows, macOS y Linux desde el día uno.
- **El núcleo es nuestro.** ChessOptic tiene nombre, modelo y protocolo propios. Hablar como otro tablero (para compatibilidad) es solo un adaptador de salida.
- **Todo lo de visión es testeable sin cámara** (fuentes de frames inyectables + videos grabados como fixtures).

---

## 2. Decisiones tomadas (y por qué)

| Tema | Decisión | Motivo |
|---|---|---|
| Lenguaje | **Python 3.12+** | OpenCV nativo, `python-chess`, `pyserial`, librerías BLE multiplataforma, corre en segundo plano. |
| UI | **PySide6 (Qt)** | App de escritorio real, video en vivo fluido, "siempre arriba", sin navegador de por medio. |
| Visión v1 | OpenCV: calibración + homografía + clasificador de ocupación por casilla | No requiere dataset; se autoentrena con la posición inicial. |
| Visión v2 | Modelo de reconocimiento de piezas (YOLO u otro, exportado a ONNX) | Validar tipo de pieza y recuperarse si se pierde el seguimiento. |
| Lógica de ajedrez | `python-chess` | Legalidad, SAN/UCI, FEN, PGN. |
| Motor local | Stockfish (binario del sistema o descargado) vía UCI | Modo práctica offline y banco de pruebas de la visión. |
| Distribución inicial | Paquete Python: `pipx install chessoptic` / `uv tool install chessoptic` + comando `chessoptic doctor` | Funciona en los tres SO sin instaladores; `doctor` explica qué falta. |
| Distribución v1 estable | Instaladores nativos (.exe / .dmg / AppImage) con PyInstaller o Briefcase, en GitHub Releases | Para usuarios no técnicos. |
| Proveedores (contra quién / dónde se juega) | **Adaptadores enchufables**: locales (Stockfish primero; cualquier motor UCI u otro que alguien sume por PR) y online (Lichess, chess.com vía Chessconnect, otros) | Que un tercero pueda agregar un proveedor sin tocar el núcleo ni la UI. |
| Modos de juego | **Strategy**: el modo base es sin reloj; bullet/blitz/rápidas y otros vienen después, cada uno con su configuración | Hacer andar la detección antes que el reloj. |
| Fase actual (2026-10-29) | **POC sin tests automáticos** hasta que la v1 funcione; CI solo lint + tipos. Orden e hitos en [`IMPLEMENTATION.md`](IMPLEMENTATION.md) | Ir rápido. La arquitectura (fuentes de frames inyectables, núcleo sin Qt) deja los tests posibles para después. |
| Sin backend web / sin extensión propia | Descartado | Una UI en el navegador no puede abrir puertos ni emular BLE, y automatizar el DOM de chess.com tiene riesgo de ToS. |

### Descartado y por qué (para no volver a discutirlo)

- **Extensión de Chrome propia que mueve piezas en el DOM de chess.com**: frágil y riesgosa respecto al ToS (chess.com no tiene API pública para jugar).
- **Web app React + WebSerial**: el navegador no puede crear puertos ni anunciar BLE; depende de pestañas visibles.
- **LLM local (Ollama) como rival**: juega mal y propone jugadas ilegales. Para jugar contra la PC se usa Stockfish.

---

## 3. Arquitectura

```
                 ┌─────────────────────────── ChessOptic (Python) ───────────────────────────┐
 webcam ──────►  │  capture  →  vision  →  board model  →  output adapters                 │
                 │  (frames)    (calib,     (posición     ├─ LichessAdapter   (Board API)   │──► lichess.org
                 │              ocupación,   completa,    ├─ CompatAdapter    (emula un      │──► Chessconnect ──► chess.com,
                 │              piezas)      eventos)     │                    tablero ya     │                    lichess, etc.
                 │                                        │                    soportado)     │
                 │                                        ├─ NativeAdapter    (protocolo     │──► (futuro: soporte nativo
                 │                                        │                    ChessOptic)    │     en Chessconnect u otros)
                 │                                        └─ LocalEngine      (Stockfish)    │
                 │                                                                           │
                 │  ui (PySide6): panel lateral de diagnóstico                               │
                 └───────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Módulos

```
chessoptic/
├── src/chessoptic/
│   ├── core/          # config, eventos/snapshots, bus, salud, runtime. Sin Qt.
│   ├── capture/       # FrameSource: webcam, archivo de video, imágenes (para tests)
│   ├── vision/        # calibración, homografía, clasificador de ocupación, estabilidad, chequeo de setup
│   ├── board/         # BoardModel: posición completa, inferencia por jugadas legales, tracker
│   ├── game/          # GameSession (máquina de estados), modos de juego (Strategy), PGN
│   ├── adapters/      # proveedores: base.py, tracking.py, local/ (motores UCI, Stockfish), online/ (después)
│   ├── ui/            # PySide6: ventana lateral, pestañas, asistente de setup, tema QSS
│   ├── assets/        # fuentes (OFL) e íconos empaquetados
│   ├── doctor.py      # chequeo de dependencias / permisos / hardware por SO
│   ├── cli.py         # `chessoptic`, `chessoptic doctor`, (después) replay / calibrate
│   └── __main__.py    # `python -m chessoptic`
├── tests/
│   └── fixtures/      # grabaciones reales del tablero (locales por ahora) + manifests
├── docs/
│   ├── PLAN.md            # este documento
│   ├── UI.md              # especificación de la interfaz
│   ├── IMPLEMENTATION.md  # orden de implementación, hitos, mapeo UI, "para hacer en casa"
│   ├── STATES.md          # máquina de estados detallada (se escribe en H2)
│   ├── SETUP.md           # guía de cámara / luz / encuadre (se escribe en H1)
│   └── PROTOCOL.md        # protocolo nativo ChessOptic (más adelante)
├── assets/            # logo
├── pyproject.toml     # uv / hatchling
├── CLAUDE.md
└── README.md
```

### 3.2 BoardModel: cómo sabemos qué pieza hay en cada casilla

**v1 (sin reconocer piezas):**
1. Al empezar se **asume la posición inicial** (el usuario la confirma; la cámara verifica que la ocupación coincide: 16 blancas, 16 negras, 32 vacías en el lugar correcto).
2. La visión entrega una matriz 8×8 de ocupación `{vacía, blanca, negra}` cuando la imagen está estable (sin mano encima).
3. Ante un cambio de ocupación, se buscan entre **las jugadas legales** (de ambos bandos, según el turno) la que produce exactamente esa ocupación. Así se mantiene la posición completa (tipo de pieza incluido) jugada a jugada.
   - 0 coincidencias → ocupación inválida/transitoria: esperar o marcar error.
   - 1 coincidencia → jugada.
   - Varias → solo en promoción: se resuelve por la plataforma/adaptador o por un default configurable.
4. Enroque, captura al paso y promoción quedan cubiertos porque se compara la ocupación resultante completa.

**v2 (con reconocimiento de piezas):** un detector (YOLO u otro) confirma el tipo de pieza por casilla, permite arrancar desde cualquier posición y recuperarse si se perdió el seguimiento.

Importante: el BoardModel reporta **posición/eventos**, no "jugadas que decidimos nosotros". La plataforma (o Chessconnect) es la que valida y ejecuta. Esto es igual a cómo funciona un tablero electrónico real.

### 3.3 Visión (v1)

1. **Captura**: OpenCV `VideoCapture`, 720p por defecto, ~10–15 fps de análisis alcanzan.
2. **Calibración**: el usuario marca las 4 esquinas (manual primero; detección automática después). Se elige dónde está a1. Se guarda por cámara.
3. **Homografía** → imagen rectificada 8×8.
4. **Clasificador de ocupación** por casilla: features de color/textura de la región central; se **autoentrena con la posición inicial** (64 etiquetas conocidas) y se refina tras cada posición confirmada.
5. **Estabilidad**: diferencia entre frames para detectar mano/movimiento; se exige N frames iguales antes de aceptar una ocupación.
6. **Confianza por casilla**: se expone a la UI para detectar mala luz o casillas dudosas.

---

## 4. Adaptadores de salida

Interfaz común (todas las salidas reciben eventos del BoardModel y pueden devolver eventos hacia la UI: jugada del rival, relojes, fin de partida, conexión).

```python
class OutputAdapter(Protocol):
    name: str
    async def start(self) -> None
    async def stop(self) -> None
    def on_board_event(self, event: BoardEvent) -> None        # posición/jugada detectada
    def subscribe(self, cb: Callable[[AdapterEvent], None])    # conexión, jugada rival, relojes, fin, errores
    @property
    def status(self) -> AdapterStatus
```

| Adaptador | Para qué | Estado |
|---|---|---|
| `LocalEngineAdapter` | Jugar contra Stockfish offline; probar la visión | Etapa 2 |
| `LichessAdapter` | Lichess Board API oficial (token `board:play`), sin intermediarios | Etapa 3 |
| `CompatAdapter` (Chessconnect) | Que ChessOptic aparezca como un tablero ya soportado por [Chessconnect](https://chessconnect.de) → acceso a chess.com y muchas plataformas | Etapa 4 (requiere prueba de concepto) |
| `NativeAdapter` | Protocolo abierto propio de ChessOptic, para proponer soporte nativo a Chessconnect u otros clientes | Etapa 5 |

### 4.1 Lo que sabemos de Chessconnect (investigado)

- Extensión de Chrome + apps Android/iOS, gratuita y no comercial, de Dr. Jörn Gehring. Usa la API oficial de chess.com para el juego normal y es reconocida por chess.com y Lichess.
- **No tiene API, SDK ni forma documentada de agregar tableros propios.** Solo habla con tableros electrónicos por **USB serie** y **Bluetooth** (en iOS solo BLE). Las marcas se agregaron una por una, en colaboración con fabricantes y la comunidad. Contacto: Discord del proyecto / info@chessconnect.de.
- Uso: se instala desde la Chrome Web Store → en chess.com/lichess aparece un botón "Connect" → Chrome muestra un selector de dispositivo (puerto serie o BLE) → "Connected".
- Los DGT por Bluetooth clásico aparecen como **puerto COM** → Chessconnect habla con un puerto serie, no con un hardware concreto.
- Tableros **sin** reconocimiento de piezas (ej. DGT Pegasus): Chessconnect muestra un diálogo de promoción en el navegador.
- Avisa la jugada del rival con LEDs del tablero y/o beep o voz. Con DGT e-board + reloj DGT3000 manda jugada y tiempos al reloj **a través del tablero**.
- Ajustes recomendados en chess.com: premoves desactivados, animación por defecto, "click squares" o "drag or click", "white always on bottom" desactivado.

### 4.2 Estrategia de compatibilidad

1. **Antes de escribir el CompatAdapter**, consultar a Jörn (Discord/email) si aceptaría un tablero por cámara / protocolo abierto, o si ve bien la emulación.
2. Elegir el tablero a emular **con reconocimiento completo de piezas** (DGT e-board por serie o Chessnut por BLE), para que el futuro detector de piezas tenga sentido. No el Pegasus.
3. Transporte por SO (a validar en la prueba de concepto):
   - **Serie virtual**: Windows con com0com (par de puertos); Linux/macOS con pseudo-terminales (`socat`/`os.openpty`) — **riesgo**: verificar que Chrome/WebSerial los liste.
   - **BLE periférico**: la PC anuncia un tablero BLE (ej. librería `bless`). Funciona también con la app de Chessconnect en celular/iPad.
4. Referencias de protocolos: documentación DGT e-board publicada/recuperada por la comunidad; [DGTCentaurMods](https://github.com/EdNekebno/DGTCentaur) (emulación de tableros en Python); implementaciones open source del protocolo Chessnut.

### 4.3 Preguntas abiertas para la prueba de concepto

1. ¿Cómo detectamos inicio y fin de partida? (pedidos de estado del cliente, LEDs, primera jugada… si no hay señal confiable: botón "partida en curso").
2. ¿Qué hace Chessconnect si al empezar el tablero no coincide con el sitio?
3. ¿Llegan relojes/jugada del rival por el protocolo emulado (DGT + DGT3000)? Si no, el driver mide sus propios tiempos de turno.
4. ¿Qué transporte funciona en cada SO (serie virtual vs. BLE)?

---

## 5. UX / UI

### 5.1 Concepto

La pantalla se reparte: **~3/4 navegador** (la plataforma) y **≤1/4 ChessOptic** (ventana angosta, ~300–420 px de ancho, alto completo, "siempre arriba" opcional). ChessOptic es un **panel de diagnóstico del driver**, legible de reojo. Durante una partida no debería requerir interacción.

Principios:
- Color **+** ícono siempre (accesible para daltonismo).
- Las acciones son para cuando algo falla.
- Modo compacto: solo indicador de salud, turno, última jugada y cámara miniatura.
- Sonido opcional en errores.

### 5.2 Modelo de estados (tres capas)

**A. Salud del driver — el "semáforo" (siempre visible, arriba).**
Solo refleja si el driver funciona, NO de quién es el turno.

| Componente | Estados |
|---|---|
| Cámara | OK · sin permiso · desconectada · fps bajos |
| Tablero | calibrado y visible · tapado/movido · baja confianza (luz) |
| Enlace | inactivo · anunciando/esperando cliente · conectado · perdido |

Semáforo: verde (todo OK) · amarillo (degradado: baja confianza, fps bajos, esperando cliente) · rojo (roto: sin cámara, tablero perdido, enlace caído en partida) · gris (pausado/sin configurar).

**B. Standby (sin partida).**

1. **Inicio** → buscar cámara.
2. **Sin calibrar** → asistente (o validar la calibración guardada automáticamente).
3. **Verificando tablero** → posición inicial completa ✓ · faltan/sobran casillas (se marcan en la cámara) · otra posición (v2: retomar/puzzle).
4. **Listo, esperando cliente** → salida elegida activa (puerto/BLE/Lichess), esperando conexión.
5. **Conectado, sin partida** → instrucciones: "iniciá o abrí una partida en la plataforma".

**C. Partida.**

| Estado | Visual |
|---|---|
| Mi turno | **Azul** (fondo/acento) |
| Moviendo (mano en el tablero, esperando estabilidad) | Azul + indicador de actividad |
| Turno del rival | Sin color, solo borde |
| Rival jugó → reproducí X | Borde destacado + jugada grande (ej. "Cf6") |
| Verificando reproducción | Indicador hasta que la ocupación coincide |
| Promoción | Aviso: "elegí la pieza en el navegador" (o default) |
| Posición no coincide | Alerta + casilla marcada en la cámara (además el semáforo puede pasar a amarillo/rojo) |
| Se pierde cámara/enlace en partida | Alerta fuerte (tu reloj corre) |
| Fin de partida | "Reordená el tablero" → vuelve a *Verificando tablero* |

Contenido de la vista de partida: última jugada (grande), mi tiempo, tiempo del rival (si están disponibles; si no, tiempo del turno medido por el driver), indicador de turno y una lista corta de las últimas jugadas "por las dudas".

### 5.3 Pantallas / navegación

1. **Asistente de primer uso**: elegir cámara → consejos de encuadre → marcar 4 esquinas → orientación (dónde está a1) → verificar posición inicial → elegir salida → instrucciones de conexión según SO/salida → prueba.
2. **En vivo** (principal): semáforo de salud + conexiones, bloque de turno/última jugada/relojes, cámara con overlay de ocupación, mini log, acciones rápidas (pausar, recalibrar).
3. **Cámara**: dispositivo, exposición/enfoque, recalibrar, vista cruda/rectificada, confianza por casilla.
4. **Log**: historial con filtros (jugadas/eventos/errores), exportar PGN y log, frames guardados de cada error.
5. **Ajustes**: salida/adaptador, sensibilidad de estabilidad, promoción por defecto, sonidos, idioma, tema, siempre arriba, modo compacto.
6. **Diagnóstico** (dentro de Ajustes): fps, latencia, tráfico del protocolo en crudo y decodificado.

Especificación detallada de pantallas, tokens y datos: [`docs/UI.md`](UI.md). Mockups en [`docs/design/`](design/). Diseño de referencia (una pantalla por estado): https://claude.ai/artifact/AF5QgG3z8ddDoGfvkNUbUS — privado del autor; pedí acceso si no lo podés abrir.

---

## 6. Etapas

> El orden real de trabajo, los hitos del POC (H0–H3) y el detalle por tarea están en [`IMPLEMENTATION.md`](IMPLEMENTATION.md). La Etapa 3 (Lichess) queda fuera de la v1 mínima: los proveedores online se deciden después de investigar Chessconnect.

### Etapa 0 — Base del repo (hito H0)
- [x] `pyproject.toml` (uv + hatchling), paquete `chessoptic`, entrada `chessoptic` y `python -m chessoptic`.
- [x] Ruff + mypy; CI en GitHub Actions con matriz **Windows / macOS / Linux**. (pytest: después del POC.)
- [x] `chessoptic doctor`: Python, OpenCV, cámara disponible, Stockfish en PATH, permisos por SO. (Bluetooth: "no evaluado" hasta que haya proveedores BLE.)
- [x] Ventana PySide6 vacía con layout de panel lateral y "siempre arriba".
- [x] README con instalación vía `pipx`/`uv tool`.

**Aceptación**: `pipx install .` y `chessoptic` abren la ventana en los tres SO (CI verde).

### Etapa 1 — Visión + BoardModel (hitos H1 y H2)
- [x] `FrameSource` (webcam, video, imágenes).
- [x] Calibración manual de 4 esquinas + orientación (4 posiciones de a1), persistida por cámara.
- [x] Clasificador de ocupación autoentrenado y estabilidad/mano.
- [x] Asistente de setup de 7 pasos con chequeo de detección y prueba de jugada (H1).
- [x] BoardModel con inferencia por jugadas legales (ambos bandos) y verificación de posición inicial (H2).
- [x] UI "En vivo" con cámara, overlay, semáforo de salud, log de jugadas detectadas (H1 + H2).
- [ ] Grabaciones reales del tablero y `chessoptic replay` (después del POC, ver IMPLEMENTATION §2.6).

**Aceptación**: partida completa grabada reconstruida sin errores; en vivo ≤1 falsa detección cada 50 jugadas con luz normal.

### Etapa 2 — Modo local
- [ ] `LocalEngineAdapter` con Stockfish (nivel configurable).
- [ ] Flujo completo de estados de partida en la UI (turno azul, reproducir jugada del rival, verificación, fin).

**Aceptación**: jugar una partida completa contra Stockfish usando solo piezas físicas.

### Etapa 3 — Lichess
- [ ] `LichessAdapter` con Board API: eventos, partida en curso, enviar jugadas, jugada rival, relojes, fin.
- [ ] Configuración de token en Ajustes.

**Aceptación**: partida real en Lichess desde el tablero físico.

### Etapa 4 — Compatibilidad Chessconnect (requiere PoC)
- [ ] Contacto con el autor de Chessconnect (registrar respuesta en este doc).
- [ ] PoC de transporte por SO (serie virtual y/o BLE).
- [ ] Implementación del protocolo del tablero emulado con reconocimiento de piezas.
- [ ] Respuestas a las preguntas de §4.3.

**Aceptación**: partida real en chess.com vía Chessconnect.

### Etapa 5 — Protocolo nativo + reconocimiento de piezas
- [ ] `docs/PROTOCOL.md`: spec abierta de ChessOptic y `NativeAdapter`.
- [ ] Detector de piezas (YOLO u otro → ONNX) y modo "arrancar desde cualquier posición".

### Etapa 6 — v1 estable
- [ ] Instaladores nativos en GitHub Releases.
- [ ] Calibración automática, robustez a cambios de luz, modo diagnóstico completo.

---

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Luz/sombras | Features relativas a la casilla vacía; refinamiento tras cada posición confirmada; confianza visible en la UI. |
| Cámara oblicua | Homografía; guía de encuadre en el asistente. |
| Piezas y casillas de tono similar | Documentar requisitos; features de textura/bordes; v2 con detector. |
| Chrome no lista puertos virtuales en algún SO | Alternativa BLE; documentar por SO en `doctor`. |
| Chessconnect cambia o no acepta la emulación | Lichess directo como camino oficial siempre disponible; protocolo nativo abierto. |
| Pérdida de seguimiento a mitad de partida | Resincronización manual en la UI; v2 con detector de piezas. |

---

## 8. Glosario

- **Driver**: ChessOptic en sí; convierte imagen en estado del tablero y lo entrega.
- **Ocupación**: para cada casilla, vacía/blanca/negra.
- **BoardModel**: posición completa (con tipo de pieza) mantenida por ChessOptic.
- **Adaptador / salida**: módulo que entrega eventos a una plataforma o cliente.
- **Cliente**: quien consume la salida (Lichess, Chessconnect, Stockfish local).
