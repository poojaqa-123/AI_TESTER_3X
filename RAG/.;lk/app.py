import json
import uuid

import pandas as pd
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from core import config, llm, pipeline, vectorstore
from ingestion import code_repo, documents, jenkins_logs, lucid_charts, test_cases, transcripts

app = Flask(__name__)
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Non-test-case sources: fully automatic "scan folder -> ingest" adapters.
SOURCE_ADAPTERS = {
    "01_selenium_framework": ("code", code_repo),
    "02_playwright_framework": ("code", code_repo),
    "05_company_docs": ("doc", documents),
    "07_meeting_notes": ("transcript", transcripts),
    "08_lucid_charts": ("chart", lucid_charts),
    "09_prd_srs_brd_frd": ("doc", documents),
    "10_jenkins_logs": ("log", jenkins_logs),
}
# 03_test_cases needs a human to pick text/meta columns (see /api/test_cases/*).
# 04_jira_tickets and 06_figma_designs are Phase 2 — intentionally absent here.

# upload_id -> {path, df}, kept in memory for the lifetime of the process so the
# test-case upload preview and ingest stream can share the parsed dataframe.
_UPLOADS: dict[str, dict] = {}
_LAST_CITED_IDS: list = []


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    info = vectorstore.collection_info()
    return jsonify({
        "llm_provider": config.LLM_PROVIDER,
        "gen_model": config.GEN_MODEL,
        "rewrite_model": config.REWRITE_MODEL,
        "embed_model": config.EMBED_MODEL,
        "rerank_model": config.RERANK_MODEL,
        "collection": info,
        "counts_by_source_type": vectorstore.counts_by_source_type() if info.get("exists") else {},
        "tunables": {
            "chunk_profiles": config.CHUNK_PROFILES,
            "top_n_hybrid": config.TOP_N_HYBRID, "top_k_rerank": config.TOP_K_RERANK,
            "rrf_k": config.RRF_K, "rewrite_enabled": config.REWRITE_ENABLED,
        },
    })


@app.get("/api/sources")
def list_sources():
    out = []
    for key, (source_type, adapter) in SOURCE_ADAPTERS.items():
        root = config.DATA_SOURCES_DIR / key
        file_count = len(list(adapter.iter_files(root))) if root.exists() else 0
        out.append({
            "key": key, "source_type": source_type, "file_count": file_count,
            "indexed_chunks": vectorstore.count_for_source_name(key),
        })
    out.append({
        "key": "03_test_cases", "source_type": "test_case",
        "file_count": len(list((config.DATA_SOURCES_DIR / "03_test_cases").glob("*.csv"))) +
                      len(list((config.DATA_SOURCES_DIR / "03_test_cases").glob("*.xls*"))),
        "indexed_chunks": vectorstore.count_for_source_name("03_test_cases"),
    })
    return jsonify({"sources": out})


@app.get("/api/sources/<key>/ingest/stream")
def ingest_source_stream(key):
    if key not in SOURCE_ADAPTERS:
        return jsonify({"error": f"Unknown or unsupported source: {key}"}), 400
    source_type, adapter = SOURCE_ADAPTERS[key]
    root = config.DATA_SOURCES_DIR / key
    chunk_size, overlap = config.CHUNK_PROFILES[source_type]

    def generate():
        try:
            chunks = adapter.ingest(root, key, chunk_size, overlap)
            for event in pipeline.run_ingest_chunks(chunks, key):
                yield sse(event)
        except Exception as e:
            yield sse({"stage": "error", "status": "error", "detail": {"message": str(e)}})

    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.post("/api/test_cases/upload")
def upload_test_cases():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        return jsonify({"error": "Only .csv, .xlsx, .xls files are supported"}), 400

    upload_id = uuid.uuid4().hex[:10]
    dest = config.DATA_SOURCES_DIR / "03_test_cases" / f"{upload_id}_{f.filename}"
    f.save(dest)

    try:
        df = test_cases.read_table(str(dest))
    except Exception as e:
        return jsonify({"error": f"Could not parse file: {e}"}), 400

    _UPLOADS[upload_id] = {"path": str(dest), "df": df}
    preview_df = df.head(5)
    return jsonify({
        "upload_id": upload_id,
        "filename": f.filename,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "preview_rows": json.loads(preview_df.to_json(orient="records")),
    })


@app.get("/api/test_cases/ingest/stream")
def ingest_test_cases_stream():
    upload_id = request.args.get("upload_id", "")
    text_cols = [c for c in request.args.get("text_cols", "").split(",") if c]
    meta_cols = [c for c in request.args.get("meta_cols", "").split(",") if c]

    entry = _UPLOADS.get(upload_id)
    if not entry:
        return jsonify({"error": "Unknown upload_id — upload the file again."}), 400
    if not text_cols:
        return jsonify({"error": "Select at least one text column."}), 400

    df = entry["df"]
    chunk_size, overlap = config.CHUNK_PROFILES["test_case"]

    def generate():
        try:
            chunks = test_cases.ingest(df, text_cols, meta_cols, "03_test_cases", chunk_size, overlap)
            for event in pipeline.run_ingest_chunks(chunks, "03_test_cases"):
                yield sse(event)
        except Exception as e:
            yield sse({"stage": "error", "status": "error", "detail": {"message": str(e)}})

    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.get("/api/chunks")
def list_chunks():
    limit = int(request.args.get("limit", 50))
    offset = request.args.get("offset")
    offset = int(offset) if offset not in (None, "", "null") else None
    search = request.args.get("search") or None
    filters = {
        "source_type": request.args.get("source_type") or None,
        "source_name": request.args.get("source_name") or None,
    }
    filters = {k: v for k, v in filters.items() if v}

    if not vectorstore.collection_exists():
        return jsonify({"points": [], "next_offset": None, "cited_ids": _LAST_CITED_IDS})

    points, next_offset = vectorstore.scroll_chunks(limit=limit, offset=offset, search=search, filters=filters)
    out = []
    for p in points:
        payload = dict(p.payload or {})
        text = payload.pop("text", "")
        out.append({
            "id": p.id, "payload": payload, "text": text,
            "cited": p.id in _LAST_CITED_IDS,
        })
    return jsonify({"points": out, "next_offset": next_offset})


@app.post("/api/chat/stream")
def chat_stream():
    body = request.get_json(force=True)
    query = (body or {}).get("query", "").strip()
    mode = (body or {}).get("mode", "answer")
    source_types = (body or {}).get("source_types") or None
    if not query:
        return jsonify({"error": "query is required"}), 400
    if not vectorstore.collection_exists():
        return jsonify({"error": "No collection ingested yet — go to Sources first."}), 400
    if not config.LLM_API_KEY:
        return jsonify({"error": "No LLM API key configured (GROQ_API_KEY / OPENROUTER_API_KEY)."}), 400

    def generate():
        global _LAST_CITED_IDS
        try:
            for event in pipeline.run_chat(query, mode, source_types):
                if event.get("stage") == "answer" and event.get("status") == "done":
                    _LAST_CITED_IDS = [c["id"] for c in event["detail"].get("citations", [])]
                yield sse(event)
        except Exception as e:
            yield sse({"stage": "error", "status": "error", "detail": {"message": str(e)}})

    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False, threaded=True)
