"""Verify the four-model results (Saudi context) from the files in this repository. Works offline.

    python3 -m najiz_eval.verify_four

Checks that the graded answer sets are the ones in the repo, recomputes all 316 scores from
the grader's element-by-element decisions, unblinds the per-question labels, and prints the
tables in the README.
"""
import hashlib
import json
import sys
from collections import Counter

from .common import AREAS, ROOT, answer_text, load_json, load_rubric, score_answer

DIR = "four_model_saudi"
ANSWERS = {
    "openai/gpt-6-astra": "answers/gpt-6-astra.json",
    "anthropic/claude-opus-5.5": "answers/claude-opus-5.5.json",
    "google/gemini-4-carbon": f"{DIR}/answers/gemini-4-carbon.json",
    "meta/muse-spark-1.3": f"{DIR}/answers/muse-spark-1.3.json",
}
NAMES = {"openai/gpt-6-astra": "GPT-6 Astra", "anthropic/claude-opus-5.5": "Claude Opus 5.5",
         "google/gemini-4-carbon": "Gemini 4 Carbon", "meta/muse-spark-1.3": "Muse Spark 1.3"}
SHORT = {"openai/gpt-6-astra": "Astra", "anthropic/claude-opus-5.5": "Opus",
         "google/gemini-4-carbon": "Gemini", "meta/muse-spark-1.3": "Muse"}
PUBLISHED = {  # correct, partial, wrong, mean
    "google/gemini-4-carbon": (33, 20, 26, 0.591),
    "openai/gpt-6-astra": (28, 18, 33, 0.504),
    "anthropic/claude-opus-5.5": (12, 21, 46, 0.331),
    "meta/muse-spark-1.3": (11, 20, 48, 0.326),
}


def results():
    rubric = load_rubric()
    key = load_json(f"{DIR}/grading/key.json")
    grades = {}
    for line in (ROOT / DIR / "grading" / "grades.raw.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        grades[rec["q"]] = rec["grades"]
    res = {m: {} for m in ANSWERS}
    decisions = {m: {} for m in ANSWERS}
    for q in range(1, 80):
        els = rubric["questions"][str(q)]["elements"]
        for lab, m in key["questions"][str(q)].items():
            res[m][q] = score_answer(els, grades[str(q)][lab])
            decisions[m][q] = grades[str(q)][lab]
    return key, res, decisions


def main():
    ok = True
    key, res, _ = results()
    print("Answer sets graded")
    for m, rel in ANSWERS.items():
        ans = {k: answer_text(v) for k, v in load_json(rel).items()}
        h = hashlib.sha256(json.dumps(ans, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        same = h == key["answer_sha256"][m]
        ok &= same
        print(f"  {NAMES[m]:16} {'matches the graded set' if same else 'DIFFERS from the graded set'}")
    print(f"\nGrader: {key['grader']} · rubric {key['rubric_sha256'][:12]}... · labels shuffled per question\n")
    print(f"  {'Model':16} {'Correct':>8} {'Partial':>8} {'Wrong':>6} {'Mean':>7}")
    for m in sorted(res, key=lambda m: -sum(s for s, _ in res[m].values())):
        c = Counter(l for _, l in res[m].values())
        mean = sum(s for s, _ in res[m].values()) / 79
        print(f"  {NAMES[m]:16} {c['correct']:>8} {c['partial']:>8} {c['wrong']:>6} {mean:>7.3f}")
        exp = PUBLISHED[m]
        ok &= (c["correct"], c["partial"], c["wrong"]) == exp[:3] and abs(round(mean, 3) - exp[3]) < 0.0015
    stored = load_json(f"{DIR}/scores.json")
    diff = sum(abs(stored[m][str(q)]["score"] - round(res[m][q][0], 3)) > 0.001 or stored[m][str(q)]["label"] != res[m][q][1]
               for m in res for q in range(1, 80))
    ok &= diff == 0
    print(f"\n  316 scores recomputed; {diff} differ from scores.json")
    print("\nMean score by area of law\n")
    order = ["google/gemini-4-carbon", "openai/gpt-6-astra", "anthropic/claude-opus-5.5", "meta/muse-spark-1.3"]
    print(f"  {'Area':42} {'n':>3} " + " ".join(f"{SHORT[m]:>8}" for m in order))
    for area, qs in AREAS.items():
        print(f"  {area:42} {len(qs):>3} " + " ".join(f"{sum(res[m][q][0] for q in qs)/len(qs):>8.2f}" for m in order))
    print("\nAll checks passed." if ok else "\nSOME CHECKS FAILED.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
