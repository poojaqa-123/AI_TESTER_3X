import json
import os
import time
import uuid

import pandas as pd
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from core import config, llm, pipeline, vectorstore

app = Flask(__name__)
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# filename -> {path, df} kept in memory for the lifetime of the process so the
# /upload preview and the /ingest stream can share the parsed dataframe.
_UPLOADS: dict[str, dict] = {}

# id of the point set used to answer the most recent chat turn, so /chunks can
# outline them in the UI.
_LAST_CITED_IDS: list[int] = []


def _read_table(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


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
        "tunables": {
            "chunk_size": config.CHUNK_SIZE, "chunk_overlap": config.CHUNK_OVERLAP,
            "top_n_hybrid": config.TOP_N_HYBRID, "top_k_rerank": config.TOP_K_RERANK,
            "rrf_k": config.RRF_K, "rewrite_enabled": config.REWRITE_ENABLED,
        },
    })


@app.post("/api/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        return jsonify({"error": "Only .csv, .xlsx, .xls files are supported"}), 400

    upload_id = uuid.uuid4().hex[:10]
    dest = config.UPLOAD_DIR / f"{upload_id}_{f.filename}"
    f.save(dest)

    try:
        df = _read_table(str(dest))
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


@app.get("/api/ingest/stream")
def ingest_stream():
    upload_id = request.args.get("upload_id", "")
    text_cols = [c for c in request.args.get("text_cols", "").split(",") if c]
    meta_cols = [c for c in request.args.get("meta_cols", "").split(",") if c]

    entry = _UPLOADS.get(upload_id)
    if not entry:
        return jsonify({"error": "Unknown upload_id — upload the file again."}), 400
    if not text_cols:
        return jsonify({"error": "Select at least one text column."}), 400

    df = entry["df"]

    def generate():
        try:
            for event in pipeline.run_ingest(df, text_cols, meta_cols, recreate=True):
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
        "priority": request.args.get("priority") or None,
        "module": request.args.get("module") or None,
        "jira_id": request.args.get("jira_id") or None,
    }
    filters = {k: v for k, v in filters.items() if v}

    if not vectorstore.collection_exists():
        return jsonify({"points": [], "next_offset": None, "cited_ids": _LAST_CITED_IDS})

    points, next_offset = vectorstore.scroll_chunks(limit=limit, offset=offset, search=search, filters=filters)
    out = []
    for p in points:
        payload = dict(p.payload or {})
        text = payload.pop("text", "")
        dense_vec = None
        sparse_preview = []
        if p.vector and isinstance(p.vector, dict):
            dense_vec = (p.vector.get("dense") or [])[:8]
            sparse = p.vector.get("sparse")
            if sparse is not None:
                pairs = sorted(zip(sparse.indices, sparse.values), key=lambda x: x[1], reverse=True)[:5]
                sparse_preview = [{"token_id": i, "weight": round(float(v), 4)} for i, v in pairs]
        out.append({
            "id": p.id, "payload": payload, "text": text,
            "dense_preview": dense_vec, "sparse_preview": sparse_preview,
            "cited": p.id in _LAST_CITED_IDS,
        })
    return jsonify({"points": out, "next_offset": next_offset})


@app.get("/api/chunks/filters")
def chunk_filter_options():
    if not vectorstore.collection_exists():
        return jsonify({"modules": [], "priorities": []})
    points, _ = vectorstore.scroll_chunks(limit=5000)
    modules = sorted({p.payload.get("module") for p in points if p.payload.get("module")})
    priorities = sorted({p.payload.get("priority") for p in points if p.payload.get("priority")})
    return jsonify({"modules": modules, "priorities": priorities})


@app.post("/api/chat/stream")
def chat_stream():
    body = request.get_json(force=True)
    query = (body or {}).get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    if not vectorstore.collection_exists():
        return jsonify({"error": "No collection ingested yet — go to Upload/Ingest first."}), 400
    if not config.LLM_API_KEY:
        return jsonify({"error": "No LLM API key configured (GROQ_API_KEY / OPENROUTER_API_KEY)."}), 400

    def generate():
        global _LAST_CITED_IDS
        try:
            for event in pipeline.run_chat(query):
                if event.get("stage") == "answer" and event.get("status") == "done":
                    _LAST_CITED_IDS = [c["id"] for c in event["detail"].get("citations", [])]
                yield sse(event)
        except Exception as e:
            yield sse({"stage": "error", "status": "error", "detail": {"message": str(e)}})

    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config.PORT, debug=False, threaded=True)
