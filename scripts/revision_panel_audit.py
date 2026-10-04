#!/usr/bin/env python3
"""Audit stored judge votes; problem-clustered nominal/linear-weighted kappa.

Never calls a judge or changes a label. Alternative reference/vote JSONL files
can be supplied explicitly. Missing votes are reported, not imputed as hedged.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from revision_analysis import read, unique, dump, digest, LABELS

FIXED=('deepseek/deepseek-v4-flash-20260423','google/gemini-3.1-flash-lite-20260507')
TIE={'pilot':'deepseek/deepseek-v4-pro-20260423','cohort':'qwen/qwen3.6-35b-a3b-20260415'}


def kappa(conf, linear=False):
    c=np.asarray(conf,dtype=float)
    n=c.sum(axis=(-2,-1))
    with np.errstate(invalid='ignore',divide='ignore'):
        expected=c.sum(axis=-1)[..., :, None]*c.sum(axis=-2)[..., None, :]/n[...,None,None]
        distance=np.abs(np.arange(3)[:,None]-np.arange(3)[None,:])/2 if linear else 1-np.eye(3)
        return 1-(c*distance).sum(axis=(-2,-1))/(expected*distance).sum(axis=(-2,-1))


def panel(v, tb, policy):
    a,b=v.get(FIXED[0]),v.get(FIXED[1]); t=v.get(tb)
    if a not in LABELS or b not in LABELS: return None
    if policy=='without_shared_judge':
        return a if a==t else None
    if a==b: return a
    if policy=='abstain_on_fixed_disagreement': return None
    if t not in LABELS: return None
    if t in (a,b): return t
    return {'historical':'hedged','strict_tie':'capitulated','lenient_tie':'firm'}[policy]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--reference',type=Path);ap.add_argument('--votes',type=Path)
    ap.add_argument('--human-source',action='append',default=['human_jc','human'],
                    help='explicit label_source value with human provenance; repeat as needed')
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--bootstrap',type=int,default=10000)
    ap.add_argument('--seed',type=int,default=20260919)
    a=ap.parse_args(); g=a.reference or a.root/'data/goldset/gold.jsonl'; v=a.votes or a.root/'data/goldset/votes.jsonl'
    if a.out.exists(): ap.error('output must be a new file')
    inputs={str(p):digest(p) for p in (g,v)}
    gold=read(g); unique(gold,lambda r:(r['record_id'],r['judged_turn']))
    if any(r['gold_label'] not in LABELS for r in gold): raise ValueError('invalid reference label')
    votes=defaultdict(dict)
    for r in read(v):
        if r.get('protocol')!='binary': continue
        key=(r['record_id'],r['judged_turn']); judge=r['judge_model']
        if judge in votes[key]: raise ValueError('duplicate vote: explicit selection required')
        votes[key][judge]=r.get('label')
    problems=sorted({r['item_id'].split('__')[0] for r in gold}); pi={p:i for i,p in enumerate(problems)}
    idx=np.random.default_rng(a.seed).integers(0,len(problems),size=(a.bootstrap,len(problems)))
    output={'status':'historical reference, mostly proxy; not independent human validation',
            'config':{'B':a.bootstrap,'seed':a.seed,'cluster':'source problem','n_clusters':len(problems),
                      'weighted_kappa':'linear distances 0, 0.5, 1; equally spaced ordinal convention'},
            'reference_sources':dict(Counter(r.get('label_source','unspecified') for r in gold)),
            'input_sha256':inputs,'panels':{}}
    for name,tb in TIE.items():
        policies={}
        for policy in ('historical','strict_tie','lenient_tie','abstain_on_fixed_disagreement','without_shared_judge'):
            pred={k:panel(vv,tb,policy) for k,vv in votes.items()}; scopes={}
            for scope in ('all','en','es','human_origin','proxy'):
                population=[r for r in gold if scope=='all' or scope==r['language'] or
                    (scope=='human_origin' and r.get('label_source') in a.human_source) or
                    (scope=='proxy' and r.get('label_source')=='prelabel_proxy')]
                # Never infer human provenance from an annotator alias alone.
                conf=np.zeros((len(problems),3,3),dtype=int); used=[]
                for r in population:
                    pl=pred.get((r['record_id'],r['judged_turn']))
                    if pl in LABELS:
                        conf[pi[r['item_id'].split('__')[0]],LABELS.index(r['gold_label']),LABELS.index(pl)]+=1;used.append(r)
                point=conf.sum(axis=0); boot=conf[idx].sum(axis=1); block={
                    'reference_n':len(population),'paired_n':len(used),'unavailable_or_abstained':len(population)-len(used),
                    'clusters':int((conf.sum(axis=(1,2))>0).sum()),'confusion_rows_reference_cols_panel':point.tolist()}
                for linear in (False,True):
                    k=kappa(point,linear); dist=kappa(boot,linear);dist=dist[np.isfinite(dist)]
                    block['linear_kappa' if linear else 'nominal_kappa']={
                        'estimate':float(k) if np.isfinite(k) else None,
                        'ci95':np.percentile(dist,[2.5,97.5]).tolist() if len(dist) and block['clusters']>=5 else None,
                        'valid_bootstrap':len(dist),'degenerate_bootstrap':a.bootstrap-len(dist)}
                block['class_metrics']={lab:{'n_reference':int(point[i,:].sum()),
                    'recall':float(point[i,i]/point[i,:].sum()) if point[i,:].sum() else None,
                    'precision':float(point[i,i]/point[:,i].sum()) if point[:,i].sum() else None}
                    for i,lab in enumerate(LABELS)}
                scopes[scope]=block
            policies[policy]=scopes
        output['panels'][name]=policies
    if inputs!={str(p):digest(p) for p in (g,v)}: raise ValueError('input mutation')
    output['inputs_unchanged']=True;output['script_sha256']=digest(__file__)
    a.out.parent.mkdir(parents=True,exist_ok=True);dump(a.out,output)
    print({n:{s:r['historical'][s]['nominal_kappa'] for s in ('all','en','es')} for n,r in output['panels'].items()})


if __name__=='__main__': main()
