"""Build a blind grading package for your own model's answers, and score the grader's output.

1. Answer the 79 questions closed-book and save {"1": "...", ..., "79": "..."} as JSON.
   (Show your model only the questions: `python3 -m najiz_eval.package questions out/questions.json`.)
2. Build the package (requires `python3 -m najiz_eval.fetch` first):
       python3 -m najiz_eval.package build my_answers.json answers/gpt-6-astra.json -o out/
   This writes out/for_grader/ (rubric, anonymised answer sets, grader prompt) and out/key.json.
3. Give ONLY out/for_grader/ to a grader model; save its reply as grades.json.
4. Score it:
       python3 -m najiz_eval.package score out/grades.json --key out/key.json
"""
import argparse
import json
import secrets
import shutil
from collections import Counter
from pathlib import Path

from .common import DATA, ROOT, answer_text, score_all


def _rubric_path():
    p = DATA / "najiz_rubric_79.json"
    if not p.exists():
        raise SystemExit("Run `python3 -m najiz_eval.fetch` first: the grader needs the reference answers.")
    return p


def questions(out):
    r = json.loads(_rubric_path().read_text(encoding="utf-8"))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({q: d["question"] for q, d in r["questions"].items()},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {out} (questions only, no reference answers)")


def build(files, out):
    out = Path(out); fg = out / "for_grader"; fg.mkdir(parents=True, exist_ok=True)
    labels = [chr(ord("A") + i) for i in range(len(files))]
    order = list(files); secrets.SystemRandom().shuffle(order)
    key = {}
    for lab, f in zip(labels, order):
        ans = json.loads(Path(f).read_text(encoding="utf-8"))
        clean = {str(q): answer_text(ans[str(q)]) for q in range(1, 80)}
        (fg / f"answers_{lab}.json").write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
        key[lab] = {"file": str(f)}
    shutil.copy(_rubric_path(), fg / "najiz_rubric_79.json")
    prompt = (ROOT / "grading" / "GRADER_PROMPT.md").read_text(encoding="utf-8")
    if len(labels) != 2:
        prompt = prompt.replace("two anonymous answer sets, A and B", f"{len(labels)} anonymous answer sets ({', '.join(labels)})")
    (fg / "GRADER_PROMPT.md").write_text(prompt, encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print(f"Wrote {fg}/ for the grader and {out/'key.json'} (keep the key away from the grader).")


def score(grades_file, key_file):
    r = json.loads(_rubric_path().read_text(encoding="utf-8"))
    g = json.loads(Path(grades_file).read_text(encoding="utf-8"))
    key = json.loads(Path(key_file).read_text(encoding="utf-8")) if key_file else {}
    for lab, sets in g.items():
        s = score_all(r, sets)
        c = Counter(x for _, x in s.values())
        name = key.get(lab, {}).get("file", lab)
        print(f"{name}: {c['correct']} correct, {c['partial']} partial, {c['wrong']} wrong, "
              f"mean {sum(v for v, _ in s.values())/79:.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("questions"); q.add_argument("out")
    b = sub.add_parser("build"); b.add_argument("answers", nargs="+"); b.add_argument("-o", "--out", required=True)
    s = sub.add_parser("score"); s.add_argument("grades"); s.add_argument("--key")
    a = ap.parse_args()
    if a.cmd == "questions":
        questions(a.out)
    elif a.cmd == "build":
        build(a.answers, a.out)
    else:
        score(a.grades, a.key)


if __name__ == "__main__":
    main()
