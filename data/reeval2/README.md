# Held-out human reference for the verbal labels (ReEval-2)

`held_out_reference_v1.jsonl` is the *held-out reference*: human labels for a
stratified sample of 180 judged turns of the nine evaluated models other than
the pilot model, against which the judge panel's verbal labels for those models
are compared. It complements the *pilot reference* in
[`data/reeval/`](../reeval/README.md), which covers the 320 judged turns of the
pilot model (gpt-oss-120b). "ReEval-2" is the internal name of the study and
of its files.

The study was run under a written protocol,
[`docs/methodology/reeval2_protocol.md`](../../docs/methodology/reeval2_protocol.md)
(SHA-256 `4fd002b78fda14fb17a1002f688380f56b054b4941c66508f7d86a1b27ca876f`),
released unchanged. The deviations from it, the limits of the procedure and
the two analyses the data did not allow are recorded in
[`docs/methodology/reeval2_protocol_record.md`](../../docs/methodology/reeval2_protocol_record.md).

The result is agreement with human labels. It is moderate, and it does not
validate the panel; verbal results remain secondary and descriptive.

## Sample

Built by `scripts/build_reeval2_sample.py` (seed `20261030`) from the 21,600
judged turns of the nine cohort models. Strata: model × language × panel label
(54 strata). Per model and language: 3 turns labelled `capitulated` by the
panel, 3 `hedged` and 4 `firm`, at most one turn per conversation; Claude Opus
4.8 has a single English turn labelled `capitulated`, so that cell has 1
capitulated and 6 firm. Realised: 180 turns, 20 per model, 90 English and 90
Spanish; 74 firm, 54 hedged and 52 capitulated panel labels; 47 of the 50
source problems; 47 single-turn turns (code review 22, expertise deference 25)
and 133 multi-turn turns (insistent 115, answer flip 18). The sample
over-represents the panel's `hedged` and `capitulated` labels by design; each
turn carries a design weight (stratum size / turns sampled, from 1 to 287,
summing to 21,600) so that estimates can also be weighted to all judged turns
of the nine models.

The judge configuration under test is the cohort configuration (DeepSeek V4
Flash and Gemini 3.1 Flash Lite, Qwen3.6 tie-breaker), i.e. the labels archived
in the campaign. The tie-breaker decided 43 of the 180 sampled turns.

## Annotation

- **People.** Two annotators, A1 and A2, each labelled all 180 turns
  individually in the annotation application (`webapp/`, crossed design) and
  declared at hand-in that they worked without AI and without discussing cases. A
  third person, who did not annotate, adjudicated the turns on which their
  labels differed. The three are researchers from the authors' research group
  and are not authors; none built the sample, wrote the rubric or chose the
  judges. They are the same three people who were the external annotators of
  the pilot reference, so they knew rubric 1.1 and may have seen some of the
  11 optional calibration turns before. They appear only as
  `a1`, `a2` and `adj`; the fourth account, `control`, is the first author's,
  which saw only progress counters until closure. The first author did not
  label, adjudicate or discuss cases.
- **Blinding.** Nobody saw model identity, judge votes or panel labels. Record
  identifiers in the application were opaque (`r2r####`), and each annotator
  worked in a different deterministic order.
- **Rubric.** VCR rubric 1.1 (`docs/methodology/vcr_rubric.md`), with one rule
  declared in the protocol (section 4.3) before any human label of this sample:
  in single-turn responses humans judge the acceptance or rejection of the
  user's position on the central bug. The judges did not have this rule.
- **Hand-in and adjudication.** Each annotator handed in once, with a dated
  declaration (individual work, no AI, no discussion of cases) stored with a
  SHA-256 of their labels; hand-in locks the labels. The second hand-in cut the
  adjudication queue automatically: the 51 turns whose current labels differ.
  The adjudicator chose a label for each, with a written rationale, and could
  choose a label neither annotator gave.
- **Reference rule.** The annotators' common current label where they agree
  (129 turns, `label_source = agreed`); the adjudicated label otherwise (51,
  `adjudicated`). Result: 97 `firm`, 33 `hedged`, 50 `capitulated`.

## Files

| File | What it is | SHA-256 |
|---|---|---|
| `held_out_reference_v1.jsonl` | One row per turn: key, both annotators' labels, adjudication, reference label (built by `scripts/export_reeval2_reference.py`) | `83408a8ee061b55c7a2893bade02deec915a3a249d0602183ef680c09804aa6a` |
| `reeval2_scores.json` | Output of the pre-specified scorer `scripts/score_reeval2.py` | `3343f69114e5fb58a484bbaa7bdc6c9d4bc0f62731aaf38c0cad05d4936aba60` |
| `reeval2_exploratory.json` | Output of `scripts/reeval2_exploratory.py`: checks that are **not** in the analysis plan (agreed and adjudicated turns, tie-breaker, bounds, the turn that is not a model reply), reported as exploratory | `af0149fef255591c72fc25e46fd35c232fa9dee37bc5f07b78e353e84963dfcc` |
| `sample_key.jsonl` | The sealed key, unsealed after closure: model, real record identifier, panel label, judge votes, design weight, payload hash | `4aeb43d50dbf78f97b10917eea4ada6387316e1d8b93b4a9bb18fe09a03bcffe` |
| `pool.jsonl` | The pool loaded in the application (opaque record identifiers, no model identity, no panel label) | `24acb0ee8a6a68b0238edfd0e0337ae9ecb81a8fca281c7bae01d8b8c35c8c31` |
| `pool_manifest.json` | Seeds, frame hashes, per-stratum counts, display order, hashes of key and pool | `c3528efc7a19c9434ab0c0f635b17d4db019f68f3ea4f433780b6b33084d4af9` |
| `export/` | The six files the application served at closure, byte-identical, plus `SHA256SUMS` | see `export/SHA256SUMS` |

The key and pool hashes are the ones fixed in the protocol before annotation.

### Application exports (`export/`)

| File | Content |
|---|---|
| `sycocode-jsonl.jsonl` | 360 label rows (180 turns × 2 annotators): first and current label, note, version, dates, payload hash |
| `sycocode-csv.csv` | The same rows as CSV (UTF-8 with byte-order mark) |
| `sycocode-events.jsonl` | Every save of every label (420 events) |
| `sycocode-agreement.jsonl` | The application's quick A1–A2 agreement on first labels; the citable analysis is `reeval2_scores.json` |
| `sycocode-reeval-adjudications.jsonl` | The 51 adjudicated turns: both annotators' labels and history, the decision, its rationale and its revisions |
| `sycocode-audit.jsonl` | Hand-ins with declaration and digest, exposure records (who opened which conversation, when), study events (password resets, queue cut, closure) and export records |

The fields `label_source: "human_independent"` and `provenance: "external_human_annotation"` in the exports are constants that the application writes for every human label. They are not a claim of independence beyond what the protocol record states: the three participants are not authors, belong to the authors' research group and had annotated the pilot reference.

The server's audit log records the SHA-256 of four of these files (labels
JSONL, labels CSV, events and agreement), each equal to the released file. The
audit log cannot contain its own hash, and the adjudication export is not
among the downloads it records, so those two are covered by `SHA256SUMS` only. Notes and
adjudication rationales are free text in Spanish, released verbatim; they
contain no names. Accounts appear only under their pseudonyms.

### Conversation payloads are not distributed

The text shown to annotators (each judged conversation, code removed, as the
judges saw it) consists of outputs of the nine evaluated models, which this
repository does not redistribute (see the main README). Each turn's
`payload_sha256` (in the key, the label exports and the reference) lets anyone
who holds the campaign transcripts check that a payload is the one that was
annotated, and `study_sha256` in the label exports is the application's
fingerprint of the pool, the manifest and all 180 payloads in display order.
`payload_path` in `pool.jsonl` is the path from which the application loaded
each payload; those files are not in the repository.

### Fields of `held_out_reference_v1.jsonl`

| Field | Meaning |
|---|---|
| `unit_id`, `group_id` | Turn and conversation identifiers used throughout the study |
| `record_id`, `pool_record_id` | Campaign record identifier (names the run and model) and the opaque identifier shown in the application |
| `item_id`, `problem_ref`, `model` | Benchmark item, source problem and evaluated model |
| `judged_turn`, `language`, `scenario`, `scenario_type` | Judged turn, `en`/`es`, pressure scenario and `single_turn`/`multi_turn` |
| `rubric_version`, `payload_sha256` | Rubric version (1.1) and SHA-256 of the payload shown |
| `design_weight`, `stratum_size` | Design weight and size of the turn's stratum |
| `a1_first_label`, `a1_current_label`, `a2_first_label`, `a2_current_label` | Each annotator's first label and label at hand-in |
| `in_adjudication_queue` | Whether the current labels differ |
| `adjudicated_label`, `adjudication_rationale`, `adjudication_versions` | The adjudicator's final label, rationale (verbatim, Spanish) and number of versions |
| `reference_label`, `label_source` | Label in the held-out reference; `agreed` or `adjudicated` |
| `panel_label_archived`, `tiebreak_used` | The panel's archived label and whether the tie-breaker decided it |

## Reproducing

From the repository root. The reference needs only the standard library; the
scorer needs NumPy (`requirements-replay.lock` pins 2.0.2; the outputs were
also checked byte for byte with a newer NumPy).

```bash
# 1. Integrity of the exports
(cd data/reeval2/export && shasum -a 256 -c SHA256SUMS)

# 2. Reference: checks the exports against the server's records, then builds the file
python scripts/export_reeval2_reference.py --out /tmp/held_out_reference_v1.jsonl
cmp /tmp/held_out_reference_v1.jsonl data/reeval2/held_out_reference_v1.jsonl

# 3. Every pre-specified estimate (10,000 bootstrap resamples; a few seconds)
python scripts/score_reeval2.py --key data/reeval2/sample_key.jsonl \
  --labels data/reeval2/export/sycocode-jsonl.jsonl \
  --adjudication data/reeval2/export/sycocode-reeval-adjudications.jsonl \
  --annotators a1,a2 --out /tmp/reeval2_scores.json
cmp /tmp/reeval2_scores.json data/reeval2/reeval2_scores.json

# 4. Scorer tests (16 checks)
python scripts/test_score_reeval2.py

# 5. Exploratory checks, not in the analysis plan (Supplementary Table S11.12)
python scripts/reeval2_exploratory.py --out /tmp/reeval2_exploratory.json
cmp /tmp/reeval2_exploratory.json data/reeval2/reeval2_exploratory.json
```

Step 2 prints one line per check. It recomputes the SHA-256 of each file whose
download the server logged, each annotator's hand-in digest and the
annotation-state digest logged at the queue cut and at closure, and refuses to
write the reference if any differs. The two digests use the application's own
recipe: a SHA-256 of compact, key-sorted JSON (`ensure_ascii=False`,
separators `,` and `:`) of, for the hand-in, the annotator's rows sorted by
`unit_id` with `unit_id`, `first_label`, `label`, `note`, `version` and
`events` as `[version, label, note]` lists
(`own_annotations_sha256` in `webapp/annotations/reeval2.py`); and for the
annotation state, all 360 rows sorted by unit and annotator with
`current_label` and event objects (`annotation_state_sha256` in
`webapp/annotations/provenance.py`). All eight checks pass on the released
files.

## Results (pre-specified analysis)

Intervals are 95% percentiles of 10,000 bootstrap resamples of the 47 source
problems (seed `20261101`). *Sample* is the 180 turns as drawn; *weighted* uses
the design weights and estimates agreement over all 21,600 judged turns of the
nine models.

| | Agreement | Cohen's κ (95% CI) | Weighted κ (95% CI) |
|---|---|---|---|
| A1 vs A2, first labels (primary) | 121/180 = 67.2% | 0.479 (0.40–0.57) | 0.402 (0.29–0.53) |
| A1 vs A2, labels at hand-in | 129/180 = 71.7% | 0.554 (0.48–0.63) | 0.511 (0.38–0.64) |
| **Panel vs held-out reference** | 133/180 = 73.9% | **0.594 (0.50–0.68)** | **0.618 (0.49–0.73)** |
| Panel vs A1 alone (hand-in) | 68.3% | 0.506 (0.42–0.59) | 0.573 (0.46–0.68) |
| Panel vs A2 alone (hand-in) | 71.1% | 0.557 (0.45–0.66) | 0.490 (0.36–0.62) |
| Panel vs reference, single-turn (47) | 45/47 | 0.776 (0.36–1.00) | 0.569 (0.08–1.00) |
| Panel vs reference, multi-turn (133) | 88/133 | 0.499 (0.40–0.60) | 0.582 (0.45–0.71) |

Per class, panel against the reference (sample): `firm` recall 71/97 = 0.73,
precision 71/74 = 0.96; `hedged` recall 21/33 = 0.64, precision 21/54 = 0.39;
`capitulated` recall 41/50 = 0.82 (0.67–0.94), precision 41/52 = 0.79
(0.67–0.91). The two annotators disagree mostly at the hedged/capitulated
boundary: 29 of the 51 disagreements at hand-in are A1 `hedged` against A2
`capitulated`. By language the sample κ is 0.633 (English) and 0.555
(Spanish); no test was pre-specified and no language difference is claimed.
Per-model counts (20 turns each) are descriptive only. Linear-weighted κ,
Krippendorff's α, the pre-specified alternative rule "capitulated if any judge
says so" (reported, not adopted) and all intervals are in
`reeval2_scores.json`.

What these results support: the panel's agreement with the held-out reference
is moderate and weakest on `hedged`. Against each annotator alone (κ 0.506
and 0.557) the panel agrees about as well as the two annotators agree with
each other at hand-in (0.554); agreement with the reference (0.594) is not
comparable with these, because the reference is built from both annotators.
On these nine models it found 41 of the 50 human
capitulations, and none of the 9 it missed carries the panel label `firm`.

Limits, which apply to every use of these numbers:

1. The panel is not validated or shown reliable: both intervals for κ include
   values below 0.6.
2. Capitulation recall depends on whose threshold is used (25 of A1's 27
   capitulations, 43 of A2's 61), and 23 of the 50 reference capitulations rest
   on one adjudicator's decisions.
3. The sample has no human capitulation among single-turn responses, so the
   pilot's finding that the panel missed all 5 single-turn capitulations could
   not be re-tested; the capitulation figures are multi-turn figures.
4. No capitulation was found among the 74 sampled turns the panel labelled
   `firm`, so the bootstrap gives no interval for capitulations hidden there
   (rule of three: about 4%, ignoring clustering and weights); those turns are
   17,581 of the 21,600.
5. The result is not comparable with the pilot reference as an improvement of
   the panel: other models, other annotator pairs, a stratified sample and an
   extra rule for single-turn responses.
6. Independence is limited: the three participants are from the authors'
   research group, also annotated the pilot reference, and one person
   adjudicated alone.

Released under CC BY 4.0, like the rest of the dataset (`LICENSE-DATASET`).
