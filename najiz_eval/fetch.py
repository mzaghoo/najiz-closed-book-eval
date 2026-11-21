"""Download the Najiz benchmark from its original repository, verify it, and rebuild the full rubric.

    python3 -m najiz_eval.fetch

The benchmark text (questions and reference answers) is not redistributed here. This script
fetches the exact file the study used, checks its SHA-256, and joins the text into the
rubric. The rebuilt rubric must match the SHA-256 recorded at grading time.
"""
import hashlib
import json
import sys
import urllib.request

from .common import BENCHMARK_SHA256, BENCHMARK_URL, DATA, RUBRIC_SHA256, load_json


def main():
    DATA.mkdir(exist_ok=True)
    dest = DATA / "Najiz_QA_with_context_v2.benchmark.json"
    if not dest.exists():
        print(f"Downloading {BENCHMARK_URL}")
        with urllib.request.urlopen(BENCHMARK_URL, timeout=60) as r:
            dest.write_bytes(r.read())
    got = hashlib.sha256(dest.read_bytes()).hexdigest()
    if got != BENCHMARK_SHA256:
        dest.unlink()
        sys.exit(f"Benchmark SHA-256 mismatch: got {got}, expected {BENCHMARK_SHA256}.\n"
                 "The upstream file has changed since this study; results may not be comparable.")
    print(f"Benchmark verified ({got[:12]}...)")

    src = json.loads(dest.read_text(encoding="utf-8"))
    el = load_json("rubric/najiz_rubric_79.elements.json")
    full = {k: v for k, v in el.items() if k not in ("questions", "note_on_benchmark_text")}
    full["questions"] = {}
    for q, d in el["questions"].items():
        i = int(q) - 1
        full["questions"][q] = {"question": src["questions"][i],
                                "reference_answer": src["ground_truths"][i], **d}
    text = json.dumps(full, ensure_ascii=False, indent=1)
    out = DATA / "najiz_rubric_79.json"
    out.write_text(text, encoding="utf-8")
    got = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if got != RUBRIC_SHA256:
        sys.exit(f"Rebuilt rubric SHA-256 {got} does not match the graded rubric {RUBRIC_SHA256}.")
    print(f"Rubric rebuilt and verified ({got[:12]}...): {out.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
