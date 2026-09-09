"""Jenkins log chunker: extracts failure/stack-trace blocks (one chunk each)
plus a single rollup summary chunk per build run, instead of embedding the
whole (often megabyte-scale, mostly-noise) console log. Keeps token usage low
per the QABuddy.ai constraint."""

import re

from ingestion.base import Chunk

from .text_chunker import sliding_window

FAILURE_START_RE = re.compile(
    r"^\s*(?:FAILED|FAILURE|ERROR)\b|"
    r"^\s*\w*(?:Exception|Error)\b.*|"
    r"^\s*java\.\w+\.\w*(?:Exception|Error)|"
    r"AssertionError",
    re.IGNORECASE,
)
CONTINUATION_RE = re.compile(r"^\s*(?:at\s|Caused by:|\.\.\.\s*\d+\s*more)")
SUMMARY_RE = re.compile(
    r"Tests run:\s*\d+.*|BUILD SUCCESS.*|BUILD FAILURE.*|Finished:\s*\w+.*",
    re.IGNORECASE,
)
JOB_BUILD_RE = re.compile(r"(?P<job>.+?)[_-](?P<build>\d+)$")


def parse_job_build(source_name: str) -> dict:
    stem = source_name.rsplit(".", 1)[0]
    m = JOB_BUILD_RE.match(stem)
    if m:
        return {"job_name": m.group("job"), "build_number": m.group("build")}
    return {"job_name": stem, "build_number": None}


def extract_failure_blocks(lines: list[str]) -> list[str]:
    blocks = []
    i = 0
    while i < len(lines):
        if FAILURE_START_RE.search(lines[i]):
            block = [lines[i]]
            j = i + 1
            while j < len(lines) and (CONTINUATION_RE.match(lines[j]) or lines[j].strip() == ""):
                if lines[j].strip():
                    block.append(lines[j])
                j += 1
                if len(block) > 200:  # safety cap per block
                    break
            blocks.append("\n".join(block))
            i = j
        else:
            i += 1
    return blocks


def extract_summary(text: str, lines: list[str]) -> str:
    matches = SUMMARY_RE.findall(text)
    if matches:
        return "\n".join(matches[:20])
    # Fallback: Jenkins console output usually has the job/result context in the
    # head and tail of the log even without a recognizable summary line.
    head = "\n".join(lines[:15])
    tail = "\n".join(lines[-15:])
    return f"{head}\n...\n{tail}"


def chunk_log(text: str, source_name: str, chunk_size: int) -> list[Chunk]:
    lines = text.splitlines()
    job_build = parse_job_build(source_name)

    chunks = []
    for i, block in enumerate(extract_failure_blocks(lines)):
        for j, piece in enumerate(sliding_window(block, chunk_size, 0)):
            chunks.append(Chunk(
                source_type="log", source_name=source_name, chunk_id=f"failure{i}-{j}",
                chunk_index=len(chunks), text=piece,
                meta={**job_build, "block_type": "failure"},
            ))

    summary = extract_summary(text, lines)
    if summary.strip():
        chunks.append(Chunk(
            source_type="log", source_name=source_name, chunk_id="summary",
            chunk_index=len(chunks), text=summary,
            meta={**job_build, "block_type": "summary"},
        ))
    return chunks
