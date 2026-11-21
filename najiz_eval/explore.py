"""Look at one question: both models' answers, the rubric elements, and how each was graded.

    python3 -m najiz_eval.explore 14
    python3 -m najiz_eval.explore --list wrong --model claude-opus-5.5

Question and reference text appear after `python3 -m najiz_eval.fetch`.
"""
import argparse

from .common import ANSWER_FILES, load_json, load_rubric, score_answer, answer_text

NAMES = {"gpt-6-astra": "GPT-6 Astra", "claude-opus-5.5": "Claude Opus 5.5"}


def show(q, rubric, grades, key):
    d = rubric["questions"][str(q)]
    print(f"\nQ{q}" + (f"  {d['question']}" if "question" in d else "  (run najiz_eval.fetch for the question text)"))
    if "reference_answer" in d:
        print(f"\nReference:\n  {d['reference_answer']}")
    print("\nRubric elements:")
    for i, e in enumerate(d["elements"]):
        print(f"  [{i}] {e['type']} (w{e['weight']}) {e['text']}")
    if d.get("note"):
        print(f"  note: {d['note']}")
    for blind in "AB":
        model = key[blind]["model"]
        ans = answer_text(load_json(ANSWER_FILES[model][0])[str(q)])
        g = grades[blind][str(q)]
        s, lab = score_answer(d["elements"], g)
        print(f"\n{NAMES[model]}: {lab.upper()}  score {s:.3f}  met {g.get('met')}")
        if g.get("gate_failure"):
            print(f"  contradiction: {g['gate_failure']}")
        if g.get("wrong_amount_or_timeline"):
            print(f"  wrong amount or timeline (x0.3): {g['wrong_amount_or_timeline']}")
        print(f"  answer: {ans}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?", type=int, help="question number, 1-79")
    ap.add_argument("--list", choices=["correct", "partial", "wrong"], help="list questions with this label")
    ap.add_argument("--model", choices=list(NAMES), default="gpt-6-astra")
    a = ap.parse_args()
    rubric, grades, key = load_rubric(), load_json("grading/grades_sonnet-5.5.json"), load_json("grading/key.json")
    if a.list:
        blind = next(b for b in "AB" if key[b]["model"] == a.model)
        qs = [q for q in range(1, 80)
              if score_answer(rubric["questions"][str(q)]["elements"], grades[blind][str(q)])[1] == a.list]
        print(f"{NAMES[a.model]} — {a.list}: {len(qs)} questions\n  {qs}")
    elif a.question and 1 <= a.question <= 79:
        show(a.question, rubric, grades, key)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
