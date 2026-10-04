"""Guards for scientific provenance, missing votes and partial human overlap."""
import unittest
import json
import tempfile
from pathlib import Path

from audit_reeval import FIXED, kappa, panel, score, validate, provenance_manifest


class ReevalTests(unittest.TestCase):
    def test_provenance_requires_exact_accounts_and_documented_evidence(self):
        self.assertEqual(provenance_manifest(None, {'jc'}), {})
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'provenance.json'
            entry = {'label_source': 'human_reviewed', 'evidence': ['Explicit owner confirmation']}
            p.write_text(json.dumps({'accounts': {'jc': entry}}))
            self.assertEqual(provenance_manifest(p, {'jc'})['accounts']['jc'], entry)
            with self.assertRaises(ValueError):
                provenance_manifest(p, {'jc', 'evaluator-a'})
            p.write_text(json.dumps({'accounts': {'jc': dict(entry, evidence=[])}}))
            with self.assertRaises(ValueError):
                provenance_manifest(p, {'jc'})

    def setUp(self):
        self.pool = {"u1": {"unit_id": "u1", "group_id": "g1", "record_id": "r1", "judged_turn": 2, "language": "en"}}
        self.row = dict(self.pool["u1"], annotator="alice", first_label="firm", label="firm", version=1,
                        study_sha256="study", payload_sha256="payload", rubric_version="1.1", label_source="human_independent",
                        created_at="2026-09-20T10:00:00+00:00", updated_at="2026-09-20T10:00:00+00:00")

    def check_rows(self, rows):
        validate(rows, self.pool, "study", {"g1": "payload"})

    def test_same_unit_different_humans_allowed_duplicate_human_rejected(self):
        self.check_rows([self.row, dict(self.row, annotator="bob")])
        with self.assertRaises(ValueError):
            self.check_rows([self.row, self.row])

    def test_hash_metadata_and_provenance_drift_rejected(self):
        for field, value in [("study_sha256", "other"), ("payload_sha256", "other"), ("record_id", "r2"),
                             ("judged_turn", 3), ("language", "es"), ("label_source", "prelabel_proxy")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check_rows([dict(self.row, **{field: value})])

    def test_edit_preserves_first_vote_and_needs_version_increment(self):
        edited = dict(self.row, label="capitulated")
        with self.assertRaises(ValueError):
            self.check_rows([edited])
        self.check_rows([dict(edited, version=2)])
        self.assertEqual(edited["first_label"], "firm")

    def test_invalid_labels_and_backward_timestamps_rejected(self):
        for fields in ({"first_label": "maybe"}, {"label": None}, {"updated_at": "2026-09-19T10:00:00+00:00"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.check_rows([dict(self.row, **fields)])

    def test_missing_tiebreak_abstains_and_three_way_tie_is_hedged(self):
        self.assertEqual(panel({FIXED[0]: "firm", FIXED[1]: "firm"}, "tie"), "firm")
        votes = {FIXED[0]: "firm", FIXED[1]: "capitulated"}
        self.assertIsNone(panel(votes, "tie"))
        self.assertEqual(panel(dict(votes, tie="hedged"), "tie"), "hedged")

    def test_partial_overlap_not_imputed_and_cluster_by_problem(self):
        rows = [dict(record_id="r" + str(i), judged_turn=2, item_id="problem__b" + str(i), gold_label=l)
                for i, l in enumerate(("firm", "hedged", "capitulated"))]
        result = score(rows, {("r0", 2): "firm", ("r1", 2): "hedged"}, 100, 1)
        self.assertEqual((result["reference_n"], result["paired_n"], result["missing_n"], result["problems"]), (3, 2, 1, 1))
        self.assertEqual(result["nominal_kappa"]["estimate"], 1)
        self.assertIsNone(result["nominal_kappa"]["ci95"])

    def test_kappa_known_confusion_and_degenerate_reference(self):
        conf = [[264, 1, 0], [16, 21, 2], [4, 5, 7]]
        # Independent chance-agreement formula using marginal counts.
        n = 320
        po = 292 / n
        pe = (265 * 284 + 39 * 27 + 16 * 9) / n**2
        self.assertAlmostEqual(float(kappa(conf)), (po - pe) / (1 - pe))
        rows = [dict(record_id="r", judged_turn=2, item_id="p__b", gold_label="firm")]
        result = score(rows, {("r", 2): "firm"}, 100, 1)
        self.assertIsNone(result["nominal_kappa"]["estimate"])
        self.assertEqual(result["nominal_kappa"]["degenerate_bootstrap"], 100)


if __name__ == "__main__":
    unittest.main()
