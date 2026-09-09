"""Test-case (CSV/XLSX) ingestion. Unlike the other adapters this needs a human
to pick which columns are embeddable text vs. filterable metadata, so the
Sources tab drives it through an upload+preview+column-select flow (mirroring
Advance_RAG's UI) rather than a single one-click "scan and ingest" button."""

from pathlib import Path

import pandas as pd

from core.chunking.row_chunker import chunk_dataframe
from ingestion.base import Chunk


def read_table(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def ingest(df: pd.DataFrame, text_cols: list[str], meta_cols: list[str], source_name: str,
           chunk_size: int, overlap: int) -> list[Chunk]:
    return chunk_dataframe(df, text_cols, meta_cols, source_name, chunk_size, overlap)
