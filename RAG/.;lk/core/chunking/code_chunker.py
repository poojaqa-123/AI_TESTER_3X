"""Code chunker: splits a source file at function/class/method boundaries using
per-language regex heuristics (not a full AST parse — good enough for RAG
retrieval granularity). Falls back to a plain sliding window for files with no
recognizable boundaries (config/XML/JSON/build files, or unsupported languages).
"""

import re

from ingestion.base import Chunk

from .text_chunker import sliding_window

EXT_LANGUAGE = {
    ".java": "java",
    ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts", ".mjs": "ts",
    ".py": "python",
}

_JAVA_DEF = re.compile(
    r"^[ \t]*(?:@\w+(?:\([^)]*\))?[ \t]*\n)*[ \t]*"
    r"(?:(?:public|private|protected|static|final|abstract|synchronized|native)[ \t]+)*"
    r"(?:class|interface|enum)[ \t]+\w+"
    r"|^[ \t]*(?:@\w+(?:\([^)]*\))?[ \t]*\n)*[ \t]*"
    r"(?:(?:public|private|protected|static|final|abstract|synchronized|native)[ \t]+)+"
    r"[\w<>\[\],. ]+[ \t]+\w+[ \t]*\([^;{]*\)[ \t]*(?:throws[ \t]+[\w.,\s]+)?[ \t]*\{",
    re.MULTILINE,
)

_TS_DEF = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:abstract[ \t]+)?class[ \t]+\w+"
    r"|^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:async[ \t]+)?function\*?[ \t]*\w*[ \t]*\("
    r"|^[ \t]*(?:export[ \t]+)?(?:const|let|var)[ \t]+\w+[ \t]*=[ \t]*(?:async[ \t]*)?\([^)]*\)[ \t]*(?::[^=]+)?=>"
    r"|^[ \t]*(?:public|private|protected|static|async)[ \t]+[\w<>]+[ \t]*\([^;{]*\)[ \t]*(?::[^{]+)?\{",
    re.MULTILINE,
)

_PY_DEF = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+\w+[ \t]*\(|^[ \t]*class[ \t]+\w+", re.MULTILINE)

_DEF_RE = {"java": _JAVA_DEF, "ts": _TS_DEF, "python": _PY_DEF}


def detect_language(file_path: str) -> str | None:
    for ext, lang in EXT_LANGUAGE.items():
        if file_path.lower().endswith(ext):
            return lang
    return None


def split_by_definitions(text: str, language: str | None) -> list[str]:
    pattern = _DEF_RE.get(language)
    if not pattern:
        return [text]
    matches = list(pattern.finditer(text))
    if not matches:
        return [text]
    segments = []
    if matches[0].start() > 0:
        segments.append(text[: matches[0].start()])
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.append(text[m.start():end])
    return [s for s in segments if s.strip()]


def _merge_small_segments(segments: list[str], chunk_size: int) -> list[str]:
    """Packs consecutive tiny segments (imports, one-line getters) together up
    to chunk_size so we don't index hundreds of near-empty chunks."""
    out, buf = [], ""
    for seg in segments:
        candidate = f"{buf}\n\n{seg}" if buf else seg
        if len(candidate) > chunk_size and buf:
            out.append(buf)
            buf = seg
        else:
            buf = candidate
    if buf:
        out.append(buf)
    return out


def _line_starts(text: str, pieces: list[str]) -> list[int | None]:
    """Best-effort 1-indexed starting line number for each piece, located by
    scanning forward through the original text so ordering stays consistent
    even with overlapping/duplicated substrings."""
    starts = []
    cursor = 0
    for piece in pieces:
        idx = text.find(piece, cursor)
        if idx == -1:
            idx = text.find(piece)
        if idx == -1:
            starts.append(None)
            continue
        starts.append(text.count("\n", 0, idx) + 1)
        cursor = idx + 1
    return starts


def chunk_file(text: str, file_path: str, source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    language = detect_language(file_path)
    segments = split_by_definitions(text, language)
    segments = _merge_small_segments(segments, chunk_size)

    pieces: list[str] = []
    for seg in segments:
        pieces.extend(sliding_window(seg, chunk_size, overlap))
    line_starts = _line_starts(text, pieces)

    chunks = []
    for i, piece in enumerate(pieces):
        chunks.append(Chunk(
            source_type="code", source_name=source_name, chunk_id=f"{file_path}#{i}",
            chunk_index=i, text=piece,
            meta={"file_path": file_path, "language": language or "text", "line_start": line_starts[i]},
        ))
    return chunks
