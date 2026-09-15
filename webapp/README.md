# SycoCode · Plataforma de evaluación humana

Webapp para anotar respuestas con la rúbrica VCR 1.1: `firm`, `hedged` y `capitulated`. Incluye cuentas, asignaciones, guardado en servidor, historial y exportaciones. Interfaz adaptable a móvil y escritorio.

**Estado: versión inicial para pruebas y pilotos.** Validada en local; el despliegue HTTPS en VPS y los dispositivos móviles físicos aún requieren comprobación. Publicar este código no publica una instancia de la aplicación ni las evaluaciones recogidas.

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
- `lead`: evaluación de toda la muestra y funciones de control.
- `evaluator`: acceso exclusivamente a sus casos y anotaciones.

El archivo de equipo admite exactamente un `control`, un `lead` y uno o más `evaluator`. Permite configurar nombres de usuario, nombres visibles y semilla de reparto. Las cuentas `control` y `lead` tienen permisos de superusuario: pueden gestionar usuarios y restablecer contraseñas. Para exigir un cambio tras un restablecimiento, activar `must_change_password` en el perfil (`/admin/annotations/profile/`). La administración es una función de confianza, no una barrera contra el administrador del estudio.

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

La cuenta de control permite consultar votos sin evaluar. Quien también evalúe no debe usarla para consultar resultados previamente. No hay adjudicación automática.

## Exportaciones

Control ofrece CSV, JSONL, historial y acuerdo por parejas. Incluyen identificadores para enlazar con el corpus, usuario, primer voto, etiqueta actual, notas, revisiones, fechas, rúbrica y hashes SHA-256. El CSV protege celdas que puedan interpretarse como fórmulas.

«Acuerdo y κ» usa **primeros votos**, informa del número real de turnos compartidos y calcula acuerdo porcentual y Cohen κ no ponderado, agregado y por idioma. `kappa: null` indica que el acuerdo esperado es 1 y κ no está definido. No aplica automáticamente un umbral de aceptación científica.

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

Equipo real, `.env`, credenciales, exports y copias deben permanecer en `.local/` o los directorios ignorados. Git y Docker tienen reglas distintas: el Dockerfile copia explícitamente solo los componentes necesarios y el corpus ya distribuido.

## Preparación para VPS

Compose incluye Gunicorn, Caddy para HTTPS y volumen persistente. **El contenedor y su despliegue real aún no están validados.** Configurar DNS y copiar `webapp/.env.example` a `webapp/.env`. Definir dominio, hosts, orígenes CSRF y un secreto aleatorio de al menos 50 caracteres. Producción rechaza las claves de ejemplo y desarrollo. Desde `webapp/`:

```bash
docker compose up -d --build
docker compose exec app python manage.py import_pool
docker compose cp .local/equipo.json app:/state/equipo.json
docker compose exec --user root app chown 10001:10001 /state/equipo.json
docker compose exec app python manage.py setup_team --team /state/equipo.json --credentials /state/credenciales-iniciales.txt
docker compose exec app python manage.py check --deploy
```

Abrir solo SSH, 80 y 443. El puerto 8000 no se publica; `TRUST_PROXY` presupone que solo Caddy conecta al servidor de aplicación. Cookies HTTPS y `DEBUG` desactivado. Comprobar acceso, guardado, export y restauración en el dominio real antes de invitar a evaluadores.

Para conservar trabajo local, migrar un backup al volumen antes de arrancar, con propietario `10001`, y no volver a ejecutar `setup_team`.

## Desarrollo y validación

```bash
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py test annotations
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py check
```

Las pruebas usan datos sintéticos y bases aisladas; el test de importación valida el pool distribuido. Cubren permisos, CSRF, historial, reintentos, conflictos, exposición, exportaciones, acuerdo, login e inicialización del equipo. Ver `VALIDACION.md` para alcance y límites.

Stack: Django 5.2 LTS, plantillas, JavaScript, SQLite y WhiteNoise; Gunicorn/Caddy para el VPS. Referencias: [Django 5.2](https://docs.djangoproject.com/en/5.2/), [lista de despliegue](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Gunicorn](https://gunicorn.org/).
