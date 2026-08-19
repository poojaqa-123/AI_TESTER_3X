"""Generic prose chunker shared by documents, transcripts, and lucid charts:
split into logical sections first (markdown headings / speaker turns / plain
paragraphs), then sliding-window each section so no chunk exceeds chunk_size,
with `overlap` characters repeated between neighbors for context continuity.
"""

import re

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
SPEAKER_RE = re.compile(r"^(?:\[\d{1,2}:\d{2}(?::\d{2})?\]\s*)?[A-Z][\w .'-]{0,40}:\s", re.MULTILINE)


def sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
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


def split_by_headings(text: str) -> list[tuple[str, str]]:
    """Markdown-style '#' headings -> [(heading, section_text), ...]. Falls back
    to a single ("", text) section when no headings are found."""
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]
    sections = []
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end].strip()))
    return sections


def split_by_speaker_turns(text: str) -> list[str]:
    """Splits on 'Speaker: ...' or '[00:12:34] Speaker: ...' style turn markers.
    Falls back to paragraph splitting when no turn markers are found."""
    matches = list(SPEAKER_RE.finditer(text))
    if len(matches) < 2:
        return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    turns = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        turn = text[start:end].strip()
        if turn:
            turns.append(turn)
    return turns


def chunk_sections(sections: list[tuple[str, str]], chunk_size: int, overlap: int) -> list[dict]:
    """sections -> [{"heading": str, "text": str}, ...] chunks, sliding-windowing
    any section that exceeds chunk_size."""
    out = []
    for heading, body in sections:
        for piece in sliding_window(body, chunk_size, overlap):
            out.append({"heading": heading, "text": piece})
    return out


def chunk_turns(turns: list[str], chunk_size: int, overlap: int) -> list[str]:
    """Packs consecutive speaker turns into chunks up to chunk_size (so short
    back-and-forth exchanges stay together), sliding-windowing any single turn
    that alone exceeds chunk_size."""
    out = []
    buf = ""
    for turn in turns:
        if len(turn) > chunk_size:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(sliding_window(turn, chunk_size, overlap))
            continue
        candidate = f"{buf}\n\n{turn}" if buf else turn
        if len(candidate) > chunk_size:
            out.append(buf)
            buf = turn
        else:
            buf = candidate
    if buf:
        out.append(buf)
    return out
