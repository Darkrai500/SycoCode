# Human reference for the verbal labels (v1)

`human_reference_v1.jsonl` is the human reference against which SycoCode's
judge panel is evaluated. It replaces the historical reference in
`data/goldset/gold.jsonl`, in which only 41 of 320 labels were human.

## Sample

The 320 judged turns of the pilot model (gpt-oss-120b) already used to select
the panel (`data/goldset/pool.jsonl`): 200 conversations from 49 problems,
160 English and 160 Spanish turns, all five pressure scenarios. The
transcripts shown to annotators are the code-free payloads in
`data/goldset/payloads/`, the same text given to the judges. Labels follow
rubric v1.1 (`docs/methodology/vcr_rubric.md`): `firm`, `hedged` or
`capitulated`.

## Annotation

Every turn has two human labels:

- **Author.** The first author labelled all 320 turns in the annotation
  application (`webapp/`) by reviewing labels proposed by AI assistants
  (Codex and Claude, neither of which is a panel judge) and changing those he
  disagreed with. These labels were entered before any external label and
  were never edited. They are not blind: the first author also wrote the
  rubric and had seen model pre-labels for this set when the historical
  reference was built.
- **External annotator.** Three researchers from the authors' computer
  science research group, with no previous involvement in SycoCode, labelled
  disjoint subsets by hand and without AI (E1: 109 turns, E2: 106, E3: 105).
  Their accounts showed only their own assignments. The application keeps
  each annotator's first label and stores later edits as new versions.

Because the external subsets are disjoint, agreement among E1, E2 and E3
cannot be measured; agreement is reported between the author and each
external annotator.

## Reference rule

The rule was fixed before the first adjudication decision:

- Turns on which the author's label and the external annotator's current
  label agree take that label (278 turns, `label_source = pair_agreement`).
- The 42 turns in the review queue (35 current disagreements and seven turns
  that had entered the queue through earlier disagreements or label changes)
  were adjudicated individually by the first author, who formed a judgement
  before reading the external label, saw no judge output and recorded a
  written rationale (`label_source = adjudication`).

Result: 280 `firm`, 21 `hedged`, 19 `capitulated`. Of the 35 adjudicated
disagreements, 16 were resolved towards the author's label, 17 towards the
external label and two to the third category.

No reference label rests on an AI proposal alone: the external label, made by
hand, agrees with the reference in 301 of the 320 turns (278 agreed and 23
adjudicated), and the author's label prevails over it in only 16.

## Fields

| Field | Meaning |
|---|---|
| `unit_id`, `record_id`, `item_id`, `judged_turn` | Identify the judged turn; `record_id` + `judged_turn` join with `data/goldset/pool.jsonl` and `votes.jsonl` |
| `language`, `scenario`, `rubric_version` | Language (`en`/`es`), pressure scenario and rubric version |
| `external_annotator` | Pseudonym of the external annotator (`E1`, `E2`, `E3`) |
| `author_label` | The first author's label |
| `external_first_label` | The external annotator's first label |
| `external_label_at_adjudication` | The external annotator's current label when the reference was built |
| `in_review_queue` | Whether the turn was adjudicated |
| `reference_label` | Label in the frozen reference |
| `label_source` | `pair_agreement` or `adjudication` |
| `adjudication_rationale` | The adjudicator's rationale, verbatim and in Spanish (adjudicated turns only) |
| `panel_label_archived` | The label assigned by the judge panel during the campaign run |

No names, account identifiers, timestamps or server records are included.

## Scoring

```bash
python scripts/score_human_reference.py --out agreement.json
```

The script needs only NumPy and reproduces the agreement statistics reported
for SycoCode v1.1.0, including problem-clustered bootstrap intervals and the
sensitivity of panel agreement to the choice of reference (see
`docs/reproducibility/README.md`).

## Scope

The reference covers one evaluated model and is not a held-out sample; it
does not validate the verbal labels of the other nine models. Released under
CC BY 4.0, like the rest of the dataset (`LICENSE-DATASET`).
