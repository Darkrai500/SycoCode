#!/usr/bin/env python3
"""Print a minimal evaluation snapshot from SQLite using a read-only transaction.

Run on the server as the database owner, with --db pointing to study.sqlite3.
Does not export passwords, sessions, email addresses, or conversation text.
Does not invoke Django views (exports there record exposure as a side effect).
"""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def snapshot(path):
    con = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    con.execute('BEGIN')

    def rows(sql):
        return [dict(row) for row in con.execute(sql)]

    data = {
        'snapshot_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'SQLite mode=ro; query_only=ON; single read transaction; no HTTP export',
        'integrity_check': [r[0] for r in con.execute('PRAGMA integrity_check')],
        'studies': rows('SELECT id, fingerprint, rubric_version FROM annotations_study'),
        'accounts': rows('SELECT username, is_active, is_staff, is_superuser FROM auth_user ORDER BY username'),
        'assignments': rows('''SELECT u.username AS annotator, a.conversation_id AS group_id,
            t.id AS unit_id, a.created_at AS assigned_at
            FROM annotations_assignment a JOIN auth_user u ON a.user_id=u.id
            JOIN annotations_unit t ON t.conversation_id=a.conversation_id
            ORDER BY u.username, t.id'''),
        'annotations': rows('''SELECT a.unit_id, t.conversation_id AS group_id,
            t.metadata, t.judged_turn, u.username AS annotator, a.label, a.first_label,
            a.note, a.version, a.created_at, a.updated_at, c.language,
            s.rubric_version, s.fingerprint AS study_sha256,
            c.source_sha256 AS payload_sha256
            FROM annotations_annotation a JOIN auth_user u ON a.user_id=u.id
            JOIN annotations_unit t ON t.id=a.unit_id
            JOIN annotations_conversation c ON c.id=t.conversation_id
            JOIN annotations_study s ON s.id=c.study_id ORDER BY a.unit_id, u.username'''),
        'events': rows('''SELECT a.unit_id, u.username AS annotator, e.label, e.note,
            e.version, e.created_at FROM annotations_annotationevent e
            JOIN annotations_annotation a ON a.id=e.annotation_id
            JOIN auth_user u ON u.id=a.user_id ORDER BY e.id'''),
        'exposures': rows('''SELECT u.username AS annotator, e.conversation_id AS group_id,
            e.created_at FROM annotations_exposure e JOIN auth_user u ON u.id=e.user_id
            ORDER BY u.username, e.conversation_id'''),
    }
    for row in data['annotations']:
        row['record_id'] = json.loads(row.pop('metadata'))['record_id']
        # Preserve the existing exporter field; it is not authorship evidence.
        row['label_source'] = 'human_independent'
        for field in ('created_at', 'updated_at'):
            row[field] = datetime.fromisoformat(row[field]).replace(tzinfo=timezone.utc).isoformat()
    con.rollback()
    con.close()
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    args = parser.parse_args()
    print(json.dumps(snapshot(args.db), ensure_ascii=False, indent=2))
