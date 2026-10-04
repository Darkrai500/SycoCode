#!/usr/bin/env python3
"""Exercise closure rejection paths on private temporary copies of evidence."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from freeze_reeval_reference import derive, json_bytes, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'Refusing to overwrite test evidence')
    root = Path(__file__).resolve().parents[1]
    folder = args.folder.resolve()
    derive(root, folder)
    original = json.loads((folder/'private/server-snapshot.json').read_text())
    cases = [
        ('missing_adjudication', 'Incomplete adjudications'),
        ('duplicate_reference_unit', 'Duplicate reference_candidate'),
        ('empty_rationale', 'Invalid decision provenance/rationale'),
        ('changed_original_vote', 'Original annotation changed'),
        ('disagreement_outside_queue', 'Agreement outside queue missing'),
        ('missing_decision_event', 'Missing decision version'),
        ('wrong_decision_author', 'Decision attribution mismatch'),
    ]
    results = []
    for name, expected in cases:
        snapshot = copy.deepcopy(original)
        exports = {key: [json.loads(line) for line in value['jsonl'].splitlines()]
                   for key, value in snapshot['exports'].items()}
        adjudications = exports['adjudications']
        candidates = exports['reference_candidate']
        entry = adjudications[0]
        candidate = next(r for r in candidates if r['unit_id'] == entry['unit_id'])
        if name == 'missing_adjudication':
            adjudications.pop()
        elif name == 'duplicate_reference_unit':
            candidates[-1] = copy.deepcopy(candidates[0])
        elif name == 'empty_rationale':
            entry['decision']['rationale'] = candidate['decision']['rationale'] = ''
            entry['events'][-1]['rationale'] = ''
        elif name == 'changed_original_vote':
            vote = candidates[0]['annotations'][0]
            vote['current_label'] = 'hedged' if vote['current_label'] != 'hedged' else 'firm'
        elif name == 'disagreement_outside_queue':
            row = next(r for r in candidates if r['label_source'] == 'current_pair_agreement')
            row['reference_label'] = 'hedged' if row['reference_label'] != 'hedged' else 'firm'
        elif name == 'missing_decision_event':
            entry['events'].pop()
        elif name == 'wrong_decision_author':
            entry['decision']['author'] = candidate['decision']['author'] = 'control'
        for key, rows in exports.items():
            body = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
            snapshot['exports'][key]['jsonl'] = body
            snapshot['exports'][key]['sha256'] = hashlib.sha256(body.encode()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='sycocode-closure-check-') as tmp:
            temporary = Path(tmp)
            (temporary/'private/inputs').mkdir(parents=True, mode=0o700)
            for filename in ('server-snapshot-2026-09-24.json', 'review_queue-2026-09-24.jsonl', 'historical-gold.jsonl'):
                shutil.copyfile(folder/'private/inputs'/filename, temporary/'private/inputs'/filename)
            (temporary/'private/server-snapshot.json').write_bytes(json_bytes(snapshot))
            try:
                derive(root, temporary)
            except ValueError as exc:
                require(expected in str(exc), f'{name}: unexpected failure {exc}')
            else:
                raise ValueError(f'{name}: corrupted input was accepted')
        results.append({'case': name, 'rejected': True, 'reason': expected})
    report = {'status': 'passed', 'valid_snapshot_accepted': True,
              'invalid_cases_rejected': len(results), 'cases': results,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_snapshot_sha256': hashlib.sha256((folder/'private/server-snapshot.json').read_bytes()).hexdigest()}
    with args.out.open('xb') as stream:
        stream.write(json_bytes(report))
    print(json.dumps({'status':'passed', 'invalid_cases_rejected':len(results)}))


if __name__ == '__main__':
    main()
