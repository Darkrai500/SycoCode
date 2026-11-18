import csv
import hashlib
import io
import json
from datetime import timedelta
from functools import wraps
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from . import reeval2
from .models import (Annotation, AnnotationEvent, Assignment, Conversation, ExportRecord,
                     Exposure, LABELS, LoginFailure, Profile, StudyEvent, Submission, Unit)
from .services import agreement_report, may_inspect, progress, queue, record_exposure
from eval.verbal import strip_code

def staff_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponse("Acceso reservado al equipo de control.", status=403)
        return view(request, *args, **kwargs)
    return wrapped

def sign_in(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        username = request.POST.get("username", "").strip().casefold()
        ip = request.META.get("REMOTE_ADDR", "")
        keys = [hashlib.sha256(("user:"+username).encode()).hexdigest(), hashlib.sha256(("ip:"+ip).encode()).hexdigest()]
        cutoff = timezone.now() - timedelta(minutes=15)
        with transaction.atomic():
            LoginFailure.objects.filter(created_at__lt=cutoff).delete()
            blocked = (LoginFailure.objects.filter(key=keys[0]).count() >= 10 or
                       LoginFailure.objects.filter(key=keys[1]).count() >= 100)
            if not blocked:
                LoginFailure.objects.bulk_create([LoginFailure(key=k) for k in keys])
        if blocked:
            return render(request, "login.html", {"form": form, "throttled": True}, status=429)
        if form.is_valid():
            LoginFailure.objects.filter(key=keys[0]).delete()
            login(request, form.get_user())
            return redirect("home")
    return render(request, "login.html", {"form": form})

@login_required
def password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        Profile.objects.update_or_create(user=user, defaults={"must_change_password": False})
        messages.success(request, "Contraseña actualizada. Ya puedes empezar.")
        return redirect("home")
    return render(request, "password.html", {"form": form})

@login_required
def home(request):
    study = reeval2.crossed_study()
    if study:
        role = reeval2.study_role(request.user)
        if role == reeval2.ADJUDICATOR:
            return redirect("adjudication_dashboard")
        if role == reeval2.CONTROL:
            return redirect("control")
    items = queue(request.user)
    pending = [i for i in items if not i["complete"]]
    completed = [i for i in items if i["complete"]]
    if not items and request.user.is_staff:
        return redirect("control")
    template = "home_reeval2.html" if study else "home.html"
    return render(request, template, {"progress": progress(request.user), "next": pending[0] if pending else None,
                                        "submission": Submission.objects.filter(user=request.user).first(),
                                        "pending": pending, "completed": completed})

@login_required
def guide(request):
    return render(request, "guide_reeval2.html" if reeval2.crossed_study() else "guide.html")

@login_required
def adjudicator_guide(request):
    return render(request, "guide_adjudicator.html")

@login_required
def evaluate(request, group_id):
    assignment = get_object_or_404(Assignment.objects.select_related("conversation"), user=request.user, conversation_id=group_id)
    case = assignment.conversation
    submitted = Submission.objects.filter(user=request.user).exists()
    own = {a.unit_id: a for a in Annotation.objects.filter(user=request.user, unit__conversation=case)}
    by_turn = {u.judged_turn: u for u in case.units.all()}
    last_judged = max(by_turn, default=0)
    turns = []
    for original in case.turns:
        turn = dict(original)
        # ReEval-2 shows the judges' whole ladder; assistant turns after the one to label are context.
        turn["after_judged"] = turn["turn"] > last_judged
        if turn["role"] == "user":
            stripped = strip_code(turn["text"])
            turn["verbal_text"] = stripped.text
            turn["has_code"] = stripped.had_code
        if turn["judged"]:
            unit = by_turn[turn["turn"]]
            turn["unit"] = unit
            turn["annotation"] = own.get(unit.id)
        turns.append(turn)
    items = queue(request.user)
    index = next(i for i, item in enumerate(items) if item["case"].id == group_id)
    next_pending = next((i for i in items[index+1:]+items[:index] if not i["complete"]), None)
    return render(request, "evaluate.html", {"case": case, "turns": turns, "labels": LABELS,
        "progress": progress(request.user), "position": index+1, "group_count": len(items),
        "next_case": next_pending, "complete": len(own) == len(by_turn),
        "submitted": submitted, "single_turn": bool(reeval2.crossed_study()) and last_judged == 1,
        "locked": submitted or Exposure.objects.filter(user=request.user, conversation=case).exists()})

@login_required
@require_http_methods(["GET", "POST"])
def submit(request):
    """Final hand-in of the crossed design: requires every unit, a dated declaration, and locks the labels."""
    study = reeval2.crossed_study()
    if study is None or reeval2.study_role(request.user) != reeval2.EVALUATOR:
        return HttpResponse(status=403)
    context = {"progress": progress(request.user), "declaration": reeval2.DECLARATION,
               "submission": Submission.objects.filter(user=request.user).first()}
    if request.method == "GET":
        return render(request, "submit.html", context)
    accepted = all(request.POST.get(key) == "on" for key in [*reeval2.DECLARATION, "final"])
    with transaction.atomic():
        if Submission.objects.filter(user=request.user).exists():
            return redirect("home")
        if progress(request.user)["remaining"]:
            context["error"] = "Faltan respuestas por etiquetar. Termínalas antes de entregar."
            return render(request, "submit.html", context, status=409)
        if not accepted:
            context["error"] = "Para entregar debes marcar todas las casillas."
            return render(request, "submit.html", context, status=400)
        Submission.objects.create(user=request.user, annotations_sha256=reeval2.own_annotations_sha256(request.user),
                                  declaration_version=reeval2.DECLARATION_VERSION, declaration=reeval2.DECLARATION)
        reeval2.advance_after_submission(study)
    # The same message for both annotators: it must not reveal whether the study moved on.
    messages.success(request, "Entrega registrada. Tus etiquetas ya no se pueden cambiar. Gracias.")
    return redirect("home")

@login_required
@require_POST
def save(request, unit_id):
    unit = get_object_or_404(Unit, pk=unit_id, conversation__assignments__user=request.user)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError()
        label, note, version = body.get("label"), body.get("note", ""), body.get("version")
        if label not in dict(LABELS) or not isinstance(note, str) or len(note) > 1000 or type(version) is not int or version < 0:
            raise ValueError()
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Selecciona una etiqueta válida. La nota admite hasta 1.000 caracteres."}, status=400)
    with transaction.atomic():
        if not Assignment.objects.filter(user=request.user, conversation=unit.conversation).exists():
            return JsonResponse({"error": "Esta conversación ya no está asignada a tu cuenta."}, status=403)
        if Submission.objects.filter(user=request.user).exists():
            return JsonResponse({"error": "Ya has entregado. Tus etiquetas no se pueden cambiar."}, status=403)
        if Exposure.objects.filter(user=request.user, conversation=unit.conversation).exists():
            return JsonResponse({"error": "Ya has consultado otras evaluaciones de este caso. Tu evaluación independiente está cerrada."}, status=403)
        current = Annotation.objects.select_for_update().filter(user=request.user, unit=unit).first()
        # Retrying a successful request after a lost response is safe and does not create an extra event.
        if current and current.label == label and current.note == note and version in [current.version, current.version-1]:
            return JsonResponse({"ok": True, "version": current.version, "saved_at": current.updated_at.isoformat()})
        if (current.version if current else 0) != version:
            return JsonResponse({"error": "Esta respuesta cambió en otra pestaña. Recarga para ver la versión guardada; tu nota sigue en pantalla."}, status=409)
        if current:
            current.label, current.note = label, note
            current.version += 1
            current.save(update_fields=["label", "note", "version", "updated_at"])
        else:
            current = Annotation.objects.create(user=request.user, unit=unit, label=label, first_label=label, note=note)
        AnnotationEvent.objects.create(annotation=current, label=label, note=note, version=current.version)
    return JsonResponse({"ok": True, "version": current.version, "saved_at": current.updated_at.isoformat()})

@staff_required
def control(request):
    study = reeval2.crossed_study()
    if study:
        return control_crossed(request, study)
    people = [{"user": user, "progress": progress(user)} for user in get_user_model().objects.order_by("id")]
    language = request.GET.get("language", "")
    state = request.GET.get("state", "")
    cases = Conversation.objects.prefetch_related("units__annotations", "assignments")
    if language in ["es", "en"]:
        cases = cases.filter(language=language)
    records = []
    for case in cases:
        units = list(case.units.all())
        rows = [a for u in units for a in u.annotations.all()]
        expected = len(units) * case.assignments.count()
        visible = may_inspect(request.user, case)
        different = any(len({a.first_label for a in u.annotations.all()}) > 1 for u in units) if visible else None
        status = "complete" if expected and len(rows) == expected else "started" if rows else "pending"
        if state and state != status:
            continue
        records.append({"case": case, "done": len(rows), "expected": expected, "state": status,
                        "different": different, "visible": visible})
    own_complete = progress(request.user)["remaining"] == 0
    return render(request, "control.html", {"people": people, "records": records,
        "annotation_count": Annotation.objects.count(), "case_count": Conversation.objects.count(),
        "unit_count": Unit.objects.count(), "language": language, "state": state,
        "export_allowed": own_complete})

def control_crossed(request, study):
    """Progress only until closure: per annotator, plus the overall state. Nothing per case or per adjudication."""
    submissions = {s.user_id: s for s in Submission.objects.all()}
    people = [{"user": user, "progress": progress(user), "submission": submissions.get(user.id)}
              for user in reeval2.evaluators()]
    closed = bool(study.closed_at)
    return render(request, "control_reeval2.html", {"people": people, "state": reeval2.state(study), "study": study,
        "exports": ExportRecord.objects.select_related("user") if closed else [], "kinds": CROSSED_EXPORTS if closed else []})

@staff_required
def inspect_case(request, group_id):
    if reeval2.crossed_study():
        return HttpResponse(status=403)
    case = get_object_or_404(Conversation, pk=group_id)
    with transaction.atomic():
        if not may_inspect(request.user, case):
            return HttpResponse("Completa primero tu evaluación independiente de esta conversación.", status=403)
        record_exposure(request.user, case)
    units = case.units.prefetch_related("annotations__user", "annotations__events")
    return render(request, "inspect.html", {"case": case, "units": units})

@staff_required
@require_POST
def assign(request):
    if reeval2.crossed_study():
        return HttpResponse(status=403)
    try:
        user_id = int(request.POST.get("user", ""))
    except (ValueError, TypeError):
        return HttpResponse("Selecciona una cuenta válida.", status=400)
    user = get_object_or_404(get_user_model(), pk=user_id)
    case = get_object_or_404(Conversation, pk=request.POST.get("case", ""))
    with transaction.atomic():
        if request.POST.get("action") == "remove":
            if Annotation.objects.filter(user=user, unit__conversation=case).exists():
                messages.error(request, "No se puede retirar un caso que ya tiene anotaciones.")
            else:
                Assignment.objects.filter(user=user, conversation=case).delete()
                messages.success(request, "Asignación retirada.")
        elif request.POST.get("action") == "add":
            if Exposure.objects.filter(user=user, conversation=case).exists():
                messages.error(request, "Esta persona ya ha visto las etiquetas del caso; no se puede asignar como evaluación independiente.")
            else:
                Assignment.objects.get_or_create(user=user, conversation=case, defaults={"position": case.position})
                messages.success(request, "Caso asignado.")
        else:
            return HttpResponse(status=400)
    return redirect("control")

# (kind, button label). Decisions are served by adjudication_export; "gold" belongs to the first study.
CROSSED_EXPORTS = [("jsonl", "Etiquetas (JSONL)"), ("csv", "Etiquetas (CSV)"), ("events", "Historial de cambios"),
                   ("agreement", "Acuerdo y κ"), ("audit", "Registro del estudio")]

def audit_rows():
    """Hand-ins, exposures, study timeline and earlier downloads: the evidence of who touched what and when."""
    rows = [{"type": "submission", "account": s.user.username, "at": s.submitted_at.isoformat(),
             "annotations_sha256": s.annotations_sha256, "declaration_version": s.declaration_version,
             "declaration": s.declaration} for s in Submission.objects.select_related("user").order_by("id")]
    rows += [{"type": "exposure", "account": e.user.username, "conversation": e.conversation_id, "at": e.created_at.isoformat()}
             for e in Exposure.objects.select_related("user").order_by("id")]
    rows += [{"type": "study_event", "kind": e.kind, "actor": e.actor, "detail": e.detail, "at": e.created_at.isoformat()}
             for e in StudyEvent.objects.all()]
    rows += [{"type": "export", "account": e.user.username, "kind": e.kind, "sha256": e.sha256, "at": e.created_at.isoformat()}
             for e in ExportRecord.objects.select_related("user")]
    return rows

@staff_required
def export(request, kind):
    study = reeval2.crossed_study()
    if study and not study.closed_at:
        return HttpResponse("Las descargas se abren al cerrar el estudio.", status=403)
    if kind not in ([k for k, _ in CROSSED_EXPORTS] if study else ["csv", "jsonl", "events", "agreement", "gold"]):
        return HttpResponse(status=404)
    username = request.GET.get("annotator", "")
    selected_user = get_object_or_404(get_user_model(), username=username) if kind == "gold" else None
    if selected_user and progress(selected_user)["remaining"]:
        return HttpResponse("El export gold requiere terminar todas las asignaciones de esa persona.", status=409)
    if selected_user and not Assignment.objects.filter(user=selected_user).exists():
        return HttpResponse("Esta persona no tiene una muestra asignada.", status=409)
    with transaction.atomic():
        if progress(request.user)["remaining"]:
            return HttpResponse("Completa tus casos antes de exportar etiquetas o consultar el acuerdo entre evaluadores.", status=403)
        for case in Conversation.objects.all():
            record_exposure(request.user, case)
        annotations = list(Annotation.objects.select_related("user", "unit__conversation__study").order_by("unit_id", "user_id"))
        rows = [{"unit_id": a.unit_id, "group_id": a.unit.conversation_id,
                 "record_id": a.unit.metadata["record_id"], "judged_turn": a.unit.judged_turn,
                 "annotator": a.user.username, "label": a.label, "first_label": a.first_label,
                 "note": a.note, "version": a.version, "created_at": a.created_at.isoformat(),
                 "updated_at": a.updated_at.isoformat(), "language": a.unit.conversation.language,
                 "rubric_version": a.unit.conversation.study.rubric_version,
                 "study_sha256": a.unit.conversation.study.fingerprint,
                 "payload_sha256": a.unit.conversation.source_sha256,
                 "label_source": "human_independent"} for a in annotations]
        if kind == "gold":
            rows = [{**{k: a.unit.metadata[k] for k in ["schema_version", "record_id", "item_id", "scenario_ref", "scenario_family", "language", "bug_ref"]},
                     "judged_turn": a.unit.judged_turn, "gold_label": a.first_label,
                     "annotators": [a.user.username], "adjudicated": False, "label_source": "human_independent_first",
                     "note": "Primer voto humano independiente. Sin adjudicación ni mezcla con preetiquetas.",
                     "study_sha256": a.unit.conversation.study.fingerprint} for a in annotations if a.user_id == selected_user.id]
        if kind == "events":
            rows = [{"unit_id": e.annotation.unit_id, "annotator": e.annotation.user.username,
                     "label": e.label, "note": e.note, "version": e.version, "created_at": e.created_at.isoformat()}
                    for e in AnnotationEvent.objects.select_related("annotation__user").order_by("id")]
        if kind == "agreement":
            rows = agreement_report()
        if kind == "audit":
            rows = audit_rows()
    if kind == "csv":
        out = io.StringIO()
        fields = list(rows[0]) if rows else ["unit_id", "annotator", "label", "first_label"]
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "'"+v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else v for k, v in row.items()})
        content, mime, ext = "\ufeff"+out.getvalue(), "text/csv; charset=utf-8", "csv"
    else:
        content = "".join(json.dumps(r, ensure_ascii=False)+"\n" for r in rows)
        mime, ext = "application/x-ndjson", "jsonl"
    if study:
        ExportRecord.objects.create(user=request.user, kind=kind, sha256=reeval2.export_sha256(content))
    response = HttpResponse(content, content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="sycocode-{kind}.{ext}"'
    return response
