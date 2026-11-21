You are grading two anonymous answer sets, A and B, to the same 79 Arabic legal questions.

Files: najiz_rubric_79.json (questions, reference answers, elements, weights, rules), answers_A.json, answers_B.json.

Follow the rubric's "rules" and "grader_instructions" exactly. Use only the reference answers and elements; do not use outside legal knowledge. Do not try to identify which model wrote either set.

For every question and for each of A and B, return:
- met: indices (0-based) of the elements the answer states
- gate_failure: the contradicting sentence, or null
- wrong_amount_or_timeline: the wrong value, or null (multiply the score by 0.3)
- wrong_citations: list, or []
- score (0 to 1, three decimals) and label (correct / partial / wrong)

An answer of «لا أعرف» meets no elements and is not a contradiction.
Grade A and B for the same question side by side, so the same standard is applied to both.
Return one JSON object: {"A": {"1": {...}, ..., "79": {...}}, "B": {...}}. Save it as grades.json.