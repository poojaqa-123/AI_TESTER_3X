"""Document ingestion adapter for company docs and PRD/SRS/BRD/FRD: parses
.pdf (per-page, via pypdf) and .md (via heading split), then chunks each
section with the shared text chunker."""

from pathlib import Path

from core.chunking.text_chunker import chunk_sections, split_by_headings
from ingestion.base import Chunk

DOC_EXTENSIONS = {".pdf", ".md"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.name == "README.md":
            continue  # scaffolding, not ingestable content
        if path.is_file() and path.suffix.lower() in DOC_EXTENSIONS:
            yield path


def _extract_pdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
    except Exception:
        return []
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def _chunks_for_pdf(path: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    pages = _extract_pdf_pages(path)
    sections = [(f"Page {i + 1}", text) for i, text in enumerate(pages) if text.strip()]
    chunk_dicts = chunk_sections(sections, chunk_size, overlap)
    chunks = []
    for i, cd in enumerate(chunk_dicts):
        page_num = cd["heading"].replace("Page ", "") if cd["heading"] else None
        chunks.append(Chunk(
            source_type="doc", source_name=source_name, chunk_id=f"{path.name}#{i}",
            chunk_index=i, text=cd["text"],
            meta={"doc_name": path.name, "page": page_num},
        ))
    return chunks


def _chunks_for_markdown(path: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    sections = split_by_headings(text)
    chunk_dicts = chunk_sections(sections, chunk_size, overlap)
    chunks = []
    for i, cd in enumerate(chunk_dicts):
        chunks.append(Chunk(
            source_type="doc", source_name=source_name, chunk_id=f"{path.name}#{i}",
            chunk_index=i, text=cd["text"],
            meta={"doc_name": path.name, "heading": cd["heading"] or None},
        ))
    return chunks


def ingest(root: Path, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in iter_files(root):
        if path.suffix.lower() == ".pdf":
            chunks.extend(_chunks_for_pdf(path, source_name, chunk_size, overlap))
        else:
            chunks.extend(_chunks_for_markdown(path, source_name, chunk_size, overlap))
    return chunks
