#!/usr/bin/env python3
"""Reproduce statistics from derived ledgers, without transcripts or model APIs.

This tier verifies arithmetic/inference only, not extraction or label validity.
"""
import argparse
import gzip
import json
from pathlib import Path
from revision_analysis import statistics,MODELS,LABELS,dump,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--evidence-root',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    if a.out.exists():ap.error('output must be new')
    def read(name):
        p=a.evidence_root/(name+'.jsonl.gz')
        with gzip.open(p,'rt',encoding='utf-8') as f:return [json.loads(l) for l in f]
    items=read('item_ledger');turns=read('turn_ledger')
    expected=json.loads((a.evidence_root/'statistics.json').read_text());config=expected['config']
    allrows={s:[r for r in items if r['model']==s] for s in MODELS}
    vrows={s:[r for r in turns if r['model']==s and r['label'] in LABELS] for s in MODELS}
    result=statistics(allrows,vrows,config['B'],config['seed'],sorted({r['problem'] for r in items}))
    a.out.mkdir(parents=True);dump(a.out/'statistics.json',result)
    equal=result==expected
    dump(a.out/'validation.json',{'statistics_structured_equal':equal,'conversations':len(items),'turns':len(turns),
        'inputs':{name:digest(a.evidence_root/name) for name in ('item_ledger.jsonl.gz','turn_ledger.jsonl.gz','statistics.json')}})
    if not equal:raise SystemExit('ledger replay mismatch')
    print('ledger replay: complete statistics.json identical')


if __name__=='__main__':main()
