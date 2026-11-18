"""Calibration for ReEval-2: a read-only exercise, separate from the study tables.

Answers are never stored: the page posts the answer back and shows the reference
label. Cases come from the first reference (scripts/build_reeval2_calibration.py),
with no rationale, because the first author adjudicated that reference.
"""
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import LABELS

SOURCE = settings.BASE_DIR / "annotations/data/reeval2_calibration.json"


def load_cases():
    return json.loads(SOURCE.read_text(encoding="utf-8"))["cases"]


@login_required
def index(request):
    return render(request, "calibration_index.html", {"cases": load_cases()})


@login_required
@require_http_methods(["GET", "POST"])
def case(request, case_id):
    cases = load_cases()
    index_ = next((i for i, c in enumerate(cases) if c["id"] == case_id), None)
    if index_ is None:
        raise Http404
    answer = request.POST.get("label") if request.method == "POST" else None
    answer = answer if answer in dict(LABELS) else None
    return render(request, "calibration_case.html", {
        "case": cases[index_], "labels": LABELS, "answer": answer,
        "answer_display": dict(LABELS).get(answer), "reference_display": dict(LABELS)[cases[index_]["label"]],
        "next": cases[index_ + 1] if index_ + 1 < len(cases) else None,
        "position": index_ + 1, "total": len(cases)})
