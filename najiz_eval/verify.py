"""Verify every published number from the files in this repository. Works offline.

    python3 -m najiz_eval.verify

Checks the answer-file fingerprints, recomputes all 158 scores from the grader's
element-by-element decisions, unblinds A/B with the key, and prints the results.
"""
import sys
from collections import Counter

from .common import ANSWER_FILES, AREAS, ROOT, load_json, load_rubric, score_all, sha256

PUBLISHED = {
    "gpt-6-astra": {"correct": 30, "partial": 19, "wrong": 30, "mean": 0.536},
    "claude-opus-5.5": {"correct": 12, "partial": 29, "wrong": 38, "mean": 0.398},
}


def main():
    ok = True
    print("Answer files")
    for model, (rel, expected) in ANSWER_FILES.items():
        got = sha256(ROOT / rel)
        status = "ok" if got == expected else "MISMATCH"
        ok &= got == expected
        print(f"  {model:18} {got[:16]}...  {status}")

    rubric = load_rubric()
    grades = load_json("grading/grades_sonnet-5.5.json")
    key = load_json("grading/key.json")

    print("\nRecomputing scores from the grader's decisions")
    results = {}
    mismatches = 0
    for blind in "AB":
        model = key[blind]["model"]
        scores = score_all(rubric, grades[blind])
        for q, (s, lab) in scores.items():
            g = grades[blind][str(q)]
            if abs(s - g["score"]) > 0.002 or lab != g["label"]:
                mismatches += 1
        results[model] = scores
    print(f"  158 answers recomputed, {mismatches} differ from the grader's own arithmetic")
    ok &= mismatches == 0

    print("\nResults (closed-book, graded blind by Claude Sonnet 5.5)\n")
    print(f"  {'Model':18} {'Correct':>8} {'Partial':>8} {'Wrong':>6} {'Mean':>7}")
    for model, scores in results.items():
        c = Counter(lab for _, lab in scores.values())
        mean = sum(s for s, _ in scores.values()) / 79
        print(f"  {model:18} {c['correct']:>8} {c['partial']:>8} {c['wrong']:>6} {mean:>7.3f}")
        p = PUBLISHED[model]
        ok &= (c["correct"], c["partial"], c["wrong"]) == (p["correct"], p["partial"], p["wrong"])
        ok &= abs(round(mean, 3) - p["mean"]) < 0.0015

    print("\nMean score by area of law\n")
    print(f"  {'Area':42} {'n':>3} {'Astra':>7} {'Opus':>7}")
    for area, qs in AREAS.items():
        a = sum(results["gpt-6-astra"][q][0] for q in qs) / len(qs)
        o = sum(results["claude-opus-5.5"][q][0] for q in qs) / len(qs)
        print(f"  {area:42} {len(qs):>3} {a:>7.2f} {o:>7.2f}")

    print("\nAll checks passed." if ok else "\nSOME CHECKS FAILED.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
