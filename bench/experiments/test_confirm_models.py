import unittest

from confirm_models import BASE, GROUPS, select_candidates


class ModelSelectionTests(unittest.TestCase):
    def rows(self):
        return [{"dataset": dataset, "split": "dev", "label": BASE, "ndcg@10": .5, "cfg": {"base": True}}
                for datasets in GROUPS.values() for dataset in datasets]

    def test_both_corpora_must_clear_the_frozen_threshold(self):
        rows = self.rows()
        for dataset, score in (("scifact", .515), ("nfcorpus", .509)):
            rows.append({"dataset": dataset, "split": "dev", "label": "candidate", "ndcg@10": score, "cfg": {"model": "candidate"}})
        self.assertEqual(select_candidates(rows), [])
        rows[-1]["ndcg@10"] = .51
        selected = select_candidates(rows)
        self.assertEqual([(row["group"], row["label"]) for row in selected], [("English", "candidate")])

    def test_a_later_failure_must_not_reuse_an_old_success(self):
        rows = self.rows()
        rows.append({"dataset": "scifact", "split": "dev", "label": BASE, "error": "failed"})
        with self.assertRaisesRegex(ValueError, "failed dev baseline"):
            select_candidates(rows)

    def test_different_configurations_cannot_be_combined_as_one_candidate(self):
        rows = self.rows()
        for dataset, name in (("scifact", "one"), ("nfcorpus", "two")):
            rows.append({"dataset": dataset, "split": "dev", "label": "candidate", "ndcg@10": .52, "cfg": {"model": name}})
        with self.assertRaisesRegex(ValueError, "configuration changed"):
            select_candidates(rows)


if __name__ == "__main__":
    unittest.main()
