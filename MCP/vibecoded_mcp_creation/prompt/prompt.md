# RICE POT Prompt — Simple Test Case MCP (Tools + Resources + Prompts)

## R — Role
You are a Python backend engineer building a minimal, teaching-quality MCP
server using the **FastMCP** library — the goal is to demonstrate all three
MCP primitives (tools, resources, prompts) working together in one small,
readable server, not a production system.

## I — Instructions
Build a single-file (or minimal multi-file) MCP server called
**`vibecoded-testcase-mcp`** that:

1. Loads the **first 500 rows** from
   `MCP/resource/vwo_test_cases.csv` at startup into memory.
2. Exposes exactly **one resource**:
   - `resource://testcases/all` — returns the 500 loaded test cases as JSON
     (id, jira_id, title, module, priority, status).
3. Exposes exactly **one prompt**:
   - `review_test_case_prompt(id: int)` — a prompt template that asks an LLM
     to review the test case with the given id (its steps, preconditions,
     expected result) and suggest improvements or flag missing edge cases.
4. Exposes **tools** (at least 3, reusing the same shape agreed earlier):
   - `search_test_case(query: str) -> list[dict]` — keyword search over
     title/module/tags within the loaded 500.
   - `get_test_case(id: int) -> dict` — full record for one test case.
   - `test_case_status(id: int) -> str` — just the status field.

Keep it simple: no database, no pagination, no auth — just a clear
demonstration of resources + prompts + tools coexisting in one FastMCP app.

After building it, **run the server** and **open it in the MCP Inspector
(debugger mode)** so the tools/resources/prompts can be exercised live.

## C — Context
- Full dataset has ~27,000 rows; this demo intentionally uses only the first
  500 to keep it lightweight and fast to load/inspect.
- Source CSV columns: id, jira_id, issue_type, module, epic_link, title,
  priority, status, test_type, preconditions, steps, test_data, expected,
  tags, reporter, assignee, created, updated, sprint.
- Server must run over stdio so it can be registered with Claude Code
  (`claude mcp add`) and connected to via `npx @modelcontextprotocol/inspector`.
- Target location: `MCP/vibecoded_mcp_creation/` (sibling of `MCP/resource/`).

## E — Examples
```
search_test_case("email alerts")
→ [{"id": 1, "jira_id": "VWO-1001", "title": "Verify the behavior when enabling email alerts...", "status": "Done"}]

get_test_case(1)
→ {id, jira_id, title, module, priority, status, test_type, preconditions, steps, test_data, expected, tags, ...}

test_case_status(1)
→ "Done"

resource://testcases/all
→ [{...500 summarized records...}]

review_test_case_prompt(1)
→ "Review test case VWO-1001 ('Verify the behavior when enabling email alerts...'). \
   Steps: ... Expected: ... Suggest missing edge cases or ambiguous steps."
```

## P — Persona
A developer learning/demoing MCP concepts who wants one small server that
clearly shows the difference between a *resource* (raw data), a *prompt*
(reusable instruction template), and a *tool* (callable function) — using
real QA test case data as the running example.

## O — Output
```
MCP/vibecoded_mcp_creation/
├── prompt/
│   └── prompt.md            # this spec
├── server.py                 # FastMCP app: 1 resource, 1 prompt, 3 tools
└── requirements.txt           # fastmcp, pandas (or csv)
```
Plus, as part of completing the task:
- The server actually running (stdio).
- The `claude mcp add` command used to register it.
- The MCP Inspector opened and connected to it for live debugging.

## T — Tone
Simple and demonstrative over robust — prioritize readability of the code
(few lines, obvious mapping from CSV row → tool/resource/prompt output) over
edge-case handling or performance optimization.
