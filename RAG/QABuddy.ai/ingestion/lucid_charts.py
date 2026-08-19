"""Lucid chart (exported-to-text) ingestion: short prose, single chunk unless
the export is unusually large."""

from pathlib import Path

from core.chunking.text_chunker import sliding_window
from ingestion.base import Chunk

CHART_EXTENSIONS = {".txt", ".md"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.name == "README.md":
            continue  # scaffolding, not ingestable content
        if path.is_file() and path.suffix.lower() in CHART_EXTENSIONS:
            yield path


def ingest(root: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        for i, piece in enumerate(sliding_window(text, chunk_size, overlap)):
            chunks.append(Chunk(
                source_type="chart", source_name=source_name, chunk_id=f"{path.name}#{i}",
                chunk_index=i, text=piece,
                meta={"chart_name": path.stem},
            ))
    return chunks
