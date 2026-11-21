"""Shared paths, loaders and the scoring rule. Standard library only."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"  # created by `python3 -m najiz_eval.fetch`; not in git

BENCHMARK_URL = ("https://raw.githubusercontent.com/Thiqah/ArabLegalEval/main/"
                 "benchmarkQA/Najiz_QA_with_context_v2.benchmark.json")
BENCHMARK_SHA256 = "72bdc6bf5d75ba9d00fd406c9545ea822ccb43169410c3e111a7f16b5072e6b6"
RUBRIC_SHA256 = "68e1aaf55bb7887409db30c1b7229e6904efd437ac99c10f327892b8cdc3d180"

ANSWER_FILES = {
    "gpt-6-astra": ("answers/gpt-6-astra.json",
                    "756d706e963a6298d8d9628e867a4cac9db39b4d8263625547471b0a3e330aac"),
    "claude-opus-5.5": ("answers/claude-opus-5.5.json",
                        "dea83df461c0a612e1f5b8097d9c5b5c828e4bda725de83c5740eaee4271a7b8"),
}

# Areas of law, assigned by the author from each question's subject (not part of the benchmark).
AREAS = {
    "Civil & commercial procedure": [2, 29, 42, 44, 45, 56, 63, 70, 71, 75, 78],
    "Criminal procedure": [1, 20, 52, 66, 68, 73],
    "Court fees & judicial costs": [5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 21, 27, 33,
                                    35, 36, 40, 41, 51, 55, 60, 61, 62, 65, 79],
    "Enforcement": [13, 19, 23, 24, 25, 28, 31, 32, 37, 53, 58, 59, 67, 69, 72, 77],
    "Family & personal status": [22, 26, 30, 43, 48, 54, 57, 74],
    "Licensing: lawyers, notaries, providers": [3, 4, 34, 38, 39, 46, 47, 49, 50, 64],
    "Other: waqf documentation": [76],
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def load_rubric():
    """Full rubric if fetched (with question text), else the elements-only copy in git."""
    full = DATA / "najiz_rubric_79.json"
    if full.exists():
        return json.loads(full.read_text(encoding="utf-8"))
    return load_json("rubric/najiz_rubric_79.elements.json")


def answer_text(value):
    """Opus answers are stored as [answer, confidence]; Astra answers as plain strings."""
    return value[0] if isinstance(value, list) else value


def score_answer(elements, grade):
    """Apply the rubric rules to one grader decision.

    grade: {"met": [...], "gate_failure": str|None, "wrong_amount_or_timeline": str|None,
            "wrong_citations": [...]}
    Returns (score, label).
    """
    if grade.get("gate_failure"):
        return 0.0, "wrong"
    met = sorted({i for i in grade.get("met") or [] if 0 <= i < len(elements)})
    total = sum(e["weight"] for e in elements)
    score = (sum(elements[i]["weight"] for i in met) - 2 * len(grade.get("wrong_citations") or [])) / total
    score = max(0.0, score)
    if grade.get("wrong_amount_or_timeline"):
        score *= 0.3
    core_met = all(i in met for i, e in enumerate(elements) if e["type"] in "PTM")
    if score >= 0.85 and core_met:
        label = "correct"
    elif score >= 0.40:
        label = "partial"
    else:
        label = "wrong"
    return score, label


def score_all(rubric, grades_for_one_set):
    out = {}
    for q in range(1, 80):
        els = rubric["questions"][str(q)]["elements"]
        out[q] = score_answer(els, grades_for_one_set[str(q)])
    return out
