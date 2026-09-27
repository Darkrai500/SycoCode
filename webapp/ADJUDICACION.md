# Adjudicación humana de ReEval

## Alcance y estado

La utilidad permite que una persona identificada con su propia cuenta decida la etiqueta final de cada unidad de la [cola de revisión del 24/09/2026](../data/ReEval/analysis-2026-09-24-manual-reviewed/followup/review_queue.md). La cola contiene **42 unidades**: 35 desacuerdos entre las etiquetas actuales de JC y la persona externa, y siete casos que ahora coinciden pero tuvieron un desacuerdo o una edición anterior. La revisión manual de JC de las 320 respuestas está realizada y confirmada; la adjudicación es una decisión posterior y distinta.

La utilidad está implementada en la rama local. Antes de usarla en la instancia existente hay que revisar la migración, el manifiesto, los permisos reales, las pruebas y el despliegue con el procedimiento de este documento. La cola histórica, sus JSONL, las anotaciones y `data/goldset/gold.jsonl` son evidencia de entrada: no se rellenan ni sustituyen para guardar decisiones. El JSONL de la cola contiene identificadores, nombres de cuenta y votos: se mantiene ignorado por Git y se copia por separado a una ruta privada del servidor.

## Decisión de diseño

| Elemento | Regla |
|---|---|
| Unidad de decisión | `unit_id` de `Unit`, enlazado a `group_id`, `record_id` y `judged_turn`. La conversación se lee de la muestra ya importada. |
| Cola congelada | Solo se versiona `webapp/annotations/data/reeval_queue_manifest_2026-09-24.json`, con hashes, versión de rúbrica y recuentos; no contiene identificadores de unidad, nombres ni votos. `import_adjudication_queue --source /ruta/privada/review_queue.jsonl` exige el JSONL completo fuera del repositorio. Dentro de una transacción coteja su SHA-256, el estudio, la rúbrica, el estado de 640 anotaciones y sus 651 eventos, los identificadores/votos y la unión de 42 casos con recuentos 39/35/11. Una discrepancia deja la cola sin importar. |
| Identidad y acceso | `Profile.can_adjudicate` habilita la decisión para una cuenta evaluadora concreta. El comando de concesión exige que haya completado las 320 unidades y rechaza `is_staff`/`is_superuser`. La cuenta `jc` conserva ambos indicadores desactivados. `control` supervisa y exporta; no adjudica. Las comprobaciones de acceso se hacen en el servidor en cada petición. |
| Interfaz | `/adjudication/` permite recorrer y filtrar pendientes/resueltos; `/adjudication/<unit_id>/` muestra conversación, rúbrica, primer voto, etiqueta actual e historial de ambos anotadores, y exige una de las tres etiquetas con justificación para guardar. |
| Persistencia | `AdjudicationQueueItem` registra la pertenencia a la cola; `Adjudication` mantiene la decisión vigente; `AdjudicationEvent` registra cada creación o revisión con etiqueta, justificación, cuenta, fecha y versión. `Annotation` y `AnnotationEvent` conservan los votos originales. |
| Concurrencia e integridad | La petición lleva versión y UUID de envío. Una versión obsoleta devuelve `409`; repetir exactamente un envío ya confirmado no crea otra revisión. Un POST de decisión devuelve `409` si el estado de anotaciones/historial difiere del corte importado. La protección CSRF y la validación de etiqueta/justificación se aplican en el servidor. |
| Exportación de cola | `/adjudication/export/` entrega 42 filas JSONL, incluso mientras hay decisiones pendientes. Incluye identificadores, hash y fila de origen, votos con historial, decisión vigente y revisiones. Solo el personal de control puede exportar. |
| Referencia candidata | `/adjudication/export/reference/` devuelve `409` hasta reunir las 42 adjudicaciones, 320 unidades y 640 anotaciones. También bloquea con `409` si cambió cualquier anotación o evento desde la importación, si un voto adjudicado difiere de su último evento, o si alguna de las 278 unidades externas a la cola carece de acuerdo actual. Solo `control` puede descargar sus 320 filas JSONL. No aprueba científicamente la referencia. |

El [panel de control existente](README.md#exportaciones) marca desacuerdo comparando **primeros votos**. No representa la cola vigente de 42 ni los 35 desacuerdos entre etiquetas actuales. La adjudicación se presenta en una vista propia para evitar esa confusión.

El [informe del corte del 24/09/2026](../data/ReEval/README.md) registra `control` con `is_staff=1` e `is_superuser=1`, y `jc` con ambos valores en `0`; una comprobación de solo lectura del 27/09 confirmó que siguen así. El inicializador de un equipo nuevo crea ahora `lead` sin administración, como la cuenta `jc` existente. Antes de activar la utilidad se verifican de nuevo los permisos efectivos en la base desplegada. Conceder `can_adjudicate` no debe otorgar administración general.

Una decisión tomada solo por JC se identifica como **«adjudicación de JC»**, aunque coincida con cualquiera de los votos. No es consenso del equipo ni una tercera evaluación independiente. Las tres personas externas trabajaron en particiones disjuntas: cada unidad tiene revisión de JC y una evaluación externa, sin voto mayoritario de cuatro personas. [Procedencia y acuerdo](../data/ReEval/README.md#2-procedencia-y-diseño-real).

## Política fijada para una referencia completa del piloto

La política de construcción se fija **antes** de comparar el panel o calcular κ:

1. Cerrar explícitamente las **42** filas de la cola mediante una etiqueta final y justificación humanas. Los siete casos hoy concordantes también se revisan, porque entraron en la cola por su historia de voto.
2. Para esas 42 unidades usar la **última decisión adjudicada**, con referencia al evento, cuenta, fecha, justificación y ambos historiales de anotación.
3. Para las otras **278** unidades usar la etiqueta actual en la que coinciden JC y su único evaluador externo. Identificar su origen como `current_pair_agreement`, con nombres, etiquetas y versiones; no llamarlas adjudicadas. Las 42 restantes llevan `individual_adjudication`.
4. Exigir exactamente 320 `unit_id` distintos, un `record_id` y `judged_turn` correspondientes por fila, las dos anotaciones esperadas y ningún caso pendiente. Si las anotaciones o la muestra difieren del corte congelado, detener la construcción y documentar un corte nuevo en vez de mezclar silenciosamente estados.
5. Descargar el JSONL de **referencia candidata** desde `/adjudication/export/reference/`. Para aprobarlo como referencia del análisis, conservarlo como artefacto nuevo y versionado junto con un manifiesto de política, fecha de corte, hashes de entrada y conteos por fuente. El endpoint no sustituye `data/goldset/gold.jsonl` ni aprueba el artefacto. Preservar los exports previos, los primeros votos y todas las revisiones.

Esta referencia de 320 unidades corresponde solo al piloto de `full`/gpt-oss. No convierte la muestra en reservada ni reemplaza automáticamente las 24.000 etiquetas históricas de la cohorte. Tampoco valida los otros nueve modelos. La elección de referencia y la evaluación posterior del panel no se basan en cuál produzca mejor κ. Hasta cerrar las 42 decisiones y aprobar el artefacto derivado, los escenarios de primeros votos y votos actuales siguen siendo **sensibilidades sin adjudicación**. [Estado científico y editorial](../data/ReEval/README.md#4-panel-automático-frente-a-la-nueva-referencia-externa).

La confirmación de recepción y aplicación de la aclaración del 21/09 por las dos personas pendientes es otra cuestión. `rubric_version=1.1`, sus guardados y una decisión de adjudicación no acreditan recepción. La utilidad puede señalar el [acta documental](../data/ReEval/PROTOCOL_CLOSURE.md), cuyo estado permanece abierto hasta obtener evidencia o documentar expresamente la limitación.

## Operación local y preparación de despliegue

Para pruebas locales, usar la base aislada del test suite. `--synthetic` solo se admite con `DJANGO_DEBUG=1` y no permite saltarse el manifiesto en producción:

```bash
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py migrate
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py test annotations
DJANGO_DEBUG=1 webapp/.venv/bin/python webapp/manage.py check
```

Para una copia **privada** de la base completa, el comando exige `--source` con el JSONL exacto del corte; el hash del archivo debe coincidir con el manifiesto versionado. En la instancia existente, **no** volver a ejecutar `setup_team` ni `import_pool` para rehacer cuentas o asignaciones. El permiso se concede a la cuenta `jc` existente y se comprueba que `is_staff` e `is_superuser` continúan desactivados. No crear decisiones de prueba en la base real.

Pasos para revisión antes de promover el release:

1. Confirmar rama, diff y árbol que se va a subir; conservar los cambios locales ajenos y revisar que no entren credenciales, snapshots privados, el JSONL completo de la cola, exports, sesiones ni datos operativos. Comprobar que la release solo contiene el manifiesto agregado y que sus hashes/recuentos coinciden con el corte privado.
2. Tomar un backup consistente de SQLite con [el procedimiento de backup](README.md#almacenamiento-y-copias), probar integridad y capacidad de restauración, y registrar versión de aplicación, base y hora. La migración debe añadir tablas/campos sin modificar anotaciones previas.
3. Seguir el runbook privado de la instalación **systemd**: preparar una release nueva con su entorno virtual y `collectstatic`, copiar el JSONL mediante el canal privado a una ruta fuera del checkout/release con acceso restringido al servicio y tomar backup. Detener `sycocode`, cambiar el enlace `/opt/sycocode/current` a la release nueva, ejecutar `sudo sycocode-manage migrate --noinput` (el wrapper usa `current`) e importar la cola antes de arrancar el servicio. Caddy continúa como proxy; no usar Docker Compose para actualizar esta instancia.
4. Ejecutar `import_adjudication_queue --source /ruta/privada/review_queue.jsonl` en la release nueva. Comprobar 42 filas, 39 desacuerdos iniciales, 35 actuales, 11 ediciones externas y cero decisiones; repetir el comando debe confirmar coincidencia sin cambios. Un SHA, voto, estudio, historial o unión distintos deben detener la importación completa.
5. Habilitar `can_adjudicate` solo para `jc` con `set_adjudicator --username jc --enable`; releer permisos efectivos de `jc` y `control`. Comprobar en HTTP que JC puede ver/decidir con su cuenta, que los colaboradores reciben `403` y que `control` puede supervisar/exportar pero obtiene `403` al intentar guardar una decisión.
6. Verificar en escritorio y móvil la lista, filtros, conversación, rúbrica, primeros votos, etiquetas actuales, historial, guardado y estado de conflicto en una base de prueba. En producción, descargar el JSONL de **42 filas sin decisiones** y comprobar sus claves/identificadores; `/adjudication/export/reference/` debe devolver `409` hasta cerrar las 42. No enviar una adjudicación de prueba en la base real.
7. Comprobar `systemctl status sycocode caddy`, `sycocode-manage check --deploy` y health check. Registrar versión, hash de manifiesto y resultado de los tests. Comunicar la URL y el estado real solo después de estas comprobaciones.

Si la promoción falla antes de decisiones humanas, restaurar el release anterior manteniendo una copia de la base migrada. Tras la primera decisión real, preservar siempre `AdjudicationEvent` y la base; no revertir la migración ni restaurar un backup anterior sobre decisiones nuevas sin reconciliación documentada. Los comandos de servicio y rutas exactas del VPS deben cotejarse con la instalación actual antes de ejecutarlos.
