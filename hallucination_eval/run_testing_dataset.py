"""Run every query in the testing dataset through the grounded model via the API.

For each row in the input CSV (columns: Source, Query):

  POST /api/retrieve { query }                       → chunks + similarity scores
  POST /api/chat     { query, mode: grounded,
                       chunk_ids: [ids from retrieve] } → answer

The answer is generated from exactly the chunks recorded in the row, because
the retrieved ids are passed back to /api/chat.

Output keeps the input columns and adds:

  answer   the grounded answer text
  chunks   JSON list of retrieved chunk texts
  scores   JSON list of cosine similarity scores, aligned with chunks

Start the API first, from the project root:

  uvicorn backend.api.main:app --port 8000

Then:

  python -m hallucination_eval.run_testing_dataset
  python -m hallucination_eval.run_testing_dataset --input path/to/testing_dataset.csv --limit 2
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = EVAL_DIR / "testing_dataset.csv"
RESULTS_DIR = EVAL_DIR / "results"


def retrieve(api: str, query: str) -> list[dict]:
    response = requests.post(f"{api}/api/retrieve", json={"query": query}, timeout=60)
    response.raise_for_status()
    return response.json()["chunks"]


def grounded_answer(api: str, query: str, chunk_ids: list[str]) -> str:
    response = requests.post(
        f"{api}/api/chat",
        json={"query": query, "mode": "grounded", "chunk_ids": chunk_ids},
        timeout=180,
    )
    response.raise_for_status()
    return response.text


def run_query(api: str, query: str) -> pd.Series:
    try:
        chunks = retrieve(api, query)
        answer = grounded_answer(api, query, [chunk["id"] for chunk in chunks])
        error = ""
    except requests.RequestException as exc:
        chunks, answer, error = [], "", f"{type(exc).__name__}: {exc}"
        print(f"    error: {error}")
    return pd.Series(
        {
            "answer": answer,
            "chunks": json.dumps([chunk["text"] for chunk in chunks], ensure_ascii=False),
            "scores": json.dumps([chunk["score"] for chunk in chunks]),
            "error": error,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CSV with a Query column")
    parser.add_argument("--output", type=Path, help="defaults to results/<timestamp>_testing_dataset.csv")
    parser.add_argument("--api", default="http://localhost:8000", help="base URL of the running API")
    parser.add_argument("--limit", type=int, help="run only the first N queries")
    args = parser.parse_args()

    requests.get(f"{args.api}/api/health", timeout=10).raise_for_status()

    df = pd.read_csv(args.input)
    df.columns = df.columns.str.strip()
    df["Query"] = df["Query"].str.strip()
    if "Source" in df:
        # Some source titles in the sheet contain line breaks and stray spaces.
        df["Source"] = df["Source"].str.split().str.join(" ")
    if args.limit:
        df = df.head(args.limit)

    def run_row(row: pd.Series) -> pd.Series:
        print(f"[{row.name + 1}/{len(df)}] {row['Query'][:80]}")
        return run_query(args.api, row["Query"])

    df = df.join(df.apply(run_row, axis=1))

    out_path = args.output or RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_testing_dataset.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    failed = (df["error"] != "").sum()
    print(f"\n{len(df) - failed}/{len(df)} queries answered. Results: {out_path}")


if __name__ == "__main__":
    main()
