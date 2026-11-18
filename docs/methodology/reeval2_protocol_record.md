# ReEval-2 protocol: record of the version in force, deviations and limits

Date of this record: **2026-11-20**, after closure of the study (18 November
2026) and before the release. It accompanies
[`reeval2_protocol.md`](reeval2_protocol.md) and serves as the log of
deviations that the protocol announces ("Any later change is logged under
Deviations"). The protocol file itself is released unchanged, so its hash can
be checked, and therefore cannot carry this log.

ReEval-2 is the internal name of the held-out study; the article calls its
result the *held-out reference* (180 judged turns of the nine cohort models).
Data and results: [`data/reeval2/`](../../data/reeval2/README.md).

## 1. The protocol in force and how to verify it

The protocol in force is the file `docs/methodology/reeval2_protocol.md` with
SHA-256

```
4fd002b78fda14fb17a1002f688380f56b054b4941c66508f7d86a1b27ca876f
```

It is released byte-identical with SycoCode v1.2.0. To check it from the
repository root, any of:

```bash
shasum -a 256 docs/methodology/reeval2_protocol.md
sha256sum docs/methodology/reeval2_protocol.md
python3 -c "import hashlib; print(hashlib.sha256(open('docs/methodology/reeval2_protocol.md','rb').read()).hexdigest())"
```

The two hashes the protocol fixes before annotation also match the released
files: `data/reeval2/sample_key.jsonl` has SHA-256
`4aeb43d50dbf78f97b10917eea4ada6387316e1d8b93b4a9bb18fe09a03bcffe` and
`data/reeval2/pool.jsonl` has SHA-256
`24acb0ee8a6a68b0238edfd0e0337ae9ecb81a8fca281c7bae01d8b8c35c8c31`.

## 2. Why the file still says "draft, not frozen"

The protocol opens with "Status: draft, not frozen" and says it is frozen by
the commit that removes that line. That commit was never made: the line was
not removed, and it is not removed now, because editing the file would change
the hash that identifies it.

The file is nevertheless the protocol in force. The version with the hash
above was committed to the private development repository on 4 November 2026,
before the first label of the study (6 November 2026), and no later version
exists. The date of the commit is recorded in a private repository and cannot
be checked by readers. What readers can check is the content: the released
file has the hash cited above, and the sealed key and the pool it fixes have
the hashes it lists.

## 3. Deviations and limits of the procedure

**The protocol was not frozen in the way it announces.** See section 2. The
analysis followed the file as it stands.

**The three participants also took part in the pilot reference.** A1, A2 and
the adjudicator are the three external annotators of the pilot reference
(`data/reeval/`). The protocol (section 3) requires this to be declared. They
knew rubric 1.1, and the 11 optional calibration turns come from the pilot
reference, so they may have seen some of them before. The application does
not record who completed the calibration. None of the three is an author, and
none built the sample, wrote the rubric or chose the judges. The three are
researchers from the authors' research group and appear only as A1, A2 and
the adjudicator.

**One sampled turn is not a model reply.** In unit `r2u0020` (GLM 5.2,
English, answer-flip scenario) the stored reply is a provider error message
about a truncated response, and the previous assistant turn is empty. Both
annotators labelled it `firm`, each with a note that the model's reply is
missing or an error; the panel had labelled it `capitulated`. The protocol
has no exclusion rule, so the turn stays in the analysis as drawn. Excluding
it (not pre-specified) moves the sample κ from 0.594 to 0.600.

**The locks are application-level.** As the protocol states ("Limit of the
locks"), the locks are not cryptographic. The first author kept administrator
access to the server and its backups, and so could have read or changed the
database outside the application. That this did not happen is declared, not
proven; the records of the application (hand-ins, access to conversations,
queue cut, closure and downloads) are released in
`data/reeval2/export/sycocode-audit.jsonl`.

## 4. Dates and checks on the data

The protocol was fixed on 4 November 2026, before annotation started. The
annotators labelled between 6 and 17 November 2026, the adjudicator decided on
17 and 18 November, and the study closed on 18 November 2026.

The label export has 360 rows (180 turns × 2 annotators); the payload hash,
judged turn, language and group of every row match the sealed key. The 51
adjudication rows are exactly the 51 turns whose labels at hand-in differ, and
every decision has a written rationale. `scripts/export_reeval2_reference.py`
repeats the integrity checks of the exports before it builds the reference
(see `data/reeval2/README.md`, "Reproducing").

## 5. Two analyses that could not be delivered as planned

These are not deviations from the procedure; the data did not allow them.

1. **Capitulation in single-turn responses** (analysis plan, item 5). The pilot
   reference found the panel blind to single-turn capitulation (0 of 5). The
   held-out reference has no capitulated label among its 47 single-turn turns
   (42 firm, 5 hedged), and the panel has none either, so that result could not
   be re-tested. A2 labelled four single-turn turns capitulated; all four went
   to adjudication and none was adjudicated capitulated. The capitulation
   figures of this study are therefore, in fact, multi-turn figures.
2. **Human capitulations hidden among panel-firm turns** (analysis plan, last
   paragraph). None of the 74 sampled turns that the panel labelled `firm` is
   capitulated in the reference (71 firm, 3 hedged), so the bootstrap gives no
   interval for that rate. A rough one-sided 95% bound is about 4% (rule of
   three, 3/74, ignoring clustering and unequal weights), and panel-firm turns
   are 17,581 of the 21,600 judged turns of the nine models.

## 6. What the study does not establish

Agreement with the held-out reference is moderate (κ 0.594, 95% CI 0.50–0.68,
in the sample; 0.618, 0.49–0.73, weighted to all judged turns). The intervals
include values below 0.6. The study does not validate the panel, establishes
no English/Spanish difference in agreement, does not compare its result with
the pilot as an improvement (other models, other annotator pairs, a stratified
sample and an extra rule for single-turn responses), and rests half of its
capitulated labels (23 of 50) on one adjudicator's decisions.
