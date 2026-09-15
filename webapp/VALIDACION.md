# Validación local · 15/09/2026

## Resultado

- 19 pruebas Django superadas, con el pool distribuido de 200 conversaciones / 320 unidades para verificar la importación; los demás escenarios usan registros sintéticos aislados. Incluye alta de equipo configurable, contraseñas aleatorias, roles, solapamiento de asignaciones y rechazo de configuración inválida.
- `manage.py check`: sin incidencias.
- `manage.py check --deploy` con configuración de producción y una clave temporal de comprobación: sin incidencias. Esto valida configuración; no demuestra un despliegue real.
- JavaScript: validación sintáctica con `node --check`.
- Assets estáticos recopilados correctamente.
- Backup de SQLite creado mediante su API y comprobado con `PRAGMA integrity_check`.
- Comprobado que producción rechaza las claves de desarrollo y de ejemplo, y acepta la configuración de prueba con una clave distinta.

## Navegador real, con Playwright

Base exclusiva de QA: `webapp/.local/qa.sqlite3`, separada del estudio.

1. Acceso con cuenta principal de pruebas y apertura de su muestra.
2. Selección de etiqueta: respuesta del servidor y estado «Guardado».
3. Recarga: conserva etiqueta y revisión.
4. Red simulada sin conexión: muestra fallo, conserva elección y ofrece reintentar.
5. Recuperación de red: reintenta, confirma guardado y conserva la nueva etiqueta tras recargar (versión 2; primer voto conservado).
6. Panel de control del evaluador principal: muestra progreso y oculta votos aún no accesibles.
7. Conversación de cuatro turnos: cuatro formularios independientes y doce opciones, sin pérdida de turnos.
8. Anchuras de 320, 390 y 1440 píxeles: sin desbordamiento horizontal de la página en las pantallas inspeccionadas. El código original del usuario queda desplegable y las respuestas de la IA conservan el stripping verbal-only.

Capturas de comprobación en `webapp/output/playwright/` (ignoradas por Git). Se inspeccionaron visualmente login de escritorio, control de escritorio, lectura móvil y botones de anotación móvil. Los errores observados en consola fueron el favicon inicial (resuelto añadiendo el icono) y el fallo de red provocado intencionalmente.

## Separación de datos

La configuración de equipos reales, credenciales, evaluaciones y notas operativas no forma parte del código distribuido. Las pruebas de navegador usan otra base de datos. El ejemplo de equipo contiene identidades genéricas y las contraseñas de prueba solo se crean en bases aisladas.

## Pendiente para la siguiente etapa

- Acceso desde teléfono físico, HTTPS, DNS y validación del contenedor en el VPS cuando esté disponible. La comprobación móvil realizada aquí es con viewport de navegador de escritorio, no con Safari/iOS o Android físicos.
- Medir el tiempo real con un piloto y acordar el reparto con la dirección del estudio. No se ha estimado ni prometido una duración total.
- Acordar cómo adjudicar desacuerdos y si hace falta un subconjunto común a todos. El export actual conserva cada evaluación por separado.

Esta comprobación no equivale a una auditoría de seguridad exhaustiva ni valida la metodología científica de un estudio.
