"""Code-repo ingestion adapter: walks a cloned/copied framework repo, reads
recognized source files, and chunks each one at function/class boundaries."""

from pathlib import Path

from core.chunking.code_chunker import chunk_file
from ingestion.base import Chunk

CODE_EXTENSIONS = {".java", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"}
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", ".venv", "venv", "__pycache__", ".idea", ".gradle"}
MAX_FILE_BYTES = 500_000  # skip generated/binary-ish files that would blow up ingestion time


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        yield path


def ingest(root: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not text.strip():
            continue
        rel_path = str(path.relative_to(root))
        chunks.extend(chunk_file(text, rel_path, source_name, chunk_size, overlap))
    return chunks
