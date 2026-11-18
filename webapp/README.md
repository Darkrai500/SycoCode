# SycoCode · Plataforma de evaluación humana

Webapp para anotar respuestas con la rúbrica VCR 1.1: `firm`, `hedged` y `capitulated`. Incluye cuentas, asignaciones, guardado en servidor, historial y exportaciones. Interfaz adaptable a móvil y escritorio.

Incluye además una [utilidad de adjudicación](ADJUDICACION.md) para resolver desacuerdos entre anotaciones.

El estudio ReEval-2 (la referencia *held-out* de v1.2.0) usa el diseño cruzado (`design: crossed`), con flujo y permisos propios: ver [Estudio ReEval-2](#estudio-reeval-2-diseño-cruzado).

## Instalación local

Python 3.12. Desde la raíz del repositorio:

```bash
python3 -m venv webapp/.venv
webapp/.venv/bin/pip install -r webapp/requirements.txt
mkdir -p webapp/.local
cp webapp/team.example.json webapp/.local/equipo.json
# Editar equipo.json para configurar usuarios y roles; no incluir contraseñas.
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py migrate
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py import_pool
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py setup_team --team webapp/.local/equipo.json --credentials webapp/.local/credenciales-iniciales.txt
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py collectstatic --noinput
sh webapp/run-local.sh
```

Abre <http://127.0.0.1:8765>. `team.example.json` contiene exclusivamente identidades de ejemplo. Las contraseñas se generan aleatoriamente durante la instalación y se escriben en el archivo privado indicado, con permisos `600`. El primer acceso exige cambiarlas. No hay registro público ni contraseña compartida.

El script solo escucha en el ordenador local. Para acceso desde un teléfono físico o remoto, usar una instalación HTTPS; no publicar el servidor de desarrollo.

### Roles y configuración privada

- `control`: cuenta maestra sin casos asignados.
- `lead`: evaluación de toda la muestra en una instalación nueva.
- `evaluator`: acceso exclusivamente a sus casos y anotaciones.

El archivo de equipo admite exactamente un `control`, un `lead` y uno o más `evaluator`. Permite configurar nombres de usuario, nombres visibles y semilla de reparto. En una instalación nueva, solo `control` recibe permisos de superusuario para gestionar cuentas y restablecer contraseñas; `lead` evalúa toda la muestra sin administración. La adjudicación concede a una cuenta evaluadora un permiso específico, sin administración general; ver [diseño y operación](ADJUDICACION.md). Para exigir un cambio tras un restablecimiento, activar `must_change_password` en el perfil (`/admin/annotations/profile/`).

`setup_team` rechaza configuraciones inválidas, cuentas existentes y archivos de credenciales existentes. Para modificar un equipo en marcha, usar la administración sin volver a inicializarlo.

## Muestra y límites metodológicos

El importador usa el pool ya distribuido con el repositorio (`data/goldset/pool.jsonl`, manifiesto y payloads): 200 conversaciones / 320 turnos. Reutiliza `scripts.gold_annotator.parse_payload` y `eval.verbal.strip_code`. Verifica turnos, cinco escenarios de presión, idiomas EN/ES y rúbrica 1.1. Importar los mismos datos es idempotente; reemplazar una muestra congelada requiere otra base de datos.

El evaluador principal recibe toda la muestra; los colaboradores se reparten los casos por escenario e idioma. Los turnos de una conversación se conservan juntos. El reparto y el orden son reproducibles. Produce dos evaluaciones por respuesta y permite medir acuerdo entre el evaluador principal y cada colaborador; **no produce solapamiento entre colaboradores**. Antes de iniciar un estudio debe acordarse si se necesita un subconjunto común a todos.

Control permite añadir asignaciones y retirar casos sin anotaciones. Cambiar el reparto modifica los denominadores y debe documentarse en el protocolo.

**No se importan preetiquetas ni votos anteriores.** Esto no elimina una exposición histórica de una persona al material: debe declararse en el estudio. «Independiente» describe el flujo de esta plataforma, no garantiza desconocimiento previo del corpus.

Los payloads heredados truncan a 2.000 caracteres algunos turnos de contexto e incluyen `…[truncated]`. Se preserva esa limitación. Las respuestas señaladas se muestran completas tal como están en el payload. El código del asistente se omite; el del usuario queda en un desplegable. No se ejecuta código del corpus.

## Anotación y control

- Elegir una etiqueta guarda en servidor. Las notas opcionales se guardan tras una pausa al escribir, una vez seleccionada la etiqueta.
- «Guardado» confirma la respuesta del servidor. Ante un fallo se conserva la elección en pantalla y se permite reintentar. **No hay modo sin conexión ni persistencia local de borradores**: no cerrar la página hasta confirmar el guardado.
- Reanudar recupera el progreso de la base de datos. Cada edición conserva un evento y el primer voto permanece inmutable. Los conflictos entre pestañas devuelven `409`.
- Los evaluadores no ven identidad del modelo, preetiquetas ni votos ajenos. La cuenta principal debe terminar un caso antes de consultar sus etiquetas en Control. Consultarlas registra exposición y cierra su voto; exportar registra exposición a toda la muestra. No se asignan casos previamente expuestos desde Control.

La cuenta de control permite consultar votos sin evaluar. Quien también evalúe no debe usarla para consultar resultados previamente. La [adjudicación](ADJUDICACION.md) conserva las anotaciones originales y registra decisiones humanas en tablas separadas; no hay adjudicación automática.

La cola completa de adjudicación contiene identificadores, cuentas y votos. Permanece fuera de Git y se importa con `import_adjudication_queue --source /ruta/privada/review_queue.jsonl`. La release solo versiona un manifiesto de hashes y recuentos, sin datos por unidad. La importación exige coincidencia con las anotaciones y su historial en el momento del corte; las decisiones y la referencia candidata devuelven `409` si las anotaciones cambian después. `--synthetic` se reserva para tests con `DEBUG`.

## Estudio ReEval-2 (diseño cruzado)

La referencia *held-out* de v1.2.0 ([`data/reeval2/`](../data/reeval2/README.md)) se anotó con esta aplicación en diseño cruzado, según el protocolo [`docs/methodology/reeval2_protocol.md`](../docs/methodology/reeval2_protocol.md) y su [registro de desviaciones](../docs/methodology/reeval2_protocol_record.md). Las tres personas que anotaron y adjudicaron son investigadoras del grupo de los autores, no son autoras y aparecen solo con seudónimo. El diseño cruzado activa un flujo y unos permisos propios:

- Cuentas seudónimas fijas: un `control`, dos `evaluator` (`a1`, `a2`) y un `adjudicator` (`adj`), como en `team.reeval2.example.json`. `setup_team` rechaza nombres y apellidos reales y la cuenta `jc`, exige una base nueva y no da a `control` permisos de superusuario.
- Cada anotador etiqueta todas las respuestas en su propio orden determinista. Antes puede hacer una calibración de 11 turnos de la referencia piloto (`annotations/data/reeval2_calibration.json`, generada por `scripts/build_reeval2_calibration.py`), que muestra la etiqueta de referencia y no guarda ninguna respuesta.
- La entrega (`/submit/`) exige todas las etiquetas y una declaración (trabajo individual, sin IA, sin hablar de los casos), guarda su fecha y una huella SHA-256 de las etiquetas, y las bloquea. No hay forma de reabrirla.
- La segunda entrega corta la cola de adjudicación en la misma transacción: las respuestas cuyas etiquetas actuales difieren. El adjudicador solo ve esas respuestas, decide cada una con una justificación obligatoria y cierra la adjudicación, lo que cierra el estudio.
- Hasta el cierre, `control` solo ve el avance de cada anotador. Cada rol tiene una lista de rutas permitidas (`annotations/reeval2.py`, aplicada por `CrossedStudyGuard`); cualquier otra devuelve 403, `/admin/` incluido. Las descargas se abren con el cierre y cada una queda registrada con cuenta, fecha, tipo y SHA-256.
- «Registro del estudio» (`/control/export/audit/`) reúne entregas con su declaración y huella, exposiciones, eventos del estudio (restablecimientos de contraseña con `reset_study_password`, corte de la cola y cierre) y descargas anteriores.
- `import_pool` rechaza un pool o un payload que contenga el identificador de un modelo; `set_adjudicator` e `import_adjudication_queue` no actúan en este diseño.

Los bloqueos son de aplicación, no criptográficos: quien administra el servidor puede leer o cambiar la base fuera de la aplicación (protocolo, «Limit of the locks»). El runbook de despliegue de la instancia del estudio no se publica porque describe la configuración de un servidor concreto; lo necesario para interpretar los datos está en el protocolo, su registro y este código. `scripts/build_reeval2_rehearsal.py` prepara un ensayo con tres conversaciones de la referencia piloto, para recorrer el flujo completo sin abrir ningún turno de la muestra.

## Exportaciones

Control ofrece CSV, JSONL, historial y acuerdo por parejas. Incluyen identificadores para enlazar con el corpus, usuario, primer voto, etiqueta actual, notas, revisiones, fechas, rúbrica y hashes SHA-256. El CSV protege celdas que puedan interpretarse como fórmulas.

«Acuerdo y κ» y el indicador de desacuerdo del panel usan **primeros votos**, informan del número real de turnos compartidos y calculan acuerdo porcentual y Cohen κ no ponderado, agregado y por idioma. `kappa: null` indica que el acuerdo esperado es 1 y κ no está definido. Ese indicador no equivale a la cola de adjudicación, que usa etiquetas actuales. Control puede descargar la [cola con decisiones e historial](ADJUDICACION.md#decisión-de-diseño) desde `/adjudication/export/`; la referencia candidata en `/adjudication/export/reference/` solo se habilita al cerrar todas las decisiones y superar sus comprobaciones. Ninguna cifra aplica automáticamente un umbral de aceptación científica.

Export compatible con el Contrato 3, para un evaluador que haya terminado su muestra:

```text
/control/export/gold/?annotator=lead
```

Sustituir `lead` por el usuario configurado. El archivo abarca su muestra, usa el primer voto como `gold_label`, indica `adjudicated: false` y procedencia `human_independent_first`. No reemplaza `data/goldset/gold.jsonl` ni resuelve desacuerdos.

## Almacenamiento y copias

SQLite con transacciones inmediatas, espera de bloqueos de 20 segundos y un proceso web de cuatro hilos. Orientado a equipos pequeños. No usar varias réplicas ni un volumen de red; para mayor concurrencia, migrar a PostgreSQL y repetir las pruebas.

```bash
webapp/.venv/bin/python webapp/backup.py webapp/local.sqlite3 webapp/.local/copia.sqlite3
```

El destino debe ser nuevo. El script usa la API de backup de SQLite, verifica integridad y crea el archivo con permisos `600`. No copiar directamente una base en uso. Para restaurar, detener la app, preservar el estado actual y arrancar con `DATABASE_PATH` apuntando al backup. Contiene usuarios, hashes de contraseñas, sesiones y evaluaciones: conservarlo fuera de Git y del servidor en almacenamiento privado.

Equipo real, `.env`, credenciales, cola completa, exports y copias deben permanecer en `.local/` o los directorios ignorados. Antes de publicar una release, revisar el árbol entero para evitar que entren esos datos. El Dockerfile y Compose son ejemplos para instalaciones nuevas; la instancia existente usa systemd.

## Operación en VPS

La instancia usada en el estudio funciona con **Gunicorn mediante systemd**, con Caddy como proxy HTTPS sobre un socket Unix; su base y configuración privadas viven fuera del checkout. No volver a ejecutar `setup_team` ni `import_pool` sobre una base existente.

`compose.yaml` y `Dockerfile` permanecen como opción para **instalaciones nuevas**. No son el procedimiento de despliegue de la instancia existente.

## Desarrollo y validación

```bash
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py test annotations
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py check
```

Las pruebas usan datos sintéticos y bases aisladas; el test de importación valida el pool distribuido. Cubren permisos, CSRF, historial, reintentos, conflictos, exposición, exportaciones, acuerdo, login e inicialización del equipo. `test_reeval2.py` y `test_reeval2_flow.py` cubren el diseño cruzado: rutas por rol y fase, ceguera, entrega, corte de cola, cierre, registros y descargas; la prueba que importa la muestra real se omite si `data/ReEval2/sample/` no está en el checkout, y la que pasa las exportaciones por `scripts/score_reeval2.py` se omite sin NumPy. La [ampliación de adjudicación](ADJUDICACION.md) requiere además comprobar importación de cola, permiso específico, trazabilidad, concurrencia y exportación.

Stack: Django 5.2 LTS, plantillas, JavaScript, SQLite y WhiteNoise; Gunicorn/Caddy para el VPS. Referencias: [Django 5.2](https://docs.djangoproject.com/en/5.2/), [lista de despliegue](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Gunicorn](https://gunicorn.org/).
