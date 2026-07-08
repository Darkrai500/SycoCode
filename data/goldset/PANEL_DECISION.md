# VCR judge panel — final decision (2026-06-13)

Selected **empirically** by `eval/judge_harness` against the human-validated gold
set (`gold.jsonl`, 320 turns: 41 JC-committed + 279 prelabel-proxy, κ(JC,proxy)=0.655).
Sweep: 5 candidate judges × 2 protocols × 200 transcripts = 2000 calls, all via
OpenRouter (date-pinned slugs), `reasoning_effort=low`. Gate: Cohen κ ≥ 0.6.
**Real measured cost = $3.78** (plan estimated $1.74; reality higher because
reasoning models emit ~807 completion tok/call vs the 250 assumed — qwen ~1900,
glm-5.1 priciest; neither is in the chosen panel). One-time selection spend.

## Chosen panel (2+1, protocol = `binary`)

| role | model (OpenRouter slug) |
|---|---|
| fixed 1 | `deepseek/deepseek-v4-flash-20260423` |
| fixed 2 | `google/gemini-3.1-flash-lite-20260507` |
| tiebreak | `deepseek/deepseek-v4-pro-20260423` |

**κ vs gold = 0.756** (EN 0.708 · ES 0.771), disagreement rate 15%, invalid-JSON 0%.
Chosen over the best `direct` panel (v4-pro+qwen+glm-5.1, κ=0.755, EN 0.61/ES 0.811,
~2.4× pricier) for tied κ, **better cross-language balance**, and lowest cost (the two
always-on judges are the cheapest models; the pricier tiebreak fires only on ~15%).

## Per-voter κ vs gold (320 turns, gate 0.6)

| judge::protocol | κ | κ_EN | κ_ES | passes |
|---|---|---|---|---|
| glm-5.1::direct | 0.730 | 0.61 | 0.771 | ✓ (best single) |
| qwen3.6-35b-a3b::direct | 0.691 | 0.614 | 0.721 | ✓ |
| deepseek-v4-pro::direct | 0.641 | 0.49 | 0.689 | ✓ |
| deepseek-v4-pro::binary | 0.632 | 0.373 | 0.767 | ✓ |
| gemini-flash-lite::binary | 0.630 | 0.556 | 0.669 | ✓ |
| deepseek-v4-flash::direct | 0.565 | 0.449 | 0.607 | ✗ |
| (others below gate) | | | | |

## Caveats (report in the thesis)
- Gold is a **silver standard**: human (JC) on 41 units + frontier-proxy (Opus/Fable
  session agent) on 279, the proxy validated by κ(JC,proxy)=0.655 on the overlap.
- Gold label distribution is **firm-skewed** (291/19/10): κ corrects for chance, but
  the minority-class (hedged/capitulated) estimate rests on ~29 units.
- Provider is a confound — slugs are date-pinned and routed via OpenRouter; report it.

Artifacts: `votes.jsonl`, `judge_report.json`, `panel_sim.json`, `gold_stats.json`.
