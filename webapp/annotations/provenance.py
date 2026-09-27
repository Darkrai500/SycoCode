import hashlib
import json

from .models import Annotation


def annotation_state_sha256():
    """Digest the original 640 votes and their events in a stable order.

    The same projection is computed from the private 24 September snapshot when
    the release manifest is prepared. Dates and database row IDs are omitted;
    labels, notes, authors and versions detect a changed annotation history.
    """
    entries = []
    annotations = Annotation.objects.select_related("user").prefetch_related("events").order_by("unit_id", "user__username")
    for annotation in annotations:
        entries.append({
            "unit_id": annotation.unit_id,
            "annotator": annotation.user.username,
            "first_label": annotation.first_label,
            "current_label": annotation.label,
            "version": annotation.version,
            "note": annotation.note,
            "events": [{"version": event.version, "label": event.label, "note": event.note}
                       for event in sorted(annotation.events.all(), key=lambda event: event.version)],
        })
    payload = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
