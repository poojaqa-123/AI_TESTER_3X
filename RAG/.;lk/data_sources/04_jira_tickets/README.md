# 04 — JIRA tickets (Phase 2 — deferred)

Not built in Phase 1. Planned: connect via JIRA MCP (or REST API + JQL) and ingest
all tickets matching a JQL query — one document per ticket (summary + description +
comments), same row-style chunking as test cases (1000/150 chars), with metadata
(ticket key, status, assignee, sprint, labels) kept in the Qdrant payload for
filtering and citation.

`ingestion/jira_tickets.py` contains the adapter interface stub only — it is not
wired into the app yet. Revisit once a JIRA MCP connection (or API token) is
available.
