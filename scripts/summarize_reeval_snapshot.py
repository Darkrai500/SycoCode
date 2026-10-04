#!/usr/bin/env python3
"""Validate a read-only snapshot and prepare comparisons and an unfilled review queue."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path

from audit_reeval import dump, jsonl, key, panel, read, score, sha, unique, FIXED, TIES


def summarize(snapshot_path, analysis, root, cohort, out):
    import json
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot['integrity_check'] != ['ok'] or out.exists():
        raise ValueError('Require an intact database and a new output directory')
    rows = snapshot['annotations']
    pool = unique(read(root / 'data/goldset/pool.jsonl'), lambda r: r['unit_id'])
    assigned = defaultdict(set)
    by_person = defaultdict(dict)
    events = defaultdict(list)
    for r in snapshot['assignments']:
        assigned[r['annotator']].add(r['unit_id'])
    for r in rows:
        if r['unit_id'] in by_person[r['annotator']]:
            raise ValueError('Duplicate annotation')
        by_person[r['annotator']][r['unit_id']] = r
    for r in snapshot['events']:
        events[r['annotator'], r['unit_id']].append(r)
    for r in rows:
        ev = sorted(events[r['annotator'], r['unit_id']], key=lambda e: e['version'])
        if [e['version'] for e in ev] != list(range(1, r['version'] + 1)):
            raise ValueError('Missing event versions')
        if ev[0]['label'] != r['first_label'] or ev[-1]['label'] != r['label']:
            raise ValueError('Event/annotation mismatch')
    if len(events) != len(rows):
        raise ValueError('Orphan event')
    refs = {n: unique(read(analysis / ('reference_' + n + '_first.jsonl')), lambda r: r['unit_id'])
            for n in by_person}
    people = sorted(set(by_person) - {'jc'})
    external = defaultdict(list)
    for n in people:
        for uid in by_person[n]:
            external[uid].append(n)
    if set(external) != set(pool) or any(len(ns) != 1 for ns in external.values()):
        raise ValueError('This composite requires exactly one external evaluator per pool unit')
    if set(by_person['jc']) != set(pool):
        raise ValueError('JC coverage must be complete')

    predictions = {'actual_cohort_labels': {key(r): r['label'] for r in read(cohort)}}
    votes = defaultdict(dict)
    for r in read(root / 'data/goldset/votes.jsonl'):
        if r['protocol'] == 'binary':
            votes[key(r)][r['judge_model']] = r.get('label')
    for name, tie in TIES.items():
        predictions['selection_reconstructed_' + name] = {k: panel(v, tie) for k, v in votes.items()}
    predictions['jc_reviewed'] = {key(r): r['label'] for r in by_person['jc'].values()}
    combined, statistics, queue = {}, {}, []
    cutoff = '2026-09-21T15:19:00+00:00'
    result = {'snapshot_utc': snapshot['snapshot_utc'], 'snapshot_sha256': sha(snapshot_path),
              'script_sha256': sha(__file__), 'event_integrity': True,
              'events': len(snapshot['events']), 'annotations': len(rows),
              'status': 'human annotations with recorded provenance; no adjudication; partial cohort sensitivity only',
              'accounts': {}, 'external_overlap': {}, 'pairs_current': {},
              'external_reference': 'One named external annotator per unit, concatenated over disjoint assignments; not one person, a majority, or a consensus'}
    for n in sorted(by_person):
        own = by_person[n]
        if set(own) - assigned[n]:
            raise ValueError('Vote outside assignments')
        result['accounts'][n] = {
            'assigned': len(assigned[n]), 'saved': len(own), 'pending': len(assigned[n] - set(own)),
            'conversations': len({r['group_id'] for r in own.values()}),
            'first_distribution': dict(Counter(r['first_label'] for r in own.values())),
            'current_distribution': dict(Counter(r['label'] for r in own.values())),
            'edited_labels': sum(r['first_label'] != r['label'] for r in own.values()),
            'before_clarification': [r['unit_id'] for r in own.values() if r['created_at'] < cutoff],
            'last_update_utc': max(r['updated_at'] for r in own.values()),
            'recorded_exposures': sum(e['annotator'] == n for e in snapshot['exposures'])}
        if n != 'jc':
            current_refs = [dict(refs[n][uid], gold_label=r['label']) for uid, r in own.items()]
            result['pairs_current'][n] = {lg: score([r for r in current_refs if lg == 'all' or r['language'] == lg],
                predictions['jc_reviewed'], 10000, 20260921) for lg in ('all', 'en', 'es')}
    for i, a in enumerate(people):
        for b in people[i+1:]:
            result['external_overlap'][a + '::' + b] = len(set(by_person[a]) & set(by_person[b]))
    for mode, field in [('first', 'first_label'), ('current', 'label')]:
        combined[mode] = []
        for uid in sorted(pool):
            who = external[uid][0]
            row = by_person[who][uid]
            combined[mode].append(dict(refs[who][uid], gold_label=row[field], vote_version=mode,
                note='One external annotator for this unit; preserves identity; no adjudication'))
        statistics[mode] = {name: {lg: score([r for r in combined[mode] if lg == 'all' or r['language'] == lg],
            pred, 10000, 20260921) for lg in ('all', 'en', 'es')} for name, pred in predictions.items()}
    for uid in sorted(pool):
        who = external[uid][0]
        ext, jc = by_person[who][uid], by_person['jc'][uid]
        if ext['first_label'] != jc['label'] or ext['label'] != jc['label'] or ext['label'] != ext['first_label']:
            queue.append({'unit_id': uid, 'group_id': ext['group_id'], 'record_id': ext['record_id'],
                'judged_turn': ext['judged_turn'], 'language': ext['language'],
                'scenario': pool[uid]['scenario_ref'], 'external_annotator': who,
                'jc_reviewed': jc['label'], 'external_first': ext['first_label'],
                'external_current': ext['label'], 'external_first_before_clarification': ext['created_at'] < cutoff,
                'payload_path': pool[uid]['payload_path'], 'adjudicated_label': None,
                'adjudicator': None, 'rationale': None, 'status': 'pending_human_review'})
    result['comparisons_composite'] = statistics
    result['queue'] = {'units': len(queue),
        'first_disagreements': sum(r['external_first'] != r['jc_reviewed'] for r in queue),
        'current_disagreements': sum(r['external_current'] != r['jc_reviewed'] for r in queue),
        'edited_external_units': sum(r['external_first'] != r['external_current'] for r in queue)}
    audit = json.loads((analysis / 'audit.json').read_text())
    provenance_path = Path(audit['config'].get('provenance_manifest_path',
                           snapshot_path.parent / 'provenance.json'))
    result['provenance_manifest_path'] = str(provenance_path.resolve())
    result['hashes'] = {'export': sha(snapshot_path.parent / 'sycocode-jsonl.jsonl'),
                       'provenance': sha(provenance_path), 'cohort': sha(cohort)}
    out.mkdir(parents=True)
    dump(out / 'summary.json', result)
    jsonl(out / 'review_queue.jsonl', queue)
    for mode, rr in combined.items():
        jsonl(out / ('external_reference_' + mode + '.jsonl'), rr)
        jsonl(out / ('external_overlay_' + mode + '.jsonl'), [
            {'model': 'full', 'record_id': r['record_id'], 'judged_turn': r['judged_turn'],
             'label': r['gold_label'], 'source': 'unadjudicated-human-external-sensitivity:' + mode + ':' +
             r['annotators'][0] + ':' + result['hashes']['export']} for r in rr])
    print({'output': str(out), 'queue': result['queue'], 'event_integrity': True})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--analysis', type=Path, required=True)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    summarize(a.snapshot, a.analysis, a.root, a.cohort, a.out)
