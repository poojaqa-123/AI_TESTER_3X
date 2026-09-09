"""JIRA ticket ingestion — Phase 2, deferred (see data_sources/04_jira_tickets/README.md).

Interface only, not wired into app.py or core/config.SOURCE_FOLDERS. Calling
either function raises until this is built. Planned shape once a JIRA MCP
connection or REST API token is available:

- `fetch_via_jql(jql)`: MCP calls the configured JIRA MCP tool's search
  endpoint with `jql`; REST fallback GETs
  `{JIRA_BASE_URL}/rest/api/2/search?jql=...` with an API token (email + token
  Basic Auth), paginating on `startAt`.
- `ingest(tickets, source_name, chunk_size, overlap)`: one "row" per ticket —
  concatenate summary + description + comments, same sliding-window chunking
  as core/chunking/row_chunker.py, with meta = {key, status, assignee, sprint,
  labels, issue_type}.
"""

from pathlib import Path

from ingestion.base import Chunk


def fetch_via_jql(jql: str) -> list[dict]:
    raise NotImplementedError("JIRA ingestion is Phase 2 — not implemented yet")


def ingest(tickets: list[dict], source_name: str, chunk_size: int, overlap: int) -> list[Chunk]:
    raise NotImplementedError("JIRA ingestion is Phase 2 — not implemented yet")
