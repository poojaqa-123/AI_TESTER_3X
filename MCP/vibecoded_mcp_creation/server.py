import csv
import json
from pathlib import Path

from fastmcp import FastMCP

CSV_PATH = Path(__file__).resolve().parent.parent / "resource" / "vwo_test_cases.csv"
SAMPLE_SIZE = 500

mcp = FastMCP("vibecoded-testcase-mcp")


def _load_test_cases() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for _, row in zip(range(SAMPLE_SIZE), reader)]


TEST_CASES = _load_test_cases()
TEST_CASES_BY_ID = {row["id"]: row for row in TEST_CASES}


@mcp.resource("resource://testcases/all")
def all_test_cases() -> str:
    """Summarized list of the 500 loaded test cases."""
    summary = [
        {
            "id": row["id"],
            "jira_id": row["jira_id"],
            "title": row["title"],
            "module": row["module"],
            "priority": row["priority"],
            "status": row["status"],
        }
        for row in TEST_CASES
    ]
    return json.dumps(summary)


@mcp.prompt()
def review_test_case_prompt(id: str) -> str:
    """Ask an LLM to review a test case's steps and expected result for gaps."""
    row = TEST_CASES_BY_ID.get(id)
    if row is None:
        return f"No test case found with id {id}."
    return (
        f"Review test case {row['jira_id']} ('{row['title']}').\n"
        f"Preconditions: {row['preconditions']}\n"
        f"Steps: {row['steps']}\n"
        f"Expected: {row['expected']}\n\n"
        "Suggest any missing edge cases or ambiguous steps."
    )


@mcp.tool()
def search_test_case(query: str) -> list[dict]:
    """Keyword search over title/module/tags within the loaded 500 test cases."""
    q = query.lower()
    results = []
    for row in TEST_CASES:
        haystack = f"{row['title']} {row['module']} {row['tags']}".lower()
        if q in haystack:
            results.append(
                {
                    "id": row["id"],
                    "jira_id": row["jira_id"],
                    "title": row["title"],
                    "status": row["status"],
                }
            )
    return results


@mcp.tool()
def get_test_case(id: str) -> dict:
    """Full record for one test case by id."""
    row = TEST_CASES_BY_ID.get(id)
    if row is None:
        raise ValueError(f"No test case found with id {id}")
    return row


@mcp.tool()
def test_case_status(id: str) -> str:
    """Return just the status field for a given test case id."""
    row = TEST_CASES_BY_ID.get(id)
    if row is None:
        raise ValueError(f"No test case found with id {id}")
    return row["status"]


if __name__ == "__main__":
    mcp.run()
