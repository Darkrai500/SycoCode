from django.conf import settings
from django.db import models

LABELS = [("firm", "Se mantiene firme"), ("hedged", "Introduce matices"), ("capitulated", "Cede")]

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=True)
    # Granted explicitly to an evaluator without changing their staff/admin role.
    can_adjudicate = models.BooleanField(default=False)

class Study(models.Model):
    name = models.CharField(max_length=160, default="Fase 1 · Evaluación humana")
    fingerprint = models.CharField(max_length=64, unique=True)
    rubric_version = models.CharField(max_length=20, default="1.1")
    created_at = models.DateTimeField(auto_now_add=True)

class Conversation(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    study = models.ForeignKey(Study, on_delete=models.PROTECT)
    language = models.CharField(max_length=8)
    scenario = models.CharField(max_length=100)
    anchor = models.TextField()
    turns = models.JSONField()
    source_sha256 = models.CharField(max_length=64)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position", "id"]

class Unit(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT, related_name="units")
    judged_turn = models.PositiveIntegerField()
    metadata = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "judged_turn"], name="one_unit_per_turn")]

class Assignment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT, related_name="assignments")
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["user", "conversation"], name="one_assignment")]

class Annotation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="annotations")
    label = models.CharField(max_length=16, choices=LABELS)
    first_label = models.CharField(max_length=16, choices=LABELS)
    note = models.CharField(max_length=1000, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "unit"], name="one_annotation_per_user_unit"),
                       models.CheckConstraint(condition=models.Q(label__in=[x[0] for x in LABELS]), name="valid_label"),
                       models.CheckConstraint(condition=models.Q(first_label__in=[x[0] for x in LABELS]), name="valid_first_label")]

class AnnotationEvent(models.Model):
    annotation = models.ForeignKey(Annotation, on_delete=models.PROTECT, related_name="events")
    label = models.CharField(max_length=16, choices=LABELS)
    note = models.CharField(max_length=1000, blank=True)
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["annotation", "version"], name="one_event_per_version")]

class Exposure(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "conversation"], name="one_exposure")]

class LoginFailure(models.Model):
    key = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AdjudicationQueueItem(models.Model):
    unit = models.OneToOneField(Unit, primary_key=True, on_delete=models.PROTECT,
                                related_name="adjudication_queue_item")
    position = models.PositiveSmallIntegerField(unique=True)
    source_row = models.JSONField()
    source_sha256 = models.CharField(max_length=64)
    annotation_state_sha256 = models.CharField(max_length=64, default="")
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]

class Adjudication(models.Model):
    unit = models.OneToOneField(Unit, on_delete=models.PROTECT, related_name="adjudication")
    label = models.CharField(max_length=16, choices=LABELS)
    rationale = models.TextField()
    version = models.PositiveIntegerField(default=1)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decided_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(label__in=[x[0] for x in LABELS]),
                                              name="valid_adjudication_label")]

class AdjudicationEvent(models.Model):
    adjudication = models.ForeignKey(Adjudication, on_delete=models.PROTECT, related_name="events")
    version = models.PositiveIntegerField()
    label = models.CharField(max_length=16, choices=LABELS)
    rationale = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField()
    request_id = models.UUIDField(unique=True)
    vote_snapshot = models.JSONField()

    class Meta:
        ordering = ["version"]
        constraints = [models.UniqueConstraint(fields=["adjudication", "version"],
                                                name="one_adjudication_event_per_version"),
                       models.CheckConstraint(condition=models.Q(label__in=[x[0] for x in LABELS]),
                                              name="valid_adjudication_event_label")]
