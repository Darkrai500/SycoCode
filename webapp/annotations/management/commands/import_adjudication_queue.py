import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from annotations.models import AdjudicationQueueItem, Annotation, Unit
from annotations.provenance import annotation_state_sha256


MANIFEST_PATH = settings.BASE_DIR / "annotations/data/reeval_queue_manifest_2026-09-24.json"
REQUIRED = {"unit_id", "group_id", "record_id", "judged_turn", "language", "scenario",
            "external_annotator", "jc_reviewed", "external_first", "external_current",
            "external_first_before_clarification", "payload_path", "adjudicated_label",
            "adjudicator", "rationale", "status"}
LABELS = {"firm", "hedged", "capitulated"}


class Command(BaseCommand):
    help = "Importa una cola privada tras contrastarla con el manifiesto versionado y los votos del servidor."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, required=True,
                            help="JSONL privado del corte ReEval; no se incluye en Git.")
        parser.add_argument("--synthetic", action="store_true",
                            help="Solo para pruebas con DEBUG: omite el manifiesto real de 42 casos.")

    def handle(self, *args, **options):
        synthetic = options["synthetic"]
        if synthetic and not settings.DEBUG:
            raise CommandError("--synthetic solo está permitido con DJANGO_DEBUG=1.")
        try:
            manifest = json.loads(MANIFEST_PATH.read_text())
            if (set(manifest) != {"schema_version", "source_sha256", "study_sha256",
                                  "annotations_sha256", "rubric_version", "queue_count",
                                  "first_disagreements", "current_disagreements", "external_edits"} or
                    manifest["schema_version"] != "sycocode-reeval-queue-manifest-v1" or
                    manifest["queue_count"] != 42):
                raise ValueError("Manifiesto versionado inválido.")
            raw = options["source"].read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
            if not synthetic:
                if digest != manifest["source_sha256"]:
                    raise ValueError("El JSONL privado no coincide con el SHA-256 del manifiesto.")
                if len(rows) != manifest["queue_count"]:
                    raise ValueError("El número de unidades difiere del manifiesto.")
            if not rows or len({r["unit_id"] for r in rows}) != len(rows):
                raise ValueError("La cola está vacía o contiene unidades duplicadas.")
            with transaction.atomic():
                if not synthetic and (Unit.objects.count() != 320 or Annotation.objects.count() != 640):
                    raise ValueError("La cola real exige 320 unidades y 640 anotaciones.")
                prepared = []
                for position, row in enumerate(rows, 1):
                    if set(row) != REQUIRED or row["status"] != "pending_human_review":
                        raise ValueError(f"Formato o estado inesperado en la fila {position}.")
                    if any(row[key] is not None for key in ("adjudicated_label", "adjudicator", "rationale")):
                        raise ValueError("El JSONL de entrada no debe contener decisiones.")
                    if any(row[key] not in LABELS for key in ("jc_reviewed", "external_first", "external_current")):
                        raise ValueError("Etiqueta original inválida.")
                    if type(row["external_first_before_clarification"]) is not bool:
                        raise ValueError("Bandera de aclaración inválida.")
                    if not (row["jc_reviewed"] != row["external_first"] or
                            row["jc_reviewed"] != row["external_current"] or
                            row["external_first"] != row["external_current"]):
                        raise ValueError("La fila no pertenece a la unión de desacuerdos y revisiones.")
                    unit = Unit.objects.select_related("conversation__study").filter(pk=row["unit_id"]).first()
                    if unit is None:
                        raise ValueError(f"No existe la unidad {row['unit_id']}.")
                    case = unit.conversation
                    expected = (case.id, unit.metadata.get("record_id"), unit.judged_turn,
                                case.language, case.scenario, unit.metadata.get("payload_path"))
                    observed = tuple(row[k] for k in ("group_id", "record_id", "judged_turn",
                                                      "language", "scenario", "payload_path"))
                    if observed != expected:
                        raise ValueError(f"Identificadores o payload no coinciden en {unit.id}.")
                    if not synthetic and (case.study.fingerprint != manifest["study_sha256"] or
                                          case.study.rubric_version != manifest["rubric_version"]):
                        raise ValueError(f"Estudio o rúbrica distintos en {unit.id}.")
                    votes = list(Annotation.objects.filter(unit=unit).select_related("user"))
                    by_user = {a.user.username: a for a in votes}
                    if len(votes) != 2 or set(by_user) != {"jc", row["external_annotator"]}:
                        raise ValueError(f"Autoría original inesperada en {unit.id}.")
                    jc, external = by_user["jc"], by_user[row["external_annotator"]]
                    if (jc.label != row["jc_reviewed"] or external.first_label != row["external_first"] or
                            external.label != row["external_current"]):
                        raise ValueError(f"Los votos del servidor difieren del corte en {unit.id}.")
                    prepared.append(AdjudicationQueueItem(unit=unit, position=position,
                        source_row=row, source_sha256=digest))
                if not synthetic:
                    self._verify_full_union(rows, manifest)
                state_hash = annotation_state_sha256()
                if not synthetic and state_hash != manifest["annotations_sha256"]:
                    raise ValueError("Las anotaciones o sus eventos cambiaron desde el corte.")
                for item in prepared:
                    item.annotation_state_sha256 = state_hash
                existing = list(AdjudicationQueueItem.objects.order_by("position"))
                if existing:
                    if len(existing) != len(prepared) or any(
                        a.unit_id != b.unit_id or a.position != b.position or
                        a.source_row != b.source_row or a.source_sha256 != b.source_sha256 or
                        a.annotation_state_sha256 != b.annotation_state_sha256
                        for a, b in zip(existing, prepared)
                    ):
                        raise ValueError("Ya existe otra cola; no se modifica ni se mezclan cohortes.")
                    self.stdout.write("La cola ya está cargada y coincide; sin cambios.")
                    return
                AdjudicationQueueItem.objects.bulk_create(prepared)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f"Cola no importada: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Cargadas {len(prepared)} unidades; cero adjudicaciones creadas."))

    @staticmethod
    def _verify_full_union(rows, manifest):
        union, first_disagreements, current_disagreements, external_edits = set(), 0, 0, 0
        for unit in Unit.objects.prefetch_related("annotations__user"):
            votes = list(unit.annotations.all())
            by_user = {a.user.username: a for a in votes}
            if len(votes) != 2 or "jc" not in by_user or len(by_user) != 2:
                raise ValueError(f"Se esperan JC y un evaluador externo en {unit.id}.")
            jc = by_user.pop("jc")
            external = next(iter(by_user.values()))
            first_diff = jc.label != external.first_label
            current_diff = jc.label != external.label
            edited = external.first_label != external.label
            first_disagreements += first_diff
            current_disagreements += current_diff
            external_edits += edited
            if first_diff or current_diff or edited:
                union.add(unit.id)
        expected_counts = (manifest["first_disagreements"], manifest["current_disagreements"],
                           manifest["external_edits"])
        if (union != {row["unit_id"] for row in rows} or
                (first_disagreements, current_disagreements, external_edits) != expected_counts):
            raise ValueError("La unión o los recuentos 39/35/11 cambiaron desde el corte; crear un corte nuevo.")
