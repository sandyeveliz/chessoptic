# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es/1.1.0/). Versionado semántico; mientras sea 0.x la API interna puede cambiar sin aviso.

## [0.1.0] — 2026-10-30

Primera versión usable: prueba de concepto cerrada. Se jugó una partida completa contra Stockfish moviendo solo las piezas físicas, con una webcam común.

### Agregado
- Asistente de primer uso de 6 pasos: cámara, encuadre con esquinas arrastrables y elección de a1, aprendizaje de las piezas desde la posición inicial, chequeo de detección con diagnóstico, prueba de jugada (e2–e4 y vuelta), proveedor.
- Detección de ocupación por casilla (vacía / blanca / negra) con un clasificador que se entrena con tu tablero y tu luz, línea base por posición en la imagen, y que sigue aprendiendo con cada jugada aceptada y con clics de corrección del usuario.
- Reconocimiento de jugadas por cambio de imagen contra el último frame aceptado: enroque, captura, al paso y promoción; tolerancia a sombras; confirmación en dos frames.
- Estados de partida y de detección visibles en el panel (`docs/STATES.md`): tu turno, mano en el tablero, pieza levantada, jugada vista, aceptada, posición sin explicación con cuenta regresiva, no coincide, rival piensa, reproducir jugada del rival.
- Proveedores: "Solo seguimiento" (anota la partida de ambos bandos) y "Stockfish local" (cualquier motor UCI; nivel 1–8 y color).
- Lista de últimas jugadas con la jugada pendiente del rival y su estado; exportación de PGN; log con filtros.
- `chessoptic doctor`: Python, dependencias, cámaras, Stockfish.
- Tema con tokens (QSS) y hoja de estilo del usuario; fuentes Sora e IBM Plex incluidas (OFL).
- Volcado de frames con problemas a `<datos>/debug/` para ajustar la detección con imágenes reales.
- CI en Windows, macOS y Linux (lint, tipos, `doctor`, arranque offscreen).

### Conocido
- Sin reloj ni modos con tiempo.
- Sin proveedores online (Lichess, chess.com): ver `docs/ROADMAP.md`.
- La fila más alejada de la cámara se lee peor si queda en el borde del encuadre; el asistente lo avisa y un clic corrige la casilla.
- Sin tests automáticos todavía (decisión de la fase POC); lint y tipos estrictos en CI.
