# Hoja de ruta después de la v0.1

La v0.1 cerró el POC: una partida completa contra Stockfish con piezas físicas y una webcam cualquiera. Lo que sigue se ordena por lo que más valor da con menos riesgo. Cada bloque es una versión 0.x; dentro de cada uno el orden es el propuesto.

## v0.2 — Partidas locales completas

Objetivo: que jugar contra el motor sea una experiencia de verdad, no una demo.

| Qué | Estado hoy | Qué falta |
|---|---|---|
| Dificultad | Nivel 1–8 en Ajustes y en el asistente (se traduce a `Skill Level` y tiempo por jugada del motor). | Mostrar el Elo aproximado de cada nivel; opción "Elo limitado" (`UCI_LimitStrength` + `UCI_Elo`) para motores que lo soporten. |
| Rendirse | "Terminar" cierra la partida con resultado `*`. | Botón **Rendirse** que registre `0-1` / `1-0` y lo diga en el PGN; confirmación para no tocarlo sin querer. |
| Deshacer una jugada | No existe. | **Deshacer** la última jugada propia (y la respuesta del motor): el modelo vuelve atrás y el panel pide reponer las piezas, verificando como una jugada del rival. En seguimiento, deshacer la última de cualquier bando. |
| Modos con tiempo | Solo `FreePlay` (sin reloj). La interfaz `GameMode` ya existe (Strategy). | `TimedMode` con controles clásicos (3+2, 5+0, 10+0, 15+10) y reloj en el bloque de estado; el tiempo propio corre desde que el motor mueve hasta que la cámara ve tu jugada. Pérdida por tiempo como `GameOver`. |
| Historial de partidas | Cada partida se exporta a `<datos>/games/*.pgn` a pedido. | Guardar siempre el PGN al terminar con cabeceras completas (motor, nivel, color, control de tiempo, resultado) y una pestaña **Partidas** con el balance por configuración: ganadas / perdidas / tablas contra cada nivel, y abrir el PGN. |
| Arrancar desde cualquier posición | Solo desde la posición inicial. | Pedir la posición por FEN o por foto con detección de piezas (Etapa 5 del PLAN). |

## v0.3 — Online

Dos caminos en paralelo, porque dependen de terceros distintos.

### Lichess (directo)
- La [Board API](https://lichess.org/api#tag/Board) es oficial y está pensada para tableros físicos. Lo que hace falta: token personal con alcance `board:play` guardado en Ajustes, stream de eventos y de la partida (ndjson), enviar jugadas en UCI, reloj del cliente, resultado, y retomar una partida en curso al abrir ChessOptic.
- Adaptador `adapters/online/lichess.py` con la misma interfaz `OutputAdapter` que Stockfish; el flujo de estados del panel ya es el mismo (tu turno → enviada → rival jugó → reproducila).
- Riesgo bajo: API documentada y estable; se puede probar con una cuenta propia y partidas contra la IA de Lichess.

### chess.com (vía Chessconnect)
chess.com no tiene API pública para jugar. [Chessconnect](https://chessconnect.de) conecta tableros electrónicos a chess.com y otras plataformas, así que el camino es que ChessOptic se presente como un tablero más.

Pasos:
1. **Pedido al autor de Chessconnect** (ver kit más abajo): si existe o puede existir un transporte para un "tablero virtual" (puerto serie virtual, BLE emulado o un protocolo local por socket), y con qué protocolo de tablero.
2. Según la respuesta, PoC de transporte por SO (serie virtual con `com0com` en Windows, `socat` en macOS/Linux, o BLE emulado).
3. Implementar el protocolo del tablero elegido en `adapters/online/chessconnect.py`.

### Kit para el pedido a Chessconnect
Lo que conviene mandar, en inglés, corto:
- Qué es ChessOptic en dos líneas y el repo público.
- Un video de 30–60 s: el asistente ya calibrado, una jugada propia detectada, una jugada del motor reproducida y verificada. En Windows: Xbox Game Bar (`Win+Alt+R`) o OBS; grabar con la ventana de ChessOptic al lado del tablero real.
- Tres capturas: "Tu turno" con la jugada marcada, "Rival jugó · reproducila" y la lista de jugadas.
- La pregunta concreta: "¿Chessconnect puede recibir jugadas desde un tablero virtual (sin hardware), por ejemplo por puerto serie virtual, BLE o un socket local? ¿Qué protocolo de tablero conviene emular?"
- Lo que ofrecemos: implementar el protocolo que indiquen y publicarlo con licencia Apache-2.0.

## v0.4 — Robustez y comodidad

- Calibración asistida: sugerir las esquinas automáticamente y detectar cuando la cámara se movió.
- Modo compacto, sonido en errores, pausa.
- Grabaciones reales del tablero como banco de pruebas (`chessoptic replay`) y primeros tests automáticos sobre ellas.
- Instaladores (GitHub Releases) y actualización de `doctor` por SO.

## Más adelante

- Reconocimiento del tipo de pieza por imagen para arrancar desde cualquier posición (hoy el tipo viene de la lógica de ajedrez, que alcanza para una partida desde el inicio).
- Protocolo abierto propio (`docs/PROTOCOL.md`) para que otras aplicaciones usen ChessOptic como tablero.
- Celular como cámara.
