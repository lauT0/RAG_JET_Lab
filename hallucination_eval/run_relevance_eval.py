"""Score testing-dataset results with Patronus relevance evaluators.

Reads a CSV written by run_testing_dataset.py (Query, answer, chunks, ...) and
adds a pass / score / explanation column for each evaluator:

  context_relevance     question + chunks                 are the chunks about the question?   (retrieval)
  context_sufficiency   question + chunks + gold_answer   do the chunks hold the correct answer? (retrieval)
  answer_relevance      question + answer                 is the answer on topic?               (generation)

Context sufficiency needs a correct answer to compare against, so it runs only
when the input CSV has a gold_answer column. Rows with no chunks are not scored
on the context evaluators.

Run from the project root (no API server needed):

  python -m hallucination_eval.run_relevance_eval                    # latest testing_dataset results
  python -m hallucination_eval.run_relevance_eval --input path.csv --limit 2
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from backend.models import refresh_env
from hallucination_eval.run_hallucination_eval import RESULTS_DIR, get_evaluator

# Column prefix → Patronus evaluator. Each is its own evaluator family (not
# "judge"); the bare alias resolves to the current large version.
EVALUATORS = {
    "context_relevance": "context-relevance",
    "context_sufficiency": "context-sufficiency",
    "answer_relevance": "answer-relevance",
}
NEEDS_CONTEXT = {"context_relevance", "context_sufficiency"}


def latest_results() -> Path:
    files = sorted(RESULTS_DIR.glob("*_testing_dataset.csv"))
    if not files:
        raise SystemExit("No *_testing_dataset.csv in results/. Run run_testing_dataset.py first.")
    return files[-1]


def score_row(evaluator, row: pd.Series, names: list[str]) -> dict:
    chunks = json.loads(row["chunks"])
    gold = str(row.get("gold_answer") or "").strip()
    to_run = [
        name
        for name in names
        if not (name in NEEDS_CONTEXT and not chunks) and not (name == "context_sufficiency" and not gold)
    ]

    record = {}
    for name in names:
        if name not in to_run:
            record[f"{name}_explanation"] = "no gold answer" if name == "context_sufficiency" and not gold else "no chunks retrieved"
    if not to_run:
        return record

    kwargs = {"gold_answer": gold} if gold else {}
    response = evaluator.evaluations.evaluate(
        evaluators=[
            {"evaluator": EVALUATORS[name], "criteria": f"patronus:{EVALUATORS[name]}", "explain_strategy": "always"}
            for name in to_run
        ],
        task_input=row["Query"],
        task_context=chunks or None,
        task_output=row["answer"],
        project_name="rag-jet-lab",
        app="relevance-eval",
        capture="all",
        **kwargs,
    )
    by_criteria = {result.criteria: result for result in response.results}
    for name in to_run:
        result = by_criteria.get(f"patronus:{EVALUATORS[name]}")
        if result is None or result.evaluation_result is None:
            status = f"{result.status}: {result.error_message}" if result else "missing from response"
            record[f"{name}_explanation"] = f"error: {status}"
            continue
        evaluation = result.evaluation_result
        record[f"{name}_pass"] = evaluation.pass_
        record[f"{name}_score"] = evaluation.score_raw
        record[f"{name}_explanation"] = evaluation.explanation or ""
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, help="defaults to the newest results/*_testing_dataset.csv")
    parser.add_argument("--output", type=Path, help="defaults to <input name>_relevance.csv")
    parser.add_argument("--limit", type=int, help="score only the first N rows")
    args = parser.parse_args()

    refresh_env()
    in_path = args.input or latest_results()
    df = pd.read_csv(in_path, keep_default_na=False)
    if args.limit:
        df = df.head(args.limit)

    names = list(EVALUATORS)
    if "gold_answer" not in df:
        names.remove("context_sufficiency")
        print("No gold_answer column: skipping context_sufficiency.")

    evaluator = get_evaluator()
    records = []
    for n, row in df.iterrows():
        print(f"[{n + 1}/{len(df)}] {row['Query'][:80]}")
        try:
            record = score_row(evaluator, row, names)
        except Exception as exc:
            record = {"relevance_error": f"{type(exc).__name__}: {exc}"}
            print(f"    error: {record['relevance_error']}")
        verdicts = [f"{name}={record[f'{name}_pass']}" for name in names if f"{name}_pass" in record]
        print(f"    {' '.join(verdicts)}")
        records.append(record)
        time.sleep(0.5)

    df = df.join(pd.DataFrame(records, index=df.index))
    out_path = args.output or in_path.with_name(f"{in_path.stem}_relevance.csv")
    df.to_csv(out_path, index=False)

    print("\n=== Patronus relevance (pass / scored) ===")
    for name in names:
        column = f"{name}_pass"
        if column in df:
            scored = df[column].isin([True, False])
            print(f"  {name:20s} {int((df.loc[scored, column] == True).sum())}/{int(scored.sum())}")
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
