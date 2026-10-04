import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .models import (Adjudication, AdjudicationEvent, AdjudicationQueueItem,
                     Annotation, LABELS, Profile, Unit)
from .services import may_inspect, progress, record_exposure
from .provenance import annotation_state_sha256


def can_adjudicate(user):
    # An explicit grant: Django's generic has_perm would grant every permission
    # implicitly to the control superuser.
    return bool(user.is_authenticated and user.is_active and not user.is_staff and not user.is_superuser and
                Unit.objects.exists() and Annotation.objects.filter(user=user).count() == Unit.objects.count() and
                Profile.objects.filter(user=user, can_adjudicate=True).exists())


def can_supervise(user):
    return bool(user.is_authenticated and user.is_active and user.is_staff and
                progress(user)["remaining"] == 0)


def can_view(user):
    return can_supervise(user) or can_adjudicate(user)


def nav_access(request):
    return {"can_view_adjudication": can_view(request.user)}


def forbidden():
    return HttpResponse("No tienes acceso a la adjudicación.", status=403)


def annotation_provenance(unit):
    annotations = Annotation.objects.filter(unit=unit).select_related("user").prefetch_related("events").order_by("user__username")
    return [{"annotation_id": a.id, "annotator": a.user.username,
             "provenance": "jc_manual_review_confirmed" if a.user.username == "jc" else "external_human_annotation",
             "first_label": a.first_label, "current_label": a.label, "version": a.version,
             "note": a.note, "created_at": a.created_at.isoformat(), "updated_at": a.updated_at.isoformat(),
             "events": [{"event_id": e.id, "version": e.version, "label": e.label,
                         "note": e.note, "created_at": e.created_at.isoformat()}
                        for e in sorted(a.events.all(), key=lambda event: event.version)]} for a in annotations]


def decision_data(decision):
    if decision is None:
        return None
    return {"label": decision.label, "rationale": decision.rationale,
            "version": decision.version, "author": decision.decided_by.username,
            "decided_at": decision.decided_at.isoformat(),
            "decision_type": "individual_adjudication", "team_consensus": False,
            "display_status": "Adjudicación de JC" if decision.decided_by.username == "jc"
                              else f"Adjudicación de {decision.decided_by.username}"}


def event_data(event):
    return {"version": event.version, "label": event.label, "rationale": event.rationale,
            "author": event.author.username, "created_at": event.created_at.isoformat(),
            "request_id": str(event.request_id), "vote_snapshot": event.vote_snapshot}


def decision_for(item):
    return Adjudication.objects.select_related("decided_by").filter(unit=item.unit).first()


def queue_context(status):
    items = list(AdjudicationQueueItem.objects.select_related("unit__conversation"))
    decisions = {d.unit_id: d for d in Adjudication.objects.select_related("decided_by")}
    rows = [{"item": i, "decision": decisions.get(i.unit_id)} for i in items]
    resolved = sum(r["decision"] is not None for r in rows)
    if status == "pending":
        rows = [r for r in rows if r["decision"] is None]
    elif status == "resolved":
        rows = [r for r in rows if r["decision"] is not None]
    return {"rows": rows, "status": status, "total": len(items), "resolved": resolved,
            "pending": len(items) - resolved}


@login_required
@require_GET
def dashboard(request):
    if not can_view(request.user):
        return forbidden()
    status = request.GET.get("status", "all")
    if status not in {"all", "pending", "resolved"}:
        return HttpResponse("Filtro inválido.", status=400)
    return render(request, "adjudication_list.html", queue_context(status))


def detail_context(item, *, error=None, draft_label=None, draft_rationale=None):
    unit = item.unit
    decision = decision_for(item)
    rows = list(Annotation.objects.filter(unit=unit).select_related("user").prefetch_related("events").order_by("user__username"))
    ids = list(AdjudicationQueueItem.objects.values_list("unit_id", flat=True))
    index = ids.index(unit.id)
    return {"item": item, "unit": unit, "case": unit.conversation,
            "annotations": rows, "decision": decision,
            "history": list(decision.events.select_related("author")) if decision else [],
            "labels": LABELS, "position": index + 1, "total": len(ids),
            "previous_id": ids[index-1] if index else None,
            "next_id": ids[index+1] if index + 1 < len(ids) else None,
            "write_allowed": False, "error": error,
            "draft_label": draft_label if draft_label is not None else (decision.label if decision else ""),
            "draft_rationale": draft_rationale if draft_rationale is not None else (decision.rationale if decision else ""),
            "form_version": decision.version if decision else 0,
            "request_id": str(uuid.uuid4())}


def render_detail(request, item, *, status=200, error=None, draft_label=None, draft_rationale=None):
    context = detail_context(item, error=error, draft_label=draft_label, draft_rationale=draft_rationale)
    context["write_allowed"] = can_adjudicate(request.user)
    return render(request, "adjudication_detail.html", context, status=status)


@login_required
@require_http_methods(["GET", "POST"])
def detail(request, unit_id):
    if not can_view(request.user):
        return forbidden()
    item = get_object_or_404(AdjudicationQueueItem.objects.select_related("unit__conversation__study"), unit_id=unit_id)
    if request.method == "POST" and not can_adjudicate(request.user):
        return forbidden()
    if not may_inspect(request.user, item.unit.conversation):
        return HttpResponse("Termina primero tu evaluación independiente de este caso.", status=403)
    if request.method == "GET":
        with transaction.atomic():
            record_exposure(request.user, item.unit.conversation)
        return render_detail(request, item)

    label = request.POST.get("label", "")
    rationale = request.POST.get("rationale", "").strip()
    raw_version = request.POST.get("version", "")
    try:
        expected_version = int(raw_version)
        request_id = uuid.UUID(request.POST.get("request_id", ""))
    except (ValueError, TypeError, AttributeError):
        return render_detail(request, item, status=400, error="Versión o identificador de envío inválido.",
                             draft_label=label, draft_rationale=rationale)
    if (label not in dict(LABELS) or not rationale or len(rationale) > 5000 or
            expected_version < 0 or str(expected_version) != raw_version):
        return render_detail(request, item, status=400,
                             error="Elige una etiqueta y escribe una justificación de hasta 5.000 caracteres.",
                             draft_label=label, draft_rationale=rationale)
    try:
        with transaction.atomic():
            if annotation_state_sha256() != item.annotation_state_sha256:
                return render_detail(request, item, status=409,
                                     error="Las anotaciones cambiaron desde el corte de la cola. Se requiere un corte nuevo antes de decidir.",
                                     draft_label=label, draft_rationale=rationale)
            record_exposure(request.user, item.unit.conversation)
            duplicate = AdjudicationEvent.objects.select_related("adjudication", "author").filter(request_id=request_id).first()
            if duplicate:
                if (duplicate.adjudication.unit_id == unit_id and duplicate.author_id == request.user.id and
                        duplicate.label == label and duplicate.rationale == rationale):
                    return redirect("adjudication_detail", unit_id=unit_id)
                return render_detail(request, item, status=409, error="Este identificador de envío ya se usó.",
                                     draft_label=label, draft_rationale=rationale)
            current = Adjudication.objects.select_for_update().filter(unit=item.unit).first()
            if (current.version if current else 0) != expected_version:
                return render_detail(request, item, status=409,
                                     error="La decisión cambió en otra pestaña. Compara la versión guardada antes de volver a enviar.",
                                     draft_label=label, draft_rationale=rationale)
            if current and current.label == label and current.rationale == rationale:
                return redirect("adjudication_detail", unit_id=unit_id)
            now = timezone.now()
            snapshot = annotation_provenance(item.unit)
            if current:
                next_version = current.version + 1
                changed = Adjudication.objects.filter(pk=current.pk, version=expected_version).update(
                    label=label, rationale=rationale, version=F("version") + 1,
                    decided_by=request.user, decided_at=now)
                if changed != 1:
                    return render_detail(request, item, status=409, error="La decisión cambió; recarga la página.",
                                         draft_label=label, draft_rationale=rationale)
            else:
                next_version = 1
                current = Adjudication.objects.create(unit=item.unit, label=label, rationale=rationale,
                    version=1, decided_by=request.user, decided_at=now)
            AdjudicationEvent.objects.create(adjudication=current, version=next_version,
                label=label, rationale=rationale, author=request.user, created_at=now,
                request_id=request_id, vote_snapshot=snapshot)
    except IntegrityError:
        return render_detail(request, item, status=409,
                             error="La decisión cambió durante el guardado. Comprueba la versión actual.",
                             draft_label=label, draft_rationale=rationale)
    messages.success(request, "Adjudicación guardada con autor, fecha y versión.")
    return redirect("adjudication_detail", unit_id=unit_id)


def export_row(item, current_annotation_sha256):
    unit = item.unit
    case = unit.conversation
    decision = decision_for(item)
    return {"schema_version": "sycocode-adjudication-v1",
            "unit_id": unit.id, "group_id": case.id,
            "record_id": unit.metadata["record_id"], "judged_turn": unit.judged_turn,
            "language": case.language, "scenario": case.scenario,
            "rubric_version": case.study.rubric_version,
            "study_sha256": case.study.fingerprint, "payload_sha256": case.source_sha256,
            "queue_source_sha256": item.source_sha256, "queue_source_row": item.source_row,
            "annotation_state_sha256": item.annotation_state_sha256,
            "current_annotation_sha256": current_annotation_sha256,
            "annotation_state_matches": item.annotation_state_sha256 == current_annotation_sha256,
            "annotations": annotation_provenance(unit),
            "decision": decision_data(decision),
            "events": [event_data(e) for e in decision.events.select_related("author")] if decision else []}


def jsonl_response(rows, filename):
    response = HttpResponse("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                            content_type="application/x-ndjson; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_GET
def export_decisions(request):
    if not can_supervise(request.user):
        return forbidden()
    if progress(request.user)["remaining"]:
        return HttpResponse("Termina tus asignaciones antes de exportar votos ajenos.", status=403)
    with transaction.atomic():
        items = list(AdjudicationQueueItem.objects.select_related("unit__conversation__study"))
        current_digest = annotation_state_sha256()
        for case_id in {i.unit.conversation_id for i in items}:
            record_exposure(request.user, next(i.unit.conversation for i in items if i.unit.conversation_id == case_id))
        rows = [export_row(i, current_digest) for i in items]
    return jsonl_response(rows, "sycocode-reeval-adjudications.jsonl")


@login_required
@require_GET
def export_reference(request):
    if not can_supervise(request.user):
        return forbidden()
    with transaction.atomic():
        items = list(AdjudicationQueueItem.objects.select_related("unit__conversation__study"))
        if (len(items) != 42 or Unit.objects.count() != 320 or Annotation.objects.count() != 640 or
                Adjudication.objects.filter(unit__in=[i.unit for i in items]).count() != 42):
            return HttpResponse("La referencia candidata exige 42 decisiones y 320 unidades con dos anotaciones.", status=409)
        frozen_hashes = {item.annotation_state_sha256 for item in items}
        if len(frozen_hashes) != 1 or not next(iter(frozen_hashes)) or annotation_state_sha256() not in frozen_hashes:
            return HttpResponse("Las anotaciones cambiaron desde el corte congelado; la referencia requiere un corte nuevo.", status=409)
        by_unit = {i.unit_id: i for i in items}
        rows = []
        for unit in Unit.objects.select_related("conversation__study").order_by("id"):
            case = unit.conversation
            record_exposure(request.user, case)
            votes = annotation_provenance(unit)
            names = [vote["annotator"] for vote in votes]
            if len(votes) != 2 or names.count("jc") != 1 or len(set(names)) != 2:
                return HttpResponse(f"Autoría incompleta en {unit.id}.", status=409)
            if unit.id in by_unit:
                item = by_unit[unit.id]
                decision = decision_for(item)
                latest = decision.events.order_by("-version").first()
                if (latest is None or latest.vote_snapshot != votes or
                        (decision.version, decision.label, decision.rationale,
                         decision.decided_by_id, decision.decided_at) !=
                        (latest.version, latest.label, latest.rationale,
                         latest.author_id, latest.created_at)):
                    return HttpResponse(f"La trazabilidad de {unit.id} cambió tras su adjudicación; requiere revisión.", status=409)
                label, source = decision.label, "individual_adjudication"
                decision_info = decision_data(decision)
                queue_sha = item.source_sha256
            else:
                if votes[0]["current_label"] != votes[1]["current_label"]:
                    return HttpResponse(f"Desacuerdo fuera de la cola en {unit.id}; revise el corte.", status=409)
                label, source = votes[0]["current_label"], "current_pair_agreement"
                decision_info, queue_sha = None, None
            rows.append({"schema_version": "sycocode-reeval-reference-candidate-v1",
                "reference_status": "candidate_human_policy_42_plus_278", "unit_id": unit.id,
                "group_id": case.id, "record_id": unit.metadata["record_id"],
                "judged_turn": unit.judged_turn, "reference_label": label,
                "label_source": source, "team_consensus": False,
                "decision": decision_info, "annotations": votes,
                "queue_source_sha256": queue_sha,
                "rubric_version": case.study.rubric_version,
                "study_sha256": case.study.fingerprint, "payload_sha256": case.source_sha256})
    return jsonl_response(rows, "sycocode-reeval-reference-candidate.jsonl")
