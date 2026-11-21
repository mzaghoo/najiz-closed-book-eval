import unittest
from collections import Counter

from najiz_eval.common import ANSWER_FILES, ROOT, load_json, score_all, score_answer, sha256


class Reproduce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rubric = load_json("rubric/najiz_rubric_79.elements.json")
        cls.grades = load_json("grading/grades_sonnet-5.5.json")
        cls.key = load_json("grading/key.json")

    def test_answer_fingerprints(self):
        for rel, expected in ANSWER_FILES.values():
            self.assertEqual(sha256(ROOT / rel), expected)

    def test_rubric_shape(self):
        qs = self.rubric["questions"]
        self.assertEqual(sorted(map(int, qs)), list(range(1, 80)))
        self.assertEqual(sum(len(d["elements"]) for d in qs.values()), 270)
        self.assertNotIn("reference_answer", qs["1"])

    def test_published_results(self):
        expected = {"gpt-6-astra": (30, 19, 30, 0.536), "claude-opus-5.5": (12, 29, 38, 0.398)}
        for blind in "AB":
            s = score_all(self.rubric, self.grades[blind])
            c = Counter(lab for _, lab in s.values())
            mean = round(sum(v for v, _ in s.values()) / 79, 3)
            self.assertEqual((c["correct"], c["partial"], c["wrong"], mean), expected[self.key[blind]["model"]])

    def test_scoring_rules(self):
        els = [{"type": "P", "weight": 3}, {"type": "T", "weight": 2}, {"type": "X", "weight": 1}]
        self.assertEqual(score_answer(els, {"met": [0, 1, 2]}), (1.0, "correct"))
        self.assertEqual(score_answer(els, {"met": [0, 2]})[1], "partial")      # missing deadline
        self.assertEqual(score_answer(els, {"met": [0, 1, 2], "gate_failure": "x"}), (0.0, "wrong"))
        s, lab = score_answer(els, {"met": [0, 2], "wrong_amount_or_timeline": "3 years vs 2"})
        self.assertAlmostEqual(s, 4 / 6 * 0.3)
        self.assertEqual(lab, "wrong")


if __name__ == "__main__":
    unittest.main()
