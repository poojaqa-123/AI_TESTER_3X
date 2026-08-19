"""Jenkins log ingestion: extracts failure/summary blocks per build file."""

from pathlib import Path

from core.chunking.log_chunker import chunk_log
from ingestion.base import Chunk

LOG_EXTENSIONS = {".log", ".txt"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in LOG_EXTENSIONS:
            yield path


def ingest(root: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        file_chunks = chunk_log(text, path.stem, chunk_size)
        # chunk_log's source_name/chunk_id are only unique within one log file;
        # re-key both against the shared folder-level source_name so ids stay
        # unique across every build file in this source.
        for c in file_chunks:
            c.meta.setdefault("log_file", path.name)
            c.chunk_id = f"{path.stem}-{c.chunk_id}"
            c.source_name = source_name
        chunks.extend(file_chunks)
    return chunks
