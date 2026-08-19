"""Meeting transcript ingestion: splits on speaker/timestamp turn markers when
present, packing short turns together and sliding-windowing long ones."""

from pathlib import Path

from core.chunking.text_chunker import chunk_turns, split_by_speaker_turns
from ingestion.base import Chunk

TRANSCRIPT_EXTENSIONS = {".txt", ".md"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.name == "README.md":
            continue  # scaffolding, not ingestable content
        if path.is_file() and path.suffix.lower() in TRANSCRIPT_EXTENSIONS:
            yield path


def ingest(root: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        turns = split_by_speaker_turns(text)
        pieces = chunk_turns(turns, chunk_size, overlap)
        for i, piece in enumerate(pieces):
            chunks.append(Chunk(
                source_type="transcript", source_name=source_name, chunk_id=f"{path.name}#{i}",
                chunk_index=i, text=piece,
                meta={"meeting": path.stem},
            ))
    return chunks
