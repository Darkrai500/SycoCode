import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from annotations.models import AdjudicationQueueItem, Annotation, Assignment, Unit
from annotations.provenance import annotation_state_sha256
from annotations.services import progress


class Command(BaseCommand):
    help = ("Diseño cruzado (ReEval-2): cuando los dos evaluadores han terminado, crea la cola con las "
            "unidades cuyas etiquetas actuales difieren. La regla está fijada en el protocolo.")

    def handle(self, *args, **options):
        with transaction.atomic():
            if AdjudicationQueueItem.objects.exists():
                raise CommandError("La cola ya existe; no se cambió nada.")
            annotators = list(get_user_model().objects.filter(
                id__in=Assignment.objects.values("user_id"), is_staff=False).order_by("username"))
            if len(annotators) != 2:
                raise CommandError("La cola cruzada requiere exactamente dos cuentas con asignaciones.")
            units = list(Unit.objects.select_related("conversation").order_by("conversation__position", "id"))
            for user in annotators:
                p = progress(user)
                if p["remaining"] or p["total"] != len(units):
                    raise CommandError(f"{user.username} no ha etiquetado las {len(units)} unidades.")
            votes = {}
            for a in Annotation.objects.select_related("user"):
                votes.setdefault(a.unit_id, {})[a.user.username] = a
            names = [u.username for u in annotators]
            rows, first_disagreements = [], 0
            for unit in units:
                pair = votes.get(unit.id, {})
                if sorted(pair) != names:
                    raise CommandError(f"La unidad {unit.id} no tiene exactamente las dos anotaciones esperadas.")
                first_disagreements += pair[names[0]].first_label != pair[names[1]].first_label
                if pair[names[0]].label == pair[names[1]].label:
                    continue
                rows.append({"unit_id": unit.id, "group_id": unit.conversation_id,
                             "record_id": unit.metadata["record_id"], "judged_turn": unit.judged_turn,
                             "language": unit.conversation.language, "scenario": unit.conversation.scenario,
                             "rule": "current_labels_differ",
                             "annotations": [{"annotator": n, "first_label": pair[n].first_label,
                                              "current_label": pair[n].label, "version": pair[n].version}
                                             for n in names]})
            state = annotation_state_sha256()
            for position, row in enumerate(rows):
                digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                AdjudicationQueueItem.objects.create(unit_id=row["unit_id"], position=position, source_row=row,
                                                     source_sha256=digest, annotation_state_sha256=state)
        self.stdout.write(self.style.SUCCESS(
            f"Cola creada: {len(rows)} de {len(units)} unidades con etiquetas actuales distintas "
            f"({first_disagreements} con primeras etiquetas distintas). Estado de anotaciones {state}."))
