"""Hallucination test for the RAG pipeline, scored by Patronus Lynx.

For each question in hallucination_eval/hallucination_questions.csv:

  question
    → retrieve() from the jet_lab index (same code the app uses)
    → generate an answer (grounded, base, or both)
    → send (question, retrieved chunks, answer) to Patronus Lynx
    → record PASS (answer supported by the chunks) or FAIL (hallucination)

Lynx checks faithfulness to the retrieved chunks, not real-world truth.
A base answer is scored against the same chunks, which measures how far
the ungrounded model drifts from what the corpus says.

Run from the project root:

  python -m hallucination_eval.run_hallucination_eval --retrieval-only     # free, no API calls
  python -m hallucination_eval.run_hallucination_eval --limit 3            # quick smoke test
  python -m hallucination_eval.run_hallucination_eval --mode both          # full run
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from backend.models import openai_configured, refresh_env
from backend.retrieval.rag import NO_CONTEXT, generate_base, generate_grounded, retrieve

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS = EVAL_DIR / "hallucination_questions.csv"
RESULTS_DIR = EVAL_DIR / "results"

FIELDS = [
    "id",
    "category",
    "mode",
    "question",
    "expected_answer",
    "source_chunk_id",
    "retrieved_chunk_ids",
    "chunk_hit",
    "doc_hit",
    "answer",
    "patronus_pass",
    "patronus_score",
    "patronus_explanation",
    "error",
]


def load_questions(ids: set[str] | None, limit: int | None) -> list[dict]:
    with open(QUESTIONS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if ids:
        rows = [row for row in rows if row["id"] in ids]
    if limit:
        rows = rows[:limit]
    return rows


def retrieval_check(row: dict, chunks: list[dict]) -> dict:
    retrieved = [chunk["id"] for chunk in chunks]
    expected = row["source_chunk_id"]
    if not expected:
        return {"retrieved_chunk_ids": " | ".join(retrieved), "chunk_hit": "", "doc_hit": ""}
    expected_doc = expected.rsplit("::", 1)[0]
    return {
        "retrieved_chunk_ids": " | ".join(retrieved),
        "chunk_hit": expected in retrieved,
        "doc_hit": any(chunk_id.rsplit("::", 1)[0] == expected_doc for chunk_id in retrieved),
    }


def get_evaluator():
    # The high-level `patronus` SDK imports typing.Self (Python 3.11+), so it
    # fails on this 3.9 venv. `patronus_api` is the client it wraps, and works.
    from patronus_api import PatronusAPI

    api_key = os.getenv("PATRONUS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("PATRONUS_API_KEY is not set in .env")
    return PatronusAPI(api_key=api_key)


def answer_for(mode: str, question: str, chunks: list[dict]) -> str:
    if mode == "base":
        return "".join(generate_base(question))
    return "".join(generate_grounded(question, chunks))


def score(evaluator, question: str, chunks: list[dict], answer: str) -> dict:
    if not chunks:
        # Nothing was retrieved, so there is no context to check against.
        return {"patronus_pass": "", "patronus_score": "", "patronus_explanation": "no context retrieved"}
    response = evaluator.evaluations.evaluate(
        evaluators=[{"evaluator": "lynx", "criteria": "patronus:hallucination", "explain_strategy": "always"}],
        task_input=question,
        task_context=[chunk["text"] for chunk in chunks],
        task_output=answer,
        project_name="rag-jet-lab",
        app="hallucination-eval",
        capture="all",
    )
    result = response.results[0]
    if result.evaluation_result is None:
        raise RuntimeError(f"Patronus {result.status}: {result.error_message}")
    evaluation = result.evaluation_result
    return {
        "patronus_pass": evaluation.pass_,
        "patronus_score": evaluation.score_raw,
        "patronus_explanation": evaluation.explanation or "",
    }


def print_summary(results: list[dict]) -> None:
    print("\n=== Retrieval (answerable + partial questions) ===")
    with_source = {row["id"]: row for row in results if row["source_chunk_id"]}.values()
    if with_source:
        chunk_hits = sum(row["chunk_hit"] is True for row in with_source)
        doc_hits = sum(row["doc_hit"] is True for row in with_source)
        total = len(with_source)
        print(f"  exact source chunk in top 5: {chunk_hits}/{total}")
        print(f"  right document in top 5:     {doc_hits}/{total}")

    scored = [row for row in results if row["mode"] != "retrieval"]
    if not scored:
        return
    print("\n=== Patronus Lynx (PASS = no hallucination) ===")
    groups = defaultdict(list)
    for row in scored:
        groups[(row["mode"], row["category"])].append(row)
    for (mode, category), rows in sorted(groups.items()):
        passed = sum(row.get("patronus_pass") is True for row in rows)
        failed = sum(row.get("patronus_pass") is False for row in rows)
        other = len(rows) - passed - failed
        note = f"  ({other} not scored)" if other else ""
        print(f"  {mode:9s} {category:13s} pass {passed}/{passed + failed}{note}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["grounded", "base", "both"], default="grounded")
    parser.add_argument("--retrieval-only", action="store_true", help="only check retrieval; no OpenAI or Patronus calls")
    parser.add_argument("--limit", type=int, help="run only the first N questions")
    parser.add_argument("--ids", help="comma-separated question ids, e.g. q01,q31")
    args = parser.parse_args()

    refresh_env()
    ids = set(args.ids.split(",")) if args.ids else None
    questions = load_questions(ids, args.limit)
    modes = [] if args.retrieval_only else (["grounded", "base"] if args.mode == "both" else [args.mode])

    evaluator = None
    if modes:
        if not openai_configured():
            raise SystemExit("OPENAI_API_KEY is not set in .env")
        evaluator = get_evaluator()

    RESULTS_DIR.mkdir(exist_ok=True)
    label = "retrieval" if args.retrieval_only else args.mode
    out_path = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{label}.csv"

    results = []
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for n, row in enumerate(questions, start=1):
            print(f"[{n}/{len(questions)}] {row['id']} ({row['category']}) {row['question'][:70]}")
            base = {key: row[key] for key in ("id", "category", "question", "expected_answer", "source_chunk_id")}
            chunks = retrieve(row["question"])
            base.update(retrieval_check(row, chunks))

            for mode in modes or ["retrieval"]:
                record = {**base, "mode": mode}
                if mode != "retrieval":
                    try:
                        answer = answer_for(mode, row["question"], chunks)
                        record["answer"] = answer
                        if mode == "grounded" and answer == NO_CONTEXT:
                            record["patronus_explanation"] = "pipeline refused: nothing above similarity threshold"
                        else:
                            record.update(score(evaluator, row["question"], chunks, answer))
                    except Exception as exc:
                        record["error"] = f"{type(exc).__name__}: {exc}"
                        print(f"    error: {record['error']}")
                    time.sleep(0.5)
                writer.writerow(record)
                f.flush()
                results.append(record)
                if record.get("patronus_pass") != "" and "patronus_pass" in record:
                    verdict = "PASS" if record["patronus_pass"] else "FAIL"
                    print(f"    {mode}: {verdict}")

    print_summary(results)
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
