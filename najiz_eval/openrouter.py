"""Four-model Najiz comparison through OpenRouter: answer, grade blind, report.

Setup (once):
    python3 -m najiz_eval.fetch                       # questions + full rubric (SHA-256 68e1aaf5...)
    # API key: put it in ~/.openrouter_api_key (chmod 600) or the OPENROUTER_API_KEY variable.
    # It is read by this script only and never printed or written to any output.

Steps:
    python3 -m najiz_eval.openrouter answer google/gemini-4-carbon
    python3 -m najiz_eval.openrouter answer meta/muse-spark-1.3
    python3 -m najiz_eval.openrouter grade          # Sonnet 5.5 grades all answer sets blind
    python3 -m najiz_eval.openrouter report

Add --dry-run to any step to write the requests it would send without calling the API.
Outputs go to runs/four-model/ (not tracked by git).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from .common import ANSWER_FILES, AREAS, DATA, RUBRIC_SHA256, ROOT, answer_text, score_answer

RUN = ROOT / "runs" / "four-model"
API = "https://openrouter.ai/api/v1/chat/completions"
GRADER = "anthropic/claude-sonnet-5.5"

# Answer sets in the comparison. Existing files are reused as-is (see README); new ones are generated.
EXISTING = {"openai/gpt-6-astra": ANSWER_FILES["gpt-6-astra"],
            "anthropic/claude-opus-5.5": ANSWER_FILES["claude-opus-5.5"]}
NEW_MODELS = ["google/gemini-4-carbon", "meta/muse-spark-1.3"]

# The same instructions GPT-6 Astra received, restated per question.
ANSWER_SYSTEM = (
    "Answer the Arabic question using only your existing knowledge. Do not browse, search, "
    "call tools, or use external sources. Do not invent laws, amounts, article numbers, or "
    "citations. If you cannot confidently recall the answer, say «لا أعرف». "
    "Answer concisely in Arabic, at most 150 words.")


# ---------------------------------------------------------------- utilities
def _key():
    k = os.environ.get("OPENROUTER_API_KEY")
    if not k:
        p = Path.home() / ".openrouter_api_key"
        if p.exists():
            k = p.read_text().strip()
    if not k:
        sys.exit("No API key: set OPENROUTER_API_KEY or create ~/.openrouter_api_key (chmod 600).")
    return k


def _call(payload, dry_log=None, retries=4):
    """POST one chat completion. In dry-run mode, log the payload and return None."""
    if dry_log is not None:
        dry_log.append(payload)
        return None
    body = json.dumps(payload).encode()
    for attempt in range(retries):
        req = urllib.request.Request(API, data=body, headers={
            "Authorization": f"Bearer {_key()}", "Content-Type": "application/json",
            "X-Title": "najiz-closed-book-eval"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(5 * 2 ** attempt); continue
            raise SystemExit(f"OpenRouter error {e.code}: {msg}")
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(5 * 2 ** attempt); continue
            raise SystemExit(f"Network error: {e}")


def _rubric():
    p = DATA / "najiz_rubric_79.json"
    if not p.exists():
        sys.exit("Run `python3 -m najiz_eval.fetch` first.")
    if hashlib.sha256(p.read_bytes()).hexdigest() != RUBRIC_SHA256:
        sys.exit("data/najiz_rubric_79.json does not match the graded rubric; re-run fetch.")
    return json.loads(p.read_text(encoding="utf-8"))


def _slug(model):
    return model.replace("/", "__")


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _rel(p):
    try:
        return Path(p).relative_to(ROOT)
    except ValueError:
        return p


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- 1. answer
def answer(model, dry_run=False, max_tokens=4000):
    r = _rubric()
    out = RUN / "answers"; out.mkdir(parents=True, exist_ok=True)
    raw_path = out / f"{_slug(model)}.raw.jsonl"
    done = {}
    if raw_path.exists():  # resume
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line); done[rec["q"]] = rec
    dry = [] if dry_run else None
    with (open(os.devnull, "w") if dry_run else raw_path.open("a", encoding="utf-8")) as raw:
        for q in range(1, 80):
            if str(q) in done:
                continue
            payload = {"model": model, "max_tokens": max_tokens,
                       "messages": [{"role": "system", "content": ANSWER_SYSTEM},
                                    {"role": "user", "content": r["questions"][str(q)]["question"]}]}
            resp = _call(payload, dry)
            if dry_run:
                continue
            msg = resp["choices"][0]["message"]
            rec = {"q": str(q), "answer": (msg.get("content") or "").strip(),
                   "served_model": resp.get("model"), "provider": resp.get("provider"),
                   "finish_reason": resp["choices"][0].get("finish_reason"),
                   "usage": resp.get("usage"), "at": _now()}
            raw.write(json.dumps(rec, ensure_ascii=False) + "\n"); raw.flush()
            done[str(q)] = rec
            print(f"  {model} Q{q}: {len(rec['answer'])} chars", flush=True)
    if dry_run:
        (out / f"{_slug(model)}.dry_run.json").write_text(json.dumps(dry, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Dry run: {len(dry)} requests written for {model}; nothing sent.")
        return
    empty = [q for q, rec in done.items() if not rec["answer"]]
    if empty:
        print(f"Warning: empty answers for questions {sorted(map(int, empty))}; delete those lines from "
              f"{raw_path.name} and re-run to retry.")
    final = out / f"{_slug(model)}.json"
    final.write_text(json.dumps({str(q): done[str(q)]["answer"] for q in range(1, 80)},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {_rel(final)}  SHA-256 {_sha(final)}")


# ---------------------------------------------------------------- 2. grade (blind)
GRADE_SYSTEM = """You are grading anonymous answers to one Arabic legal question against a fixed rubric.

Use only the reference answer and the listed elements; do not use outside legal knowledge. Do not try to identify which model wrote any answer. Apply the same standard to every answer.

Rules:
{rules}

Grader instructions:
{instructions}

For each answer label, return:
- "met": 0-based indices of the elements the answer itself states (in any wording)
- "gate_failure": the sentence that contradicts the reference on something other than an amount or timeline, or null
- "wrong_amount_or_timeline": the wrong amount, rate, deadline, period or term the answer states, or null
- "wrong_citations": list of citations that differ from reference_cited for the same point, or []

An answer of «لا أعرف» meets no elements and is not a contradiction.
Reply with one JSON object only: {{"<label>": {{"met": [...], "gate_failure": ..., "wrong_amount_or_timeline": ..., "wrong_citations": [...]}}, ...}}"""


def _answer_sets():
    sets = {}
    for model, (rel, sha) in EXISTING.items():
        if _sha(ROOT / rel) != sha:
            sys.exit(f"{rel} does not match its recorded fingerprint.")
        sets[model] = {q: answer_text(v) for q, v in json.loads((ROOT / rel).read_text(encoding="utf-8")).items()}
    for model in NEW_MODELS:
        p = RUN / "answers" / f"{_slug(model)}.json"
        if not p.exists():
            sys.exit(f"Missing answers for {model}: run `answer {model}` first.")
        sets[model] = json.loads(p.read_text(encoding="utf-8"))
    return sets


def grade(dry_run=False, grader=GRADER):
    r = _rubric()
    sets = _answer_sets()
    gdir = RUN / "grading"; gdir.mkdir(parents=True, exist_ok=True)
    key_path = gdir / "key.json"
    # Blinding: a fresh random label order per question; the key never goes to the grader.
    if key_path.exists():
        key = json.loads(key_path.read_text())
    else:
        rng = random.Random(secrets.randbits(64))
        key = {"answer_sha256": {m: hashlib.sha256(json.dumps(a, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                                 for m, a in sets.items()},
               "rubric_sha256": RUBRIC_SHA256, "grader": grader, "created": _now(), "questions": {}}
        for q in range(1, 80):
            models = list(sets); rng.shuffle(models)
            key["questions"][str(q)] = {chr(65 + i): m for i, m in enumerate(models)}
        if not dry_run:
            key_path.write_text(json.dumps(key, indent=1))
    raw_path = gdir / "grades.raw.jsonl"
    done = {}
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line); done[rec["q"]] = rec
    system = GRADE_SYSTEM.format(rules=json.dumps(r["rules"], ensure_ascii=False, indent=1),
                                 instructions="\n".join("- " + i for i in r["grader_instructions"]))
    dry = [] if dry_run else None
    with (open(os.devnull, "w") if dry_run else raw_path.open("a", encoding="utf-8")) as raw:
        for q in range(1, 80):
            if str(q) in done:
                continue
            d = r["questions"][str(q)]
            labels = key["questions"][str(q)]
            user = {"question": d["question"], "reference_answer": d["reference_answer"],
                    "elements": [{"index": i, **e} for i, e in enumerate(d["elements"])],
                    "reference_cited": d.get("reference_cited"), "note": d.get("note"),
                    "answers": {lab: sets[m][str(q)] for lab, m in sorted(labels.items())}}
            payload = {"model": grader, "max_tokens": 4000, "temperature": 0,
                       "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": json.dumps(user, ensure_ascii=False, indent=1)}]}
            if dry_run:
                _call(payload, dry); continue
            for attempt in range(3):
                resp = _call(payload)
                text = (resp["choices"][0]["message"].get("content") or "").strip()
                try:
                    g = json.loads(text[text.find("{"): text.rfind("}") + 1])
                    assert set(g) == set(labels), f"labels {sorted(g)} != {sorted(labels)}"
                    for v in g.values():
                        assert isinstance(v.get("met", []), list)
                    break
                except Exception as e:  # malformed reply: ask again
                    if attempt == 2:
                        sys.exit(f"Grader reply for Q{q} could not be parsed after 3 tries: {e}")
            rec = {"q": str(q), "grades": g, "served_model": resp.get("model"), "usage": resp.get("usage"), "at": _now()}
            raw.write(json.dumps(rec, ensure_ascii=False) + "\n"); raw.flush()
            print(f"  graded Q{q}", flush=True)
    if dry_run:
        (gdir / "dry_run.json").write_text(json.dumps(dry, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Dry run: {len(dry)} grading requests written; nothing sent. Each shows the grader only labels A-D.")
        return
    print(f"Grading complete: {_rel(raw_path)}")


# ---------------------------------------------------------------- 3. report
def report():
    r = _rubric()
    gdir = RUN / "grading"
    key = json.loads((gdir / "key.json").read_text())
    grades = {}
    for line in (gdir / "grades.raw.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line); grades[rec["q"]] = rec["grades"]
    missing = [q for q in range(1, 80) if str(q) not in grades]
    if missing:
        sys.exit(f"Grades missing for {missing}; re-run `grade`.")
    models = sorted(next(iter(key["questions"].values())).values())
    res = {m: {} for m in models}
    for q in range(1, 80):
        els = r["questions"][str(q)]["elements"]
        for lab, m in key["questions"][str(q)].items():
            res[m][q] = score_answer(els, grades[str(q)][lab])
    rows = []
    for m in models:
        c = Counter(l for _, l in res[m].values())
        rows.append((m, c["correct"], c["partial"], c["wrong"], sum(s for s, _ in res[m].values()) / 79))
    rows.sort(key=lambda x: -x[4])
    lines = [f"Najiz closed-book, 79 questions. Grader: {key['grader']} (blind, per-question shuffled labels). "
             f"Rubric SHA-256 {RUBRIC_SHA256[:12]}...", "",
             "| Model | Correct | Partial | Wrong | Mean score |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {m} | {c} | {p} | {w} | {s:.3f} |" for m, c, p, w, s in rows]
    lines += ["", "| Area of law | n | " + " | ".join(m for m, *_ in rows) + " |",
              "|---|---:|" + "---:|" * len(rows)]
    for area, qs in AREAS.items():
        lines.append(f"| {area} | {len(qs)} | " + " | ".join(
            f"{sum(res[m][q][0] for q in qs)/len(qs):.2f}" for m, *_ in rows) + " |")
    text = "\n".join(lines)
    (RUN / "report.md").write_text(text + "\n", encoding="utf-8")
    (RUN / "scores.json").write_text(json.dumps(
        {m: {str(q): {"score": round(s, 3), "label": l} for q, (s, l) in res[m].items()} for m in models},
        indent=1), encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("answer"); a.add_argument("model"); a.add_argument("--dry-run", action="store_true")
    g = sub.add_parser("grade"); g.add_argument("--dry-run", action="store_true")
    sub.add_parser("report")
    x = ap.parse_args()
    if x.cmd == "answer":
        answer(x.model, x.dry_run)
    elif x.cmd == "grade":
        grade(x.dry_run)
    else:
        report()


if __name__ == "__main__":
    main()
