# Adjudicación humana

La utilidad de adjudicación permite que una persona identificada con su propia cuenta decida la etiqueta final de cada unidad de una cola de revisión congelada (desacuerdos entre las dos anotaciones de cada respuesta y casos con desacuerdos o ediciones anteriores). Las anotaciones originales y su historial se conservan sin cambios; cada decisión guarda etiqueta, justificación, cuenta, fecha y versión en tablas separadas. No hay adjudicación automática ni se muestran votos de los jueces.

Una decisión tomada por una sola persona se identifica como adjudicación individual, aunque coincida con alguno de los votos; no equivale a consenso del equipo ni a una evaluación independiente adicional.

## Decisión de diseño

| Elemento | Regla |
|---|---|
| Unidad de decisión | `unit_id` de `Unit`, enlazado a `group_id`, `record_id` y `judged_turn`. La conversación se lee de la muestra ya importada. |
| Cola congelada | Solo se versiona `webapp/annotations/data/reeval_queue_manifest_2026-09-24.json`, con hashes, versión de rúbrica y recuentos; no contiene identificadores de unidad, nombres ni votos. `import_adjudication_queue --source /ruta/privada/review_queue.jsonl` exige el JSONL completo fuera del repositorio. Dentro de una transacción coteja su SHA-256, el estudio, la rúbrica, el estado de las anotaciones y su historial, los identificadores/votos y la unión de casos y sus recuentos. Una discrepancia deja la cola sin importar. |
| Identidad y acceso | `Profile.can_adjudicate` habilita la decisión para una cuenta evaluadora concreta. El comando de concesión exige que haya completado toda la muestra y rechaza `is_staff`/`is_superuser`. `control` supervisa y exporta; no adjudica. Las comprobaciones de acceso se hacen en el servidor en cada petición. |
| Interfaz | `/adjudication/` permite recorrer y filtrar pendientes/resueltos; `/adjudication/<unit_id>/` muestra conversación, rúbrica, primer voto, etiqueta actual e historial de ambos anotadores, y exige una de las tres etiquetas con justificación para guardar. |
| Persistencia | `AdjudicationQueueItem` registra la pertenencia a la cola; `Adjudication` mantiene la decisión vigente; `AdjudicationEvent` registra cada creación o revisión con etiqueta, justificación, cuenta, fecha y versión. `Annotation` y `AnnotationEvent` conservan los votos originales. |
| Concurrencia e integridad | La petición lleva versión y UUID de envío. Una versión obsoleta devuelve `409`; repetir exactamente un envío ya confirmado no crea otra revisión. Un POST de decisión devuelve `409` si el estado de anotaciones/historial difiere del corte importado. La protección CSRF y la validación de etiqueta/justificación se aplican en el servidor. |
| Exportación de cola | `/adjudication/export/` entrega una fila JSONL por caso de la cola, incluso mientras hay decisiones pendientes. Incluye identificadores, hash y fila de origen, votos con historial, decisión vigente y revisiones. Solo el personal de control puede exportar. |
| Referencia candidata | `/adjudication/export/reference/` devuelve `409` hasta que todos los casos de la cola están adjudicados y todas las unidades tienen sus dos anotaciones. También bloquea con `409` si cambió cualquier anotación o evento desde la importación, si un voto adjudicado difiere de su último evento, o si alguna unidad externa a la cola carece de acuerdo actual. Solo `control` puede descargarla (una fila JSONL por unidad). No aprueba científicamente la referencia. |

## Operación local

Para pruebas locales, usar la base aislada del test suite. `--synthetic` solo se admite con `DJANGO_DEBUG=1`:

```bash
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py migrate
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py test annotations
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py check
```

Para una base real, `import_adjudication_queue --source /ruta/privada/review_queue.jsonl` exige el JSONL exacto de la cola, cuyo hash debe coincidir con el manifiesto versionado, y `set_adjudicator --username <cuenta> --enable` concede el permiso a una cuenta evaluadora sin privilegios de administración. Antes de migrar una instancia en uso, tomar una copia con [el procedimiento de backup](README.md#almacenamiento-y-copias). Tras la primera decisión real, conservar siempre `AdjudicationEvent` y la base.
