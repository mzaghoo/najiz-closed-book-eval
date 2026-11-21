"""Offline test of the four-model workflow with a fake API. Skipped until `najiz_eval.fetch` has run."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from najiz_eval import openrouter as orr
from najiz_eval.common import DATA


@unittest.skipUnless((DATA / "najiz_rubric_79.json").exists(), "run `python3 -m najiz_eval.fetch` first")
class FourModelWorkflow(unittest.TestCase):
    def test_answer_grade_report(self):
        seen_by_grader = []

        def fake_call(payload, dry_log=None, retries=4):
            if dry_log is not None:
                dry_log.append(payload); return None
            if payload["model"] == orr.GRADER:
                user = json.loads(payload["messages"][1]["content"])
                seen_by_grader.append(payload["messages"][1]["content"] + payload["messages"][0]["content"])
                # every answer meets element 0 only
                g = {lab: {"met": [0], "gate_failure": None, "wrong_amount_or_timeline": None,
                           "wrong_citations": []} for lab in user["answers"]}
                return {"model": orr.GRADER, "choices": [{"message": {"content": json.dumps(g)}}]}
            return {"model": payload["model"], "choices": [{"message": {"content": "لا أعرف"},
                                                             "finish_reason": "stop"}]}

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(orr, "RUN", Path(tmp)), mock.patch.object(orr, "_call", fake_call):
            for m in orr.NEW_MODELS:
                orr.answer(m)
                ans = json.loads((Path(tmp) / "answers" / f"{orr._slug(m)}.json").read_text(encoding="utf-8"))
                self.assertEqual(len(ans), 79)
            orr.grade()
            key = json.loads((Path(tmp) / "grading" / "key.json").read_text())
            self.assertEqual(len(key["questions"]), 79)
            # blinding: model names never reach the grader
            for text in seen_by_grader:
                for name in ("astra", "opus", "gemini", "muse", "claude", "gpt"):
                    self.assertNotIn(name, text.lower())
            orr.report()
            scores = json.loads((Path(tmp) / "scores.json").read_text())
            self.assertEqual(sorted(scores), sorted(list(orr.EXISTING) + orr.NEW_MODELS))
            self.assertTrue(all(len(v) == 79 for v in scores.values()))


if __name__ == "__main__":
    unittest.main()
