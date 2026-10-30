# ReEval-2: held-out human validation of the verbal labels

Status: **draft, not frozen.** The protocol is frozen by the commit that removes
this line; the commit hash is cited in the manuscript. Any later change is
logged under [Deviations](#deviations) with its date and reason.

## 1. Purpose and scope

The first human reference (`data/reeval/`) covers 320 judged turns of one model
(gpt-oss-120b). Each turn has one external label and one label by the first
author, who also adjudicated the disagreements. ReEval-2 adds a held-out sample
that addresses the three limits of that design:

| Limit of the first reference | ReEval-2 |
|---|---|
| One external annotator per turn, disjoint subsets | Two annotators label **every** turn of a shared sample |
| The first author labelled and adjudicated | No author labels or adjudicates |
| One evaluated model | The nine other models, both languages, all three panel labels |

ReEval-2 measures how well the judge panel used for those nine models (the
*cohort configuration*: DeepSeek V4 Flash and Gemini 3.1 Flash Lite, Qwen3.6
tie-breaker) agrees with human judgement on their responses. It does not
change the panel, the campaign labels or any functional outcome, and it is not
used to select a judge configuration. Whatever the results, they are reported.
Agreement is reported as measured; it is not described as validation.

## 2. Sample

Built by `scripts/build_reeval2_sample.py` from the archived campaign
(`data/runs/<model>/responses.jsonl` and `vcr.jsonl`, hashes in the manifest).

- **Frame.** All 21,600 judged turns of the nine cohort models.
- **Strata.** Model x language x panel label (54 strata).
- **Allocation.** Per model and language: 3 capitulated, 3 hedged, 4 firm
  (180 turns). A stratum with fewer turns than requested gives its shortfall
  to `firm` of the same model and language. This happens once: Claude Opus 4.8
  has a single English turn labelled capitulated, so that cell has 1
  capitulated and 6 firm.
- **Selection.** Simple random sampling within each stratum, seed `20261030`
  per stratum; at most one turn per conversation. Realized: 74 firm, 54 hedged
  and 52 capitulated panel labels; 90 English and 90 Spanish turns; 47 of the
  50 source problems.
- **Presentation.** Each turn is shown as the judges saw it: the whole judged
  conversation with the assistant's code removed and the central bug as
  anchor. Only the sampled turn is marked for classification; the other
  assistant turns are context. Order is shuffled once (seed `20261031`).
- **Sealed key.** Model identity, panel label, judge votes and design weights
  are in `sample_key.jsonl`, which is never loaded into the annotation
  application. Its SHA-256 is fixed before annotation:

| File | SHA-256 |
|---|---|
| `sample_key.jsonl` | `4aeb43d50dbf78f97b10917eea4ada6387316e1d8b93b4a9bb18fe09a03bcffe` |
| `pool.jsonl` | `c4821a76b918cdf3a81ac22955a12eff300e74ba2934f2fbff8750a8e5f426a1` |

The sample is deterministic: rerunning the script on the same archive gives
the same files.

## 3. People and roles

| Role | Who | Sees |
|---|---|---|
| Annotator A1 | Researcher who is not an author and did not work on SycoCode | Conversation, rubric, own labels |
| Annotator A2 | Same conditions as A1 | Conversation, rubric, own labels |
| Adjudicator | Researcher who is not an author; does not annotate | Conversation, rubric, both labels and notes for disagreements only |
| Control | First author | Progress counts; exports after both annotators finish |

Nobody sees the model identity or the panel label. The first author does not
label, adjudicate or discuss cases with the annotators or the adjudicator.

## 4. Procedure

1. **Calibration.** Before starting, each annotator labels a calibration set of
   turns from the first reference (not part of this sample) and then reads their
   reference labels and rationales. Calibration labels are not analysed.
2. **Annotation.** Each annotator labels all 180 turns individually, without AI
   assistance and without discussing cases. They follow the written rubric
   (`docs/methodology/vcr_rubric.md`, version 1.1). The application keeps the
   first label and every later edit.
3. **Adjudication queue.** When both annotators have finished, the queue is
   every turn whose two **current** labels differ. Turns whose first labels
   differed but converged are reported, not adjudicated.
4. **Adjudication.** The adjudicator chooses one of the three labels for each
   queued turn and writes a rationale. They may choose a label neither annotator
   gave.
5. **Reference.** The reference label is the common label where the annotators
   agree and the adjudicated label otherwise.

## 5. Analysis plan

Run by `scripts/score_reeval2.py` (tests: `scripts/test_score_reeval2.py`).
Every estimate is given twice: over the sample as drawn, and with design
weights (stratum size divided by turns sampled), which estimate agreement over
all judged turns of the nine models. Intervals are 95% percentiles of 10,000
bootstrap resamples of source problems (seed `20261101`), keeping the design
weights fixed.

Reported quantities:

1. Human-human agreement: Cohen's kappa between A1 and A2 on first labels
   (primary) and on current labels; by language.
2. Panel against the reference: raw agreement, Cohen's kappa, linear-weighted
   kappa; by language; per-class recall and precision.
3. Panel against each annotator separately, which does not depend on
   adjudication.
4. Capitulation: precision of the panel's capitulated label and recall of
   human capitulations. Pre-specified secondary rule, from the stored votes:
   label a turn capitulated if any judge voted capitulated. It is reported, not
   adopted.
5. Per model: counts and raw agreement, descriptive only (20 turns each).

There is no acceptance threshold and no decision depends on the results. The
recall of human capitulations hidden among panel-firm turns rests on few
sampled turns and is reported with its interval.

## 6. Use in the manuscript

The results add a held-out row to the agreement table and replace the
statement that the cohort configuration has no human check on its own models.
Verbal metrics stay secondary and descriptive. The text says "agreement with
human labels", never "validated".

## 7. Release

After the analysis, the sample (pseudonymised annotator labels, adjudications
and rationales, without account names) and the scores are released with the
next software version, in the same form as `data/reeval/`.

## Deviations

None yet.
