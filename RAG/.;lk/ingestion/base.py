"""Shared Chunk type produced by every per-source-type adapter in this package,
and consumed uniformly by core/pipeline.py's embed+index step."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    source_type: str  # one of core.config.SOURCE_FOLDERS values: code/test_case/doc/transcript/chart/log
    source_name: str  # stable id for the ingested unit, e.g. "selenium_framework", "testdata.csv", "prd_v2.pdf"
    chunk_id: str      # unique within source_name, e.g. "LoginPage.java#3", "row12-c0", "build482#failure1"
    text: str
    row_index: int = 0
    chunk_index: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def char_len(self) -> int:
        return len(self.text)
