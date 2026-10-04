#!/usr/bin/env python3
"""Run via deployed Django shell; emit a consistent, read-only closure export.

No database copy, credentials, sessions, email addresses or conversations are
exported. The official export views are called with the existing control user.
Exposure recording is suppressed only in this short-lived Python process;
SQLite query_only enforces read-only access independently of that suppression.
"""
import hashlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import RequestFactory

from annotations import adjudication, provenance
from annotations.models import (Adjudication, AdjudicationEvent,
    AdjudicationQueueItem, Annotation, AnnotationEvent, Assignment,
    Conversation, Exposure, Profile, Study, Unit)


def export_snapshot():
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA query_only=ON")
        assert cursor.execute("PRAGMA query_only").fetchone()[0] == 1
    # Production uses IMMEDIATE transactions for concurrent form submissions.
    # This separate read-only connection needs a DEFERRED read transaction.
    connection.transaction_mode = "DEFERRED"
    with transaction.atomic():
        with connection.cursor() as cursor:
            integrity = [r[0] for r in cursor.execute("PRAGMA integrity_check")]
            changes_before = cursor.execute("SELECT total_changes()").fetchone()[0]
        assert integrity == ["ok"], integrity
        counts = {name: model.objects.count() for name, model in {
            "studies": Study, "conversations": Conversation, "units": Unit,
            "assignments": Assignment, "annotations": Annotation,
            "annotation_events": AnnotationEvent, "queue": AdjudicationQueueItem,
            "decisions": Adjudication, "decision_events": AdjudicationEvent,
            "exposures": Exposure}.items()}
        assert counts["queue"] == counts["decisions"] == 42, counts
        assert counts["units"] == 320 and counts["annotations"] == 640, counts
        assert counts["annotation_events"] == 651, counts
        captured_at = datetime.now(timezone.utc).isoformat()
        annotation_digest = provenance.annotation_state_sha256()
        control = get_user_model().objects.get(username="control")
        assert adjudication.can_supervise(control)
        factory = RequestFactory()
        exports = {}
        # The HTTP paths normally record read exposure. Do not change those
        # records while taking this archival snapshot.
        with patch.object(adjudication, "record_exposure", return_value=None):
            for name, route, view in [
                ("adjudications", "/adjudication/export/", adjudication.export_decisions),
                ("reference_candidate", "/adjudication/export/reference/", adjudication.export_reference),
            ]:
                request = factory.get(route)
                request.user = control
                response = view(request)
                if response.status_code != 200:
                    raise RuntimeError(f"{route}: {response.status_code}: {response.content.decode()}")
                exports[name] = {"route": route, "status_code": response.status_code,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "jsonl": response.content.decode("utf-8")}
        units = [{"unit_id": u.id, "group_id": u.conversation_id,
                  "judged_turn": u.judged_turn, "metadata": u.metadata,
                  "language": u.conversation.language, "scenario": u.conversation.scenario,
                  "payload_sha256": u.conversation.source_sha256,
                  "study_sha256": u.conversation.study.fingerprint,
                  "rubric_version": u.conversation.study.rubric_version}
                 for u in Unit.objects.select_related("conversation__study").order_by("id")]
        queue_metadata = list(AdjudicationQueueItem.objects.order_by("position").values(
            "unit_id", "position", "source_sha256", "annotation_state_sha256", "imported_at"))
        for row in queue_metadata:
            row["imported_at"] = row["imported_at"].isoformat()
        permissions = []
        for user in get_user_model().objects.filter(username__in=["jc", "control"]).order_by("username"):
            permissions.append({"username": user.username, "is_active": user.is_active,
                "is_staff": user.is_staff, "is_superuser": user.is_superuser,
                "can_adjudicate": Profile.objects.get(user=user).can_adjudicate})
        with connection.cursor() as cursor:
            changes_after = cursor.execute("SELECT total_changes()").fetchone()[0]
            query_only = cursor.execute("PRAGMA query_only").fetchone()[0]
        assert changes_before == changes_after == 0
        assert Exposure.objects.count() == counts["exposures"]
        assert provenance.annotation_state_sha256() == annotation_digest
        source_hashes = {}
        for module in (adjudication, provenance):
            source = Path(inspect.getfile(module))
            source_hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        release = str(Path(inspect.getfile(adjudication)).resolve().parents[2])
        return {"schema_version": "sycocode-reeval-closure-snapshot-v1",
            "snapshot_utc": captured_at, "source_release": release,
            "method": "Django official export views; control; one DEFERRED read transaction; PRAGMA query_only=ON; exposure recording suppressed in exporter process only",
            "integrity_check": integrity, "query_only": query_only,
            "connection_total_changes_before": changes_before,
            "connection_total_changes_after": changes_after,
            "counts": counts, "annotation_state_sha256": annotation_digest,
            "application_source_sha256": source_hashes, "permissions": permissions,
            "units": units, "queue_metadata": queue_metadata, "exports": exports}


print(json.dumps(export_snapshot(), ensure_ascii=False, indent=2))
