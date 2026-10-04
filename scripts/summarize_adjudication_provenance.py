#!/usr/bin/env python3
"""Describe which pre-adjudication vote matches each saved final label.

This is provenance accounting, not judge evaluation or a correctness score.
It never modifies decisions, rationales, votes or the frozen human reference.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path


def classify(jc_label, external_label, final_label):
    if jc_label == external_label:
        return 'prior_agreement_retained' if final_label == jc_label else 'prior_agreement_revised'
    if final_label == jc_label:
        return 'matches_jc_vote'
    if final_label == external_label:
        return 'matches_external_vote'
    return 'third_label'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    folder = args.folder.resolve()
    source = folder/'private/adjudications.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    manifest = json.loads((folder/'manifest.json').read_text())
    for name, expected in manifest['output_sha256'].items():
        if digest(folder/name) != expected:
            raise ValueError(f'Frozen artifact changed: {name}')
    source_sha = digest(source)
    if len(rows) != 42 or len({r['unit_id'] for r in rows}) != 42:
        raise ValueError('Expected 42 distinct adjudications')
    counts, authors = Counter(), Counter()
    people = defaultdict(Counter)
    trace = []
    for row in rows:
        jc = [v for v in row['annotations'] if v['annotator'] == 'jc']
        external = [v for v in row['annotations'] if v['annotator'] != 'jc']
        if len(jc) != 1 or len(external) != 1:
            raise ValueError('Expected JC and one external vote')
        jc, external = jc[0], external[0]
        decision = row['decision']
        category = classify(jc['current_label'], external['current_label'], decision['label'])
        counts[category] += 1
        people[external['annotator']][category] += 1
        authors[decision['author']] += 1
        trace.append({'unit_id':row['unit_id'], 'record_id':row['record_id'],
            'judged_turn':row['judged_turn'], 'language':row['language'],
            'jc_vote_before_adjudication':jc['current_label'],
            'external_annotator':external['annotator'],
            'external_vote_before_adjudication':external['current_label'],
            'adjudicated_label':decision['label'], 'label_alignment':category,
            'adjudication_author':decision['author'], 'adjudication_version':decision['version'],
            'adjudicated_at':decision['decided_at'], 'rationale_verbatim':decision['rationale'],
            'source_sha256':source_sha})
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(trace[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(trace)
    csv_bytes = buffer.getvalue().encode('utf-8-sig')
    disagreements = sum(counts[k] for k in ('matches_jc_vote','matches_external_vote','third_label'))
    report = {'schema_version':'sycocode-adjudication-provenance-v1',
        'basis':'Current individual votes preserved in the adjudication snapshot, not first historical votes',
        'comparison':'Equality of label; does not infer reasons from author identity or assess correctness',
        'queue_units':len(rows), 'current_disagreements':disagreements,
        'prior_agreement_units':len(rows)-disagreements,
        'label_alignment':dict(counts), 'by_external_annotator':dict(people),
        'adjudication_authors':dict(authors), 'rationales':'Copied verbatim; not rewritten or independently validated',
        'source_sha256':source_sha,
        'private_trace_sha256':hashlib.sha256(csv_bytes).hexdigest(),
        'script_sha256':digest(Path(__file__)),
        'frozen_reference_sha256':manifest['output_sha256']['private/reference-2026-09-30-v1.jsonl'],
        'frozen_artifacts_unchanged':True, 'panel_metrics_calculated':False}
    outputs = {'private/decision-trace.csv':csv_bytes,
               'decision-provenance.json':(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()}
    if any((folder/name).exists() for name in outputs):
        raise ValueError('Refusing to overwrite existing provenance outputs')
    for name, data in outputs.items():
        with (folder/name).open('xb') as stream:
            stream.write(data)
        if name.startswith('private/'):
            (folder/name).chmod(0o600)
    if digest(source) != source_sha:
        raise ValueError('Source changed during reporting')
    print(json.dumps({'queue_units':len(rows),'current_disagreements':disagreements,
                      'label_alignment':dict(counts)},ensure_ascii=False))


if __name__ == '__main__':
    main()
