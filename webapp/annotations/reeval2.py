"""Crossed design (ReEval-2): roles, the access policy and the hand-in -> queue -> closure flow.

The study runs without the first author: each annotator hands in, the second
hand-in cuts the queue, the adjudicator closes it, and closure opens the downloads.
"""
import hashlib
import json

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (Adjudication, AdjudicationQueueItem, Annotation, Assignment, Profile, Study,
                     StudyEvent, Submission, Unit)
from .provenance import annotation_state_sha256

CONTROL, EVALUATOR, ADJUDICATOR = "control", "evaluator", "adjudicator"
# Stored with each hand-in, so the wording the annotator accepted can be cited.
DECLARATION_VERSION = "reeval2-1"
DECLARATION = {"individual": "He etiquetado las respuestas yo solo o sola, sin ayuda de otra persona.",
               "no_ai": "No he usado ninguna IA ni herramienta automática para decidir las etiquetas.",
               "no_discussion": "No he hablado de los casos con nadie, ni con el resto del equipo ni con los autores."}
_COMMON = {"login", "logout", "password", "home", "guide"}
_ROUTES = {EVALUATOR: _COMMON | {"evaluate", "save", "submit", "calibration", "calibration_case"},
           ADJUDICATOR: _COMMON | {"calibration", "calibration_case", "adjudicator_guide", "adjudication_dashboard",
                                   "adjudication_detail", "adjudication_close"},
           CONTROL: _COMMON | {"control"}}
_CONTROL_AFTER_CLOSURE = {"export", "adjudication_export"}


def crossed_study():
    return Study.objects.filter(design="crossed").first()


def study_role(user):
    if not user.is_authenticated:
        return ""
    return Profile.objects.filter(user=user).values_list("study_role", flat=True).first() or ""


def allowed_routes(user, study):
    role = study_role(user)
    routes = _ROUTES.get(role, {"login", "logout", "password"})
    if role == CONTROL and study.closed_at:
        return routes | _CONTROL_AFTER_CLOSURE
    return routes


def state(study):
    if study.closed_at:
        return "closed"
    return "adjudication" if study.queue_cut_at else "annotation"


def own_annotations_sha256(user):
    rows = [{"unit_id": a.unit_id, "first_label": a.first_label, "label": a.label, "note": a.note, "version": a.version,
             "events": [[e.version, e.label, e.note] for e in sorted(a.events.all(), key=lambda e: e.version)]}
            for a in Annotation.objects.filter(user=user).prefetch_related("events").order_by("unit_id")]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evaluators():
    return get_user_model().objects.filter(id__in=Assignment.objects.values("user_id")).order_by("username")


def queue_rows(annotators):
    """Units whose two current labels differ. The rule is fixed in the protocol, section 4."""
    names = [u.username for u in annotators]
    votes = {}
    for a in Annotation.objects.select_related("user"):
        votes.setdefault(a.unit_id, {})[a.user.username] = a
    rows = []
    for unit in Unit.objects.select_related("conversation").order_by("conversation__position", "id"):
        pair = votes.get(unit.id, {})
        if sorted(pair) != names:
            raise ValueError(f"La unidad {unit.id} no tiene exactamente las dos anotaciones esperadas.")
        if pair[names[0]].label == pair[names[1]].label:
            continue
        rows.append({"unit_id": unit.id, "group_id": unit.conversation_id,
                     "record_id": unit.metadata["record_id"], "judged_turn": unit.judged_turn,
                     "language": unit.conversation.language, "scenario": unit.conversation.scenario,
                     "rule": "current_labels_differ",
                     "annotations": [{"annotator": n, "first_label": pair[n].first_label,
                                      "current_label": pair[n].label, "version": pair[n].version} for n in names]})
    return rows


def advance_after_submission(study):
    """Call inside the hand-in's transaction: the last hand-in cuts the queue, and an empty queue closes the study."""
    annotators = list(evaluators())
    if study.queue_cut_at or Submission.objects.filter(user__in=annotators).count() != len(annotators):
        return
    frozen = annotation_state_sha256()
    for position, row in enumerate(queue_rows(annotators)):
        digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        AdjudicationQueueItem.objects.create(unit_id=row["unit_id"], position=position, source_row=row,
                                             source_sha256=digest, annotation_state_sha256=frozen)
    study.queue_cut_at = timezone.now()
    study.save(update_fields=["queue_cut_at"])
    StudyEvent.objects.create(kind="queue_cut", actor="system", detail={"annotation_state_sha256": frozen})
    if not AdjudicationQueueItem.objects.exists():
        close_study(study, "system")


def pending_decisions():
    return AdjudicationQueueItem.objects.exclude(unit__in=Adjudication.objects.values("unit")).count()


def close_study(study, actor):
    study.closed_at = timezone.now()
    study.save(update_fields=["closed_at"])
    StudyEvent.objects.create(kind="closed", actor=actor, detail={"annotation_state_sha256": annotation_state_sha256()})


def export_sha256(content):
    return hashlib.sha256(content.encode()).hexdigest()
