"""Row -> document -> chunk pipeline.

Each source row becomes one "document" (the concatenation of its selected
text columns). Small documents stay as a single chunk; larger ones are split
with a sliding window so no chunk exceeds CHUNK_SIZE, with CHUNK_OVERLAP
characters repeated between neighbors for context continuity.
"""

from dataclasses import dataclass, field
from typing import Any

from . import config


@dataclass
class Chunk:
    chunk_id: str
    row_index: int
    chunk_index: int
    text: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def char_len(self) -> int:
        return len(self.text)


def build_doc_text(row: dict, text_cols: list[str]) -> str:
    parts = []
    for col in text_cols:
        val = row.get(col)
        if val is None or (isinstance(val, float) and str(val) == "nan"):
            continue
        val = str(val).strip()
        if val:
            parts.append(f"{col.replace('_', ' ').title()}: {val}")
    return "\n".join(parts)


def split_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap if overlap is not None else config.CHUNK_OVERLAP

    if len(text) <= chunk_size:
        return [text]

    pieces = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        end = min(len(text), start + chunk_size)
        pieces.append(text[start:end])
        if end == len(text):
            break
        start += step
    return pieces


def chunk_dataframe(df, text_cols: list[str], meta_cols: list[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for row_index, row in enumerate(df.to_dict(orient="records")):
        doc_text = build_doc_text(row, text_cols)
        if not doc_text:
            continue
        meta = {col: row.get(col) for col in meta_cols if col in row}
        pieces = split_text(doc_text)
        for chunk_index, piece in enumerate(pieces):
            chunk_id = f"row{row_index}-c{chunk_index}"
            chunks.append(
                Chunk(chunk_id=chunk_id, row_index=row_index, chunk_index=chunk_index, text=piece, meta=meta)
            )
    return chunks


def chunk_stats(chunks: list[Chunk]) -> dict:
    if not chunks:
        return {"total": 0, "avg_chars": 0, "min_chars": 0, "max_chars": 0, "histogram": []}
    lengths = [c.char_len for c in chunks]
    buckets = [0, 200, 400, 600, 800, 1000, 1200]
    histogram = []
    for i in range(len(buckets)):
        lo = buckets[i]
        hi = buckets[i + 1] if i + 1 < len(buckets) else float("inf")
        count = sum(1 for length in lengths if lo <= length < hi)
        label = f"{lo}-{int(hi)}" if hi != float("inf") else f"{lo}+"
        histogram.append({"bucket": label, "count": count})
    return {
        "total": len(chunks),
        "avg_chars": round(sum(lengths) / len(lengths), 1),
        "min_chars": min(lengths),
        "max_chars": max(lengths),
        "histogram": histogram,
    }
