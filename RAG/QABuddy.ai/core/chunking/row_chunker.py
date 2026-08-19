"""Row -> document -> chunk pipeline for spreadsheet-style sources (test cases).
Each row becomes one "document" (the concatenation of its selected text
columns); the row is used as-is when short, and sliding-windowed when longer
than chunk_size (ported from Advance_RAG's chunking.py)."""

from ingestion.base import Chunk

from .text_chunker import sliding_window


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


def chunk_dataframe(df, text_cols: list[str], meta_cols: list[str], source_name: str,
                     chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for row_index, row in enumerate(df.to_dict(orient="records")):
        doc_text = build_doc_text(row, text_cols)
        if not doc_text:
            continue
        meta = {col: row.get(col) for col in meta_cols if col in row}
        pieces = sliding_window(doc_text, chunk_size, overlap)
        for chunk_index, piece in enumerate(pieces):
            chunk_id = f"row{row_index}-c{chunk_index}"
            chunks.append(Chunk(
                source_type="test_case", source_name=source_name, chunk_id=chunk_id,
                row_index=row_index, chunk_index=chunk_index, text=piece, meta=meta,
            ))
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
