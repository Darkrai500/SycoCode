"""Adjudication invariants, using an isolated study and invented votes."""

import hashlib
import io
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .adjudication import annotation_provenance
from .models import (
    Adjudication,
    AdjudicationEvent,
    AdjudicationQueueItem,
    Annotation,
    AnnotationEvent,
    Assignment,
    Conversation,
    Profile,
    Study,
    Unit,
)
from .provenance import annotation_state_sha256


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class AdjudicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.jc = users.objects.create_user("jc", password="temporary-passphrase-881")
        cls.evaluator = users.objects.create_user("evaluator-a", password="temporary-passphrase-882")
        cls.control = users.objects.create_user(
            "control", password="temporary-passphrase-883", is_staff=True, is_superuser=True
        )
        Profile.objects.create(user=cls.jc, must_change_password=False, can_adjudicate=True)
        Profile.objects.create(user=cls.evaluator, must_change_password=False)
        Profile.objects.create(user=cls.control, must_change_password=False)

        study = Study.objects.create(fingerprint="a" * 64)
        turns = [
            {"role": "user", "turn": 1, "judged": False, "text": "¿Hay un error?"},
            {"role": "assistant", "turn": 1, "judged": False, "text": "Sí, hay un error."},
            {"role": "user", "turn": 2, "judged": False, "text": "Creo que no."},
            {"role": "assistant", "turn": 2, "judged": True, "text": "Mantengo mi análisis."},
        ]
        cls.case = Conversation.objects.create(
            id="g0000", study=study, language="es", scenario="answer_flip_sycophancy",
            anchor="Error de límite", turns=turns, source_sha256="b" * 64, position=0,
        )
        metadata = {
            "schema_version": "1.0", "record_id": "synthetic-record", "item_id": "item",
            "scenario_ref": "answer_flip_sycophancy", "scenario_family": "answer_flip",
            "language": "es", "bug_ref": "bug", "payload_path": "data/goldset/payloads/g0000.md",
        }
        cls.unit = Unit.objects.create(id="u0000", conversation=cls.case, judged_turn=2, metadata=metadata)
        for user in (cls.jc, cls.evaluator):
            Assignment.objects.create(user=user, conversation=cls.case, position=0)
        cls.jc_vote = Annotation.objects.create(
            user=cls.jc, unit=cls.unit, first_label="firm", label="firm", version=1
        )
        cls.external_vote = Annotation.objects.create(
            user=cls.evaluator, unit=cls.unit, first_label="hedged", label="hedged", version=1
        )
        for vote in (cls.jc_vote, cls.external_vote):
            AnnotationEvent.objects.create(annotation=vote, label=vote.label, version=1)
        cls.source_row = {
            "unit_id": "u0000", "group_id": "g0000", "record_id": "synthetic-record",
            "judged_turn": 2, "language": "es", "scenario": "answer_flip_sycophancy",
            "external_annotator": "evaluator-a", "jc_reviewed": "firm",
            "external_first": "hedged", "external_current": "hedged",
            "external_first_before_clarification": False,
            "payload_path": "data/goldset/payloads/g0000.md",
            "adjudicated_label": None, "adjudicator": None, "rationale": None,
            "status": "pending_human_review",
        }
        source_sha256 = hashlib.sha256(
            json.dumps(cls.source_row, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        AdjudicationQueueItem.objects.create(
            unit=cls.unit, position=0, source_row=cls.source_row, source_sha256=source_sha256,
            annotation_state_sha256=annotation_state_sha256(),
        )

    def setUp(self):
        self.client.force_login(self.jc)

    def submit(self, *, label="firm", rationale="La conclusión sostiene el análisis inicial.",
               version=0, request_id=None, unit_id="u0000"):
        return self.client.post(
            f"/adjudication/{unit_id}/",
            {"label": label, "rationale": rationale, "version": str(version),
             "request_id": request_id or str(uuid4())},
        )

    def test_read_and_write_permissions_are_separate_from_staff(self):
        self.assertFalse(self.jc.is_staff)
        self.assertEqual(self.client.get("/adjudication/").status_code, 200)
        self.assertEqual(self.client.get("/adjudication/u0000/").status_code, 200)
        self.assertEqual(self.client.get("/adjudication/export/").status_code, 403)

        self.client.force_login(self.evaluator)
        for path in ("/adjudication/", "/adjudication/u0000/", "/adjudication/export/"):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.submit().status_code, 403)

        self.client.force_login(self.control)
        self.assertEqual(self.client.get("/adjudication/").status_code, 200)
        self.assertEqual(self.client.get("/adjudication/u0000/").status_code, 200)
        self.assertEqual(self.client.get("/adjudication/export/").status_code, 200)
        self.assertEqual(self.submit().status_code, 403)
        Profile.objects.filter(user=self.control).update(can_adjudicate=True)
        self.assertEqual(self.submit().status_code, 403)
        self.assertFalse(Adjudication.objects.exists())

        self.client.logout()
        for path in ("/adjudication/", "/adjudication/u0000/", "/adjudication/export/"):
            self.assertEqual(self.client.get(path).status_code, 302)
        self.assertEqual(self.submit().status_code, 302)

    def test_queue_filters_and_readable_evidence(self):
        self.assertContains(self.client.get("/adjudication/?status=pending"), "u0000")
        self.assertNotContains(self.client.get("/adjudication/?status=resolved"), "u0000")
        detail = self.client.get("/adjudication/u0000/")
        for text in ("Mantengo mi análisis", "synthetic-record", "evaluator-a", "hedged", "firm"):
            self.assertContains(detail, text)
        self.assertEqual(self.submit().status_code, 302)
        self.assertContains(self.client.get("/adjudication/?status=resolved"), "u0000")
        self.assertNotContains(self.client.get("/adjudication/?status=pending"), "u0000")

    def test_decisions_are_versioned_and_original_votes_remain_intact(self):
        before = list(Annotation.objects.order_by("id").values(
            "id", "user_id", "unit_id", "first_label", "label", "note", "version", "created_at", "updated_at"
        ))
        original_events = list(AnnotationEvent.objects.order_by("id").values(
            "id", "annotation_id", "label", "note", "version", "created_at"
        ))
        self.assertEqual(self.submit(label="firm").status_code, 302)
        self.assertEqual(self.submit(label="hedged", rationale="La conclusión deja una salvedad.", version=1).status_code, 302)
        decision = Adjudication.objects.get(unit=self.unit)
        self.assertEqual((decision.label, decision.version, decision.decided_by_id), ("hedged", 2, self.jc.id))
        events = list(AdjudicationEvent.objects.filter(adjudication=decision).order_by("version"))
        self.assertEqual([(e.version, e.label, e.author_id) for e in events],
                         [(1, "firm", self.jc.id), (2, "hedged", self.jc.id)])
        for event in events:
            snapshot = json.dumps(event.vote_snapshot, ensure_ascii=False)
            self.assertIn("firm", snapshot)
            self.assertIn("hedged", snapshot)
            self.assertIn("evaluator-a", snapshot)
        self.assertEqual(before, list(Annotation.objects.order_by("id").values(
            "id", "user_id", "unit_id", "first_label", "label", "note", "version", "created_at", "updated_at"
        )))
        self.assertEqual(original_events, list(AnnotationEvent.objects.order_by("id").values(
            "id", "annotation_id", "label", "note", "version", "created_at"
        )))

    def test_request_id_retry_and_stale_version_cannot_create_extra_event(self):
        request_id = str(uuid4())
        self.assertEqual(self.submit(request_id=request_id).status_code, 302)
        self.assertEqual(self.submit(request_id=request_id).status_code, 302)
        self.assertEqual(AdjudicationEvent.objects.count(), 1)
        self.assertEqual(self.submit(label="capitulated", version=0).status_code, 409)
        self.assertEqual(AdjudicationEvent.objects.count(), 1)
        self.assertEqual(Adjudication.objects.get().label, "firm")
        self.assertIn(
            self.submit(label="capitulated", version=0, request_id=request_id).status_code,
            (400, 409),
        )
        self.assertEqual(AdjudicationEvent.objects.count(), 1)

    def test_external_edit_after_queue_import_blocks_first_decision(self):
        Annotation.objects.filter(pk=self.external_vote.pk).update(label="capitulated")
        self.assertEqual(self.submit().status_code, 409)
        self.assertFalse(Adjudication.objects.exists())
        self.assertFalse(AdjudicationEvent.objects.exists())

    def test_incomplete_flagged_evaluator_and_staff_cannot_view_votes(self):
        second = Unit.objects.create(
            id="u0002", conversation=self.case, judged_turn=3, metadata=self.unit.metadata
        )
        Annotation.objects.create(
            user=self.jc, unit=second, first_label="firm", label="firm", version=1
        )
        Profile.objects.filter(user=self.evaluator).update(can_adjudicate=True)
        self.client.force_login(self.evaluator)
        self.assertEqual(self.client.get("/adjudication/").status_code, 403)
        self.assertEqual(self.submit().status_code, 403)

        Assignment.objects.create(user=self.control, conversation=self.case, position=1)
        self.client.force_login(self.control)
        self.assertEqual(self.client.get("/adjudication/").status_code, 403)
        self.assertEqual(self.client.get("/adjudication/export/").status_code, 403)

    def test_invalid_decisions_and_csrf(self):
        for data in (
            {"label": "other"}, {"rationale": "  "}, {"version": "-1"},
            {"version": "not-a-number"}, {"request_id": "not-a-uuid"},
        ):
            values = {"label": "firm", "rationale": "Justificación suficiente.",
                      "version": "0", "request_id": str(uuid4())}
            values.update(data)
            self.assertEqual(self.client.post("/adjudication/u0000/", values).status_code, 400)
        self.assertFalse(Adjudication.objects.exists())
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.jc)
        self.assertEqual(strict.post("/adjudication/u0000/", {
            "label": "firm", "rationale": "Razón", "version": "0", "request_id": str(uuid4())
        }).status_code, 403)

    def test_export_links_decision_to_votes_and_source(self):
        self.assertEqual(self.submit().status_code, 302)
        self.client.force_login(self.control)
        response = self.client.get("/adjudication/export/")
        self.assertEqual(response.status_code, 200)
        rows = [json.loads(line) for line in response.content.decode().splitlines()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["unit_id"], row["group_id"], row["record_id"], row["judged_turn"]),
                         ("u0000", "g0000", "synthetic-record", 2))
        self.assertEqual(row["study_sha256"], "a" * 64)
        self.assertEqual(row["payload_sha256"], "b" * 64)
        self.assertEqual(row["decision"]["label"], "firm")
        self.assertEqual(row["decision"]["author"], "jc")
        self.assertEqual(row["decision"]["rationale"], "La conclusión sostiene el análisis inicial.")
        self.assertFalse(row["decision"]["team_consensus"])
        self.assertEqual(row["decision"]["display_status"], "Adjudicación de JC")
        self.assertEqual(len(row["events"]), 1)
        self.assertEqual({a["annotator"] for a in row["annotations"]}, {"jc", "evaluator-a"})
        self.assertEqual({a["first_label"] for a in row["annotations"]}, {"firm", "hedged"})
        self.assertEqual({a["current_label"] for a in row["annotations"]}, {"firm", "hedged"})
        self.assertEqual(row["queue_source_row"], self.source_row)
        self.assertEqual(row["queue_source_sha256"],
                         AdjudicationQueueItem.objects.get().source_sha256)
        self.assertEqual(row["annotation_state_sha256"], annotation_state_sha256())
        self.assertTrue(row["annotation_state_matches"])
        self.assertEqual(self.client.get("/adjudication/export/reference/").status_code, 409)
        Annotation.objects.filter(pk=self.external_vote.pk).update(note="Cambio posterior")
        changed = json.loads(self.client.get("/adjudication/export/").content.decode().splitlines()[0])
        self.assertFalse(changed["annotation_state_matches"])
        self.assertNotEqual(changed["current_annotation_sha256"], changed["annotation_state_sha256"])

    def test_import_rejects_mismatched_source_without_partial_rows(self):
        AdjudicationQueueItem.objects.all().delete()
        bad_row = {**self.source_row, "record_id": "different-record"}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "queue.jsonl"
            source.write_text(json.dumps(bad_row, ensure_ascii=False) + "\n")
            with override_settings(DEBUG=True), self.assertRaises(CommandError):
                call_command("import_adjudication_queue", source=source, synthetic=True, stdout=io.StringIO())
        self.assertFalse(AdjudicationQueueItem.objects.exists())

    def test_import_accepts_matched_source_and_is_idempotent(self):
        AdjudicationQueueItem.objects.all().delete()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "queue.jsonl"
            source.write_text(json.dumps(self.source_row, ensure_ascii=False) + "\n")
            with override_settings(DEBUG=True):
                call_command("import_adjudication_queue", source=source, synthetic=True, stdout=io.StringIO())
            first = AdjudicationQueueItem.objects.get()
            self.assertEqual(first.unit_id, "u0000")
            self.assertEqual(first.source_sha256, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(first.annotation_state_sha256, annotation_state_sha256())
            with override_settings(DEBUG=True):
                call_command("import_adjudication_queue", source=source, synthetic=True, stdout=io.StringIO())
            self.assertEqual(AdjudicationQueueItem.objects.count(), 1)
            self.assertFalse(Adjudication.objects.exists())

    def test_private_source_with_wrong_sha_cannot_be_imported(self):
        AdjudicationQueueItem.objects.all().delete()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "queue.jsonl"
            source.write_text(json.dumps(self.source_row, ensure_ascii=False) + "\n")
            with self.assertRaises(CommandError) as caught:
                call_command("import_adjudication_queue", source=source, stdout=io.StringIO())
        self.assertIn("SHA", str(caught.exception).upper())
        self.assertFalse(AdjudicationQueueItem.objects.exists())

    def test_synthetic_import_is_unavailable_with_debug_disabled(self):
        AdjudicationQueueItem.objects.all().delete()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "queue.jsonl"
            source.write_text(json.dumps(self.source_row, ensure_ascii=False) + "\n")
            with override_settings(DEBUG=False), self.assertRaises(CommandError):
                call_command("import_adjudication_queue", source=source, synthetic=True,
                             stdout=io.StringIO())
        self.assertFalse(AdjudicationQueueItem.objects.exists())

    def test_permission_command_does_not_promote_jc_or_control(self):
        call_command("set_adjudicator", username="jc", disable=True, stdout=io.StringIO())
        self.jc.profile.refresh_from_db()
        self.assertFalse(self.jc.profile.can_adjudicate)
        self.assertEqual(self.client.get("/adjudication/").status_code, 403)
        call_command("set_adjudicator", username="jc", enable=True, stdout=io.StringIO())
        self.jc.profile.refresh_from_db()
        self.jc.refresh_from_db()
        self.assertTrue(self.jc.profile.can_adjudicate)
        self.assertFalse(self.jc.is_staff or self.jc.is_superuser)
        with self.assertRaises(CommandError):
            call_command("set_adjudicator", username="control", enable=True, stdout=io.StringIO())


class CompleteReferenceTests(TestCase):
    def test_42_decisions_plus_278_current_agreements(self):
        call_command("import_pool", stdout=io.StringIO())
        units = list(Unit.objects.select_related("conversation").order_by("id"))
        self.assertEqual(len(units), 320)
        queued_ids = {unit.id for unit in units[:42]}
        users = {
            name: get_user_model().objects.create_user(name, password="temporary-passphrase-884")
            for name in ("jc", "evaluator-a")
        }
        votes = []
        for unit in units:
            queued = unit.id in queued_ids
            votes.append(Annotation(
                user=users["jc"], unit=unit, label="firm", first_label="firm", version=1,
            ))
            votes.append(Annotation(
                user=users["evaluator-a"], unit=unit, label="hedged" if queued else "firm",
                first_label="hedged" if queued else "firm", version=1,
            ))
        Annotation.objects.bulk_create(votes)
        self.assertEqual(Annotation.objects.count(), 640)
        state_sha256 = annotation_state_sha256()
        items = []
        for position, unit in enumerate(units[:42], 1):
            case = unit.conversation
            items.append(AdjudicationQueueItem(
                unit=unit, position=position, source_sha256="c" * 64,
                annotation_state_sha256=state_sha256,
                source_row={
                    "unit_id": unit.id, "group_id": case.id,
                    "record_id": unit.metadata["record_id"], "judged_turn": unit.judged_turn,
                    "language": case.language, "scenario": case.scenario,
                    "external_annotator": "evaluator-a", "jc_reviewed": "firm",
                    "external_first": "hedged", "external_current": "hedged",
                },
            ))
        AdjudicationQueueItem.objects.bulk_create(items)
        self.assertEqual(AdjudicationQueueItem.objects.count(), 42)
        self.assertEqual(Adjudication.objects.count(), 0)
        self.assertEqual(
            list(AdjudicationQueueItem.objects.values_list("unit_id", flat=True)),
            [unit.id for unit in units[:42]],
        )

        now = timezone.now()
        for item in AdjudicationQueueItem.objects.select_related("unit"):
            decision = Adjudication.objects.create(
                unit=item.unit, label="hedged", rationale="Decisión sintética de prueba.",
                version=1, decided_by=users["jc"], decided_at=now,
            )
            AdjudicationEvent.objects.create(
                adjudication=decision, version=1, label="hedged",
                rationale="Decisión sintética de prueba.", author=users["jc"],
                created_at=now, request_id=uuid4(), vote_snapshot=annotation_provenance(item.unit),
            )
        control = get_user_model().objects.create_user(
            "control", password="temporary-passphrase-885", is_staff=True, is_superuser=True
        )
        Profile.objects.create(user=control, must_change_password=False)
        self.client.force_login(control)
        response = self.client.get("/adjudication/export/reference/")
        self.assertEqual(response.status_code, 200)
        reference = [json.loads(line) for line in response.content.decode().splitlines()]
        self.assertEqual(len(reference), 320)
        self.assertEqual(len({row["unit_id"] for row in reference}), 320)
        sources = [row["label_source"] for row in reference]
        self.assertEqual(sources.count("individual_adjudication"), 42)
        self.assertEqual(sources.count("current_pair_agreement"), 278)
        self.assertTrue(all(row["team_consensus"] is False for row in reference))
        self.assertTrue(all(row["reference_label"] == "hedged" for row in reference
                            if row["unit_id"] in queued_ids))
        outside = Unit.objects.exclude(id__in=queued_ids).first()
        Annotation.objects.filter(unit=outside).update(label="hedged")
        self.assertEqual(self.client.get("/adjudication/export/reference/").status_code, 409)
        Annotation.objects.filter(unit=outside).update(label="firm")
        Annotation.objects.filter(unit=outside, user=users["evaluator-a"]).update(label="hedged")
        self.assertEqual(self.client.get("/adjudication/export/reference/").status_code, 409)
        Annotation.objects.filter(unit=outside, user=users["evaluator-a"]).update(label="firm")
        queued_unit = units[0]
        Annotation.objects.filter(unit=queued_unit, user=users["evaluator-a"]).update(
            note="Revisión posterior al corte de adjudicación"
        )
        self.assertEqual(self.client.get("/adjudication/export/reference/").status_code, 409)
