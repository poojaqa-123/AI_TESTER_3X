"""Formats a retrieved chunk's Qdrant payload into a human-readable citation,
tailored per source_type so answers point back to something a QA engineer can
actually open."""


def format_citation(payload: dict) -> str:
    source_type = payload.get("source_type")
    if source_type == "code":
        file_path = payload.get("file_path", "?")
        line = payload.get("line_start")
        return f"{file_path}:{line}" if line else file_path
    if source_type == "doc":
        doc_name = payload.get("doc_name", "?")
        page = payload.get("page")
        heading = payload.get("heading")
        if page:
            return f"{doc_name} (page {page})"
        if heading:
            return f"{doc_name} — {heading}"
        return doc_name
    if source_type == "log":
        job = payload.get("job_name", "?")
        build = payload.get("build_number")
        return f"{job} #{build}" if build else job
    if source_type == "transcript":
        return payload.get("meeting", "meeting notes")
    if source_type == "chart":
        return payload.get("chart_name", "chart")
    if source_type == "test_case":
        jira_id = payload.get("jira_id")
        title = payload.get("title")
        if jira_id:
            return f"{jira_id} — {title}" if title else jira_id
        return title or "test case"
    return payload.get("chunk_id", "source")
