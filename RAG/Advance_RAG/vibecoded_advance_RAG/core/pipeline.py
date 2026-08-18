"""Orchestrates the two pipelines described in prompt.md, yielding SSE-ready
event dicts at each stage so the UI's pipeline tracker can update live.

Stage 1 (Ingest):
  CSV/XLSX -> rows -> assemble docs -> chunk -> bge-m3 (dense+sparse) -> Qdrant

Stage 2 (Chat):
  Question -> rewrite -> embed -> dense+sparse search -> RRF fuse -> rerank -> LLM answer
"""

import time

from . import chunking, config, embeddings, fusion, llm, reranker, vectorstore


def _point_preview(point, rank: int = None) -> dict:
    payload = dict(point.payload or {})
    text = payload.pop("text", "")
    return {
        "id": point.id,
        "rank": rank,
        "score": round(float(point.score), 4) if getattr(point, "score", None) is not None else None,
        "text_preview": text[:220],
        "meta": payload,
    }


def run_ingest(df, text_cols: list[str], meta_cols: list[str], recreate: bool = True):
    t0 = time.time()
    yield {"stage": "read", "status": "done", "detail": {
        "rows": int(len(df)), "columns": list(df.columns), "elapsed_ms": int((time.time() - t0) * 1000),
    }}

    t1 = time.time()
    chunks = chunking.chunk_dataframe(df, text_cols, meta_cols)
    yield {"stage": "build_docs", "status": "done", "detail": {
        "docs": int(len(df)), "text_cols": text_cols, "meta_cols": meta_cols,
        "elapsed_ms": int((time.time() - t1) * 1000),
    }}

    if not chunks:
        yield {"stage": "error", "status": "error", "detail": {"message": "No chunkable text found — check the selected text columns."}}
        return

    t2 = time.time()
    stats = chunking.chunk_stats(chunks)
    samples = []
    for c in chunks[:6]:
        overlap_len = config.CHUNK_OVERLAP if c.chunk_index > 0 else 0
        samples.append({
            "chunk_id": c.chunk_id, "row_index": c.row_index, "chunk_index": c.chunk_index,
            "char_len": c.char_len, "overlap_chars": min(overlap_len, c.char_len),
            "text": c.text[:400],
        })
    yield {"stage": "chunk", "status": "done", "detail": {**stats, "samples": samples, "elapsed_ms": int((time.time() - t2) * 1000)}}

    t3 = time.time()
    dense_all: list[list[float]] = []
    sparse_all: list[tuple[list[int], list[float]]] = []
    total = len(chunks)
    batch_size = config.INGEST_BATCH
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.text for c in batch]
        dense, sparse = embeddings.embed(texts)
        dense_all.extend(dense)
        sparse_all.extend(embeddings.sparse_to_qdrant(s) for s in sparse)
        done = min(i + batch_size, total)
        yield {"stage": "embed", "status": "progress", "detail": {
            "done": done, "total": total,
            "dense_preview": dense[0][:8] if dense else [],
            "sparse_preview": embeddings.top_sparse_tokens(sparse[0]) if sparse else [],
        }}
    yield {"stage": "embed", "status": "done", "detail": {"total": total, "dim": len(dense_all[0]) if dense_all else 0, "elapsed_ms": int((time.time() - t3) * 1000)}}

    t4 = time.time()
    vectorstore.ensure_collection(dim=len(dense_all[0]), recreate=recreate)
    vectorstore.upsert_chunks(chunks, dense_all, sparse_all)
    info = vectorstore.collection_info()
    yield {"stage": "index", "status": "done", "detail": {**info, "elapsed_ms": int((time.time() - t4) * 1000), "total_elapsed_ms": int((time.time() - t0) * 1000)}}


def run_chat(query: str):
    t0 = time.time()

    rewrites = llm.generate_rewrites(query)
    yield {"stage": "rewrite", "status": "done", "detail": {"original": query, "rewrites": rewrites}}

    all_queries = [query] + rewrites
    dense_hits: dict[int, object] = {}
    sparse_hits: dict[int, object] = {}
    for q in all_queries:
        dense, sparse = embeddings.embed([q])
        indices, values = embeddings.sparse_to_qdrant(sparse[0])
        for p in vectorstore.dense_search(dense[0], config.TOP_N_HYBRID):
            if p.id not in dense_hits or p.score > dense_hits[p.id].score:
                dense_hits[p.id] = p
        for p in vectorstore.sparse_search(indices, values, config.TOP_N_HYBRID):
            if p.id not in sparse_hits or p.score > sparse_hits[p.id].score:
                sparse_hits[p.id] = p

    dense_rank = sorted(dense_hits.values(), key=lambda p: p.score, reverse=True)
    sparse_rank = sorted(sparse_hits.values(), key=lambda p: p.score, reverse=True)
    yield {"stage": "hybrid_search", "status": "done", "detail": {
        "dense_top": [_point_preview(p, i + 1) for i, p in enumerate(dense_rank[:10])],
        "sparse_top": [_point_preview(p, i + 1) for i, p in enumerate(sparse_rank[:10])],
    }}

    fused = fusion.rrf_fuse([[p.id for p in dense_rank], [p.id for p in sparse_rank]])
    all_points = {**dense_hits, **sparse_hits}
    fused_points = [all_points[pid] for pid, _score in fused if pid in all_points]
    yield {"stage": "fuse", "status": "done", "detail": {
        "fused_top": [_point_preview(p, i + 1) for i, p in enumerate(fused_points[:10])],
    }}

    if not fused_points:
        yield {"stage": "answer", "status": "error", "detail": {
            "message": "No matching chunks found. Has a collection been ingested yet?",
        }}
        return

    candidates = fused_points[:config.TOP_N_HYBRID]
    texts = [p.payload.get("text", "") for p in candidates]
    scores = reranker.rerank(query, texts)
    reranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    top_k = reranked[:config.TOP_K_RERANK]

    before = [_point_preview(p, i + 1) for i, p in enumerate(candidates)]
    after = [{**_point_preview(p, i + 1), "rerank_score": round(float(score), 4)} for i, (p, score) in enumerate(top_k)]
    yield {"stage": "rerank", "status": "done", "detail": {"before": before, "after": after}}

    mode = "generate" if llm.is_generate_intent(query) else "answer"
    final_chunks = [{"text": p.payload.get("text", ""), "meta": {k: v for k, v in p.payload.items() if k != "text"}} for p, _s in top_k]
    answer_text = llm.answer(query, final_chunks, mode)

    yield {"stage": "answer", "status": "done", "detail": {
        "mode": mode,
        "answer": answer_text,
        "citations": [
            {"chunk_number": i + 1, "id": p.id, "meta": {k: v for k, v in p.payload.items() if k != "text"}, "text_preview": p.payload.get("text", "")[:220]}
            for i, (p, _s) in enumerate(top_k)
        ],
        "total_elapsed_ms": int((time.time() - t0) * 1000),
    }}
