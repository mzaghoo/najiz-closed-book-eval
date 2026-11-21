import unittest
from collections import Counter

from najiz_eval import verify_four as v


class FourModelSaudi(unittest.TestCase):
    def test_published_results(self):
        _, res, _ = v.results()
        for m, (c, p, w, mean) in v.PUBLISHED.items():
            labels = Counter(l for _, l in res[m].values())
            got_mean = round(sum(s for s, _ in res[m].values()) / 79, 3)
            self.assertEqual((labels["correct"], labels["partial"], labels["wrong"], got_mean), (c, p, w, mean), m)

    def test_every_question_graded_once_per_model(self):
        key, res, _ = v.results()
        self.assertEqual(len(key["questions"]), 79)
        for labels in key["questions"].values():
            self.assertEqual(sorted(labels.values()), sorted(v.ANSWERS))
        self.assertTrue(all(len(r) == 79 for r in res.values()))


if __name__ == "__main__":
    unittest.main()
