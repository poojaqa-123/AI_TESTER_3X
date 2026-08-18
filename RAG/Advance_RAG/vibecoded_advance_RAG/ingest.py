#!/usr/bin/env python3
"""CLI ingestion, mirroring the /ingest SSE flow used by the web UI.

Usage:
    python ingest.py data/test_cases.csv \\
        --text-cols title,steps,expected,tags \\
        --meta-cols id,jira_id,priority,module
"""

import argparse
import sys

import pandas as pd

from core import pipeline


def read_table(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Path to a .csv or .xlsx file")
    parser.add_argument("--text-cols", required=True, help="Comma-separated columns to embed")
    parser.add_argument("--meta-cols", default="", help="Comma-separated columns to keep as Qdrant payload/filters")
    parser.add_argument("--no-recreate", action="store_true", help="Append to an existing collection instead of replacing it")
    args = parser.parse_args()

    text_cols = [c.strip() for c in args.text_cols.split(",") if c.strip()]
    meta_cols = [c.strip() for c in args.meta_cols.split(",") if c.strip()]

    try:
        df = read_table(args.file)
    except Exception as e:
        print(f"Failed to read {args.file}: {e}", file=sys.stderr)
        sys.exit(1)

    missing = [c for c in text_cols + meta_cols if c not in df.columns]
    if missing:
        print(f"Columns not found in {args.file}: {missing}", file=sys.stderr)
        print(f"Available columns: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingesting {len(df)} rows from {args.file}")
    print(f"  text-cols: {text_cols}")
    print(f"  meta-cols: {meta_cols}\n")

    for event in pipeline.run_ingest(df, text_cols, meta_cols, recreate=not args.no_recreate):
        stage = event["stage"]
        status = event["status"]
        detail = event["detail"]
        if stage == "embed" and status == "progress":
            print(f"\r  embedding: {detail['done']}/{detail['total']}", end="", flush=True)
            continue
        if stage == "embed" and status == "done":
            print(f"\r  embedding: {detail['total']}/{detail['total']} done (dim={detail['dim']})")
            continue
        if stage == "error":
            print(f"\n[error] {detail['message']}", file=sys.stderr)
            sys.exit(1)
        print(f"[{stage}] {detail}")

    print("\nDone.")


if __name__ == "__main__":
    main()
