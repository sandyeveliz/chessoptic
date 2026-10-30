# Guía de setup: cámara, luz y tablero

ChessOptic no exige una cámara ni un tablero concretos: el asistente de primer uso **chequea** si tu combinación funciona y te dice qué ajustar. Esta guía explica qué ayuda y qué significa cada hallazgo del chequeo.

## Antes de empezar

- Cámara **fija** (brazo con clamp, trípode, soporte sobre el monitor). Si se mueve después de calibrar, hay que recalibrar.
- El tablero entero dentro de la imagen, ocupando la mayor parte del encuadre. Desde arriba es lo más fácil; en diagonal funciona si la cámara no queda muy baja (las piezas altas tapan la casilla de atrás).
- Luz pareja. Evitá: ventana de fondo (contraluz), una lámpara puntual que tire sombras largas, luz que cambie durante la partida.
- Si tu cámara permite **fijar enfoque y exposición**, hacelo (pestaña Cámara, o el software del fabricante). El autoenfoque y la autoexposición "respirando" son la causa más común de falsos positivos.

## Los 7 pasos del asistente

1. **Cámara**: elegí la cámara. Si ya tiene una calibración guardada, podés reutilizarla.
2. **Encuadre**: acomodá la cámara hasta que el tablero quede dentro de la guía.
3. **Esquinas**: arrastrá las cuatro manijas a las esquinas exteriores de la zona de juego y decí dónde está a1. La vista rectificada de abajo tiene que mostrar un tablero derecho.
4. **Posición inicial**: armá las 32 piezas y sacá la mano. ChessOptic aprende cómo se ven *tus* piezas y *tus* casillas con esa posición (no hace falta ningún modelo descargado).
5. **Chequeo de detección**: compará el overlay con tu tablero y respondé si coincide. Abajo aparece el reporte (ver siguiente sección).
6. **Prueba de jugada**: mové e2–e4, soltá y volvé el peón. Si no lo detecta en unos segundos, probá "Reintentar" o revisá luz y estabilidad.
7. **Proveedor**: con quién jugás. En el POC: "Solo seguimiento".

## Qué significa cada hallazgo del chequeo

| Hallazgo | Qué pasa | Qué hacer |
|---|---|---|
| **Contraste en casillas claras/oscuras** | Las piezas y la casilla vacía se ven casi iguales para la cámara. | Más luz de frente; piezas con más contraste contra el tablero; si el tablero brilla, cambiá el ángulo. |
| **Casillas que cambian solas** (parpadeo) | La misma posición se clasifica distinto entre frames. | Fijá exposición y enfoque; evitá lámparas que titilan; fijá anti-parpadeo 50 Hz en la cámara. |
| **Zona fuera de foco** | Una parte del tablero está borrosa. | Enfocá al tablero y desactivá el autoenfoque. Limpiá la lente. |
| **Imagen muy oscura / quemada** | Exposición fuera de rango. | Más o menos luz; ajustá la exposición manual. |
| **Luz despareja** | Un cuadrante está mucho más oscuro. | Mové la lámpara o la cámara para eliminar la sombra. |
| **Casillas con poca seguridad** | Varias casillas se reconocen con margen chico. | Revisá luz y contraste; las casillas marcadas son las dudosas. |

Niveles: **Bien** (sin hallazgos serios), **Justo** (funciona, puede fallar con sombras o cambios de luz; el semáforo queda en amarillo) e **Insuficiente** (conviene corregir antes de jugar). Siempre podés "Continuar igual".

## Dónde queda guardado

La calibración y lo aprendido de tus piezas se guardan por cámara en la carpeta de configuración (`%APPDATA%\ChessOptic\cameras\` en Windows, `~/Library/Application Support/ChessOptic/cameras/` en macOS, `~/.config/ChessOptic/cameras/` en Linux). Borrá el archivo de una cámara para forzar el asistente desde cero.
