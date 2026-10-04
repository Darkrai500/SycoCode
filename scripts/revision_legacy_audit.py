#!/usr/bin/env python3
"""Compare obsolete pilot checks against v1/v2 and replay the long-paper analysis.

Only trusted analysis scripts are imported. No generation, judges, or corpus code
are executed. Original scripts, data and results remain unchanged.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
from revision_analysis import digest, dump


def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--archive-root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.out.exists() or a.archive_root.resolve() in a.out.resolve().parents:ap.error('new output outside archive required')
    a.out.mkdir(parents=True)
    p=a.root/'scripts/tfg_thesis_metrics.py';old=a.archive_root/'Paper/scripts/stats_validation.py'
    original=a.archive_root/'Paper/analysis/stats_validation.json'
    manifest={str(q):digest(q) for q in (p,old,original,a.archive_root/'data/runs/full/verdicts.v1.jsonl',a.archive_root/'data/runs/full/verdicts.jsonl')}
    m=module(p,'pilot');m.RUNS=a.archive_root/'data/runs'
    fn=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
    expr=next(n.value for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='checks' for t in n.targets))
    expr=compile(ast.Expression(expr),str(p),'eval');result={}
    for version,filename in (('v1','verdicts.v1.jsonl'),('v2','verdicts.jsonl')):
        m.MODELS['full']=('gpt-oss-120b',filename);g=m.compute('full')
        checks=eval(expr,{'g':g})
        result[version]={'checks':[{'name':n,'computed':v,'expected':e,'within_legacy_tolerance':v is not None and abs(v-e)<=.011}
                                  for n,v,e in checks], 'metrics':g}
    result['pass_counts']={k:sum(c['within_legacy_tolerance'] for c in v['checks']) for k,v in result.items()}
    dump(a.out/'selfcheck.json',result)
    legacy=module(old,'long_paper');legacy.OUTDIR=a.out/'long_paper';legacy.main()
    aa=json.loads((legacy.OUTDIR/'stats_validation.json').read_text());bb=json.loads(original.read_text())
    report={'input_sha256':manifest,'legacy_replay_structured_equal':aa==bb,
            'sections_equal':{k:aa[k]==bb.get(k) for k in aa},
            'selfcheck_pass_counts':result['pass_counts'],'legacy_tolerance':.011,
            'note':'Reproducing an inferential defect is not validation of that method.'}
    if manifest!={str(q):digest(q) for q in manifest}:raise ValueError('input mutation')
    report['inputs_unchanged']=True;dump(a.out/'validation.json',report)
    print(json.dumps(report))


if __name__=='__main__':main()
