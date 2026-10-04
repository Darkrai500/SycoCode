#!/usr/bin/env python3
"""Render compact review tables from frozen revision-analysis evidence."""
import argparse
import json
from pathlib import Path

DISPLAY={'full':'gpt-oss-120b','gemini-3-1-flash-lite':'Gemini 3.1 Flash Lite','gemini-3-5-flash':'Gemini 3.5 Flash',
 'glm-5-2':'GLM 5.2','kimi-k-2-6':'Kimi K2.6','claude-opus-4-8':'Claude Opus 4.8',
 'claude-sonnet-4-6':'Claude Sonnet 4.6','gpt-5-5':'GPT-5.5','gpt-5-4-mini':'GPT-5.4 Mini','minimax-m3':'MiniMax M3'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--evidence-root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.out.exists():ap.error('new output directory required')
    a.out.mkdir(parents=True)
    s=json.loads((a.evidence_root/'statistics.json').read_text());p=json.loads((a.evidence_root/'sensitivity.json').read_text())
    pct=lambda v:'NA' if v is None else f'{100*v:.2f}'
    interval=lambda d:pct(d['estimate'])+' ['+', '.join(pct(v) for v in d['ci95'])+']'
    lines=['# Tablas históricas/provisionales · 19/09/2026','',
     'IC95% percentiles por problema, B=10.000, semilla 20260919. Tasas en %; diferencias en puntos porcentuales.',
     '','## FR y comparación funcional EN/ES en soporte común','',
     '| Modelo | n FR | Problemas FR | FR [IC95%] | Pares EN/ES | Δ ES−EN [IC95%] | p Holm (10) |',
     '|---|---:|---:|---|---:|---|---:|']
    tex=[];sens=[]
    for slug in sorted(s['models'],key=lambda x:DISPLAY[x].lower()):
        r=s['models'][slug];b=r['bsg_common_support'];n=DISPLAY[slug]
        lines.append(f"| {n} | {r['fr']['n']} | {r['fr']['clusters']} | {interval(r['fr'])} | {b['n']} | {interval(b)} | {b['p_holm_within_10_models']:.3f} |")
        tex.append(f"{n} & {r['fr']['n']} & {interval(r['fr'])} & {b['n']} & {interval(b)} \\")
        q=p[slug];sens.append(f"{n} & {pct(q['historical']['fr'])} & {pct(q['cap_only']['fr'])} & {pct(q['no_requotes']['fr'])} & {pct(q['all_extracted']['fr'])} \\")
    lines+=['','## Sensibilidad de endoso y exclusiones','',
     '| Modelo | FR actual | FR solo cap. | FR sin recitas | FR todo bloque | Finales cambiados: solo cap. / todo | n sin recitas / sin errores / código final |',
     '|---|---:|---:|---:|---:|---:|---:|']
    for slug,q in p.items():
        lines.append(f"| {DISPLAY[slug]} | {pct(q['historical']['fr'])} | {pct(q['cap_only']['fr'])} | {pct(q['no_requotes']['fr'])} | {pct(q['all_extracted']['fr'])} | {q['cap_only']['final_known_changed']} / {q['all_extracted']['final_known_changed']} | {q['exclude_requotes']['conditioned_n']} / {q['exclude_execution_errors']['conditioned_n']} / {q['require_final_code']['conditioned_n']} |")
    lines+=['','Las tres reglas de endoso mantienen los denominadores históricos en esta cohorte; las exclusiones cambian la población. Los resultados de exclusión no son estimadores corregidos de la misma población.','',
     '## Extracción: cotas de FR en la población elegible histórica','',
     'Adopción de todo candidato en las dos alternativas. Comparar con `all_extracted` para separar extracción y endoso. Solo se reutiliza un veredicto de código idéntico dentro del mismo modelo/problema. Un bloque no evaluado queda desconocido.','',
     '| Modelo | Primer entrypoint: desconocidos / n | Cota FR % | Último bloque: desconocidos / n | Cota FR % |',
     '|---|---:|---|---:|---|']
    for slug,q in p.items():
        x,y=q['first_entrypoint'],q['last_fence'];fmt=lambda r:'['+', '.join(pct(v) for v in r['fr_on_historical_support_bounds'])+']'
        lines.append(f"| {DISPLAY[slug]} | {x['historical_support_unknown']} / {x['historical_support_n']} | {fmt(x)} | {y['historical_support_unknown']} / {y['historical_support_n']} | {fmt(y)} |")
    lines+=['','## Familias de contraste','',
        f"Entre modelos: {sum(r['p_holm_within_45_pairs']<.05 for r in s['pairwise_models'])}/45 contrastes exploratorios con p de cambio de signo por problema <0,05 tras Holm. Cada par tiene soporte común propio; no forman un ranking global.",
        'Los IC son marginales, no intervalos simultáneos ajustados. Los p presuponen intercambiabilidad conjunta del signo dentro de cada problema; los idiomas/modelos no fueron asignados al azar.',
        'El archivo `statistics.json` conserva tamaños de efecto, pesos, diferencias pareadas con controles, subgrupos, turnos, exclusión de insistencia y leave-one-problem-out. Categorías con menos de cinco problemas no reciben IC inferencial.']
    (a.out/'tables.md').write_text('\n'.join(lines)+'\n')
    # End each LaTeX row with the two-character row separator.
    (a.out/'statistics_rows.tex').write_text('\n'.join(x+'\\' for x in tex)+'\n')
    (a.out/'sensitivity_rows.tex').write_text('\n'.join(x+'\\' for x in sens)+'\n')


if __name__=='__main__':main()
