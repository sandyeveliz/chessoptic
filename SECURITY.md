# Política de seguridad

## Versiones con soporte

ChessOptic está en fase temprana: solo la última versión publicada recibe correcciones de seguridad.

| Versión | Soporte |
| ------- | ------- |
| 0.1.x   | Sí      |
| < 0.1   | No      |

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usá el reporte privado de GitHub:
[Security → Report a vulnerability](https://github.com/sandyeveliz/chessoptic/security/advisories/new).

Incluí, si podés:

- Qué versión y sistema operativo usás.
- Pasos para reproducirlo y qué impacto tiene (por ejemplo: ejecución de código al abrir un PGN, fuga de un token de una plataforma, escritura fuera de la carpeta de datos).
- Una propuesta de corrección, si la tenés.

Qué esperar:

- Acuse de recibo en un plazo de 7 días.
- Una evaluación inicial y un plan en un plazo de 30 días.
- Te damos crédito en el aviso de seguridad, salvo que prefieras quedar anónimo.

## Alcance

Está dentro del alcance el código de este repositorio y los paquetes que se publiquen desde él. Las vulnerabilidades de dependencias (OpenCV, PySide6, python-chess, Stockfish) se reportan en sus proyectos; si afectan a ChessOptic de una forma particular, contanos igual.
