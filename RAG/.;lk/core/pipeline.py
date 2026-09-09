"""Orchestrates the two flows:

Ingest (per source folder):
  adapter-produced Chunks -> bge-m3 (dense+sparse) -> Qdrant (source_name's old
  points replaced so re-ingesting a source doesn't leave orphaned chunks)

Chat:
  Question -> rewrite -> embed -> dense+sparse search (optionally filtered by
  source_type) -> RRF fuse -> rerank -> mode-specific LLM answer with citations
"""

import time

from ingestion.base import Chunk

from . import citations, config, embeddings, fusion, llm, reranker, vectorstore


def _point_preview(point, rank: int = None) -> dict:
    payload = dict(point.payload or {})
    text = payload.pop("text", "")
    return {
        "id": point.id,
        "rank": rank,
        "score": round(float(point.score), 4) if getattr(point, "score", None) is not None else None,
        "text_preview": text[:220],
        "citation": citations.format_citation({**payload, "source_type": payload.get("source_type")}),
        "meta": payload,
    }


def run_ingest_chunks(chunks: list[Chunk], source_name: str):
    t0 = time.time()
    yield {"stage": "read", "status": "done", "detail": {"chunks_found": len(chunks), "elapsed_ms": 0}}

    if not chunks:
        yield {"stage": "error", "status": "error", "detail": {"message": "No chunkable content found in this source."}}
        return

    lengths = [c.char_len for c in chunks]
    yield {"stage": "chunk", "status": "done", "detail": {
        "total": len(chunks),
        "avg_chars": round(sum(lengths) / len(lengths), 1),
        "min_chars": min(lengths), "max_chars": max(lengths),
        "samples": [{"chunk_id": c.chunk_id, "char_len": c.char_len, "text": c.text[:400]} for c in chunks[:6]],
    }}

    t1 = time.time()
    dense_all, sparse_all = [], []
    total = len(chunks)
    batch_size = config.INGEST_BATCH
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.text for c in batch]
        dense, sparse = embeddings.embed(texts)
        dense_all.extend(dense)
        sparse_all.extend(embeddings.sparse_to_qdrant(s) for s in sparse)
        done = min(i + batch_size, total)
        yield {"stage": "embed", "status": "progress", "detail": {"done": done, "total": total}}
    yield {"stage": "embed", "status": "done", "detail": {
        "total": total, "dim": len(dense_all[0]) if dense_all else 0, "elapsed_ms": int((time.time() - t1) * 1000),
    }}

    t2 = time.time()
    vectorstore.ensure_collection(dim=len(dense_all[0]))
    vectorstore.delete_by_source_name(source_name)  # clean re-ingest: drop this source's old points first
    vectorstore.upsert_chunks(chunks, dense_all, sparse_all)
    info = vectorstore.collection_info()
    yield {"stage": "index", "status": "done", "detail": {
        **info, "elapsed_ms": int((time.time() - t2) * 1000), "total_elapsed_ms": int((time.time() - t0) * 1000),
    }}


def run_chat(query: str, mode: str = "answer", source_types: list[str] | None = None):
    t0 = time.time()

    rewrites = llm.generate_rewrites(query)
    yield {"stage": "rewrite", "status": "done", "detail": {"original": query, "rewrites": rewrites}}

    all_queries = [query] + rewrites
    dense_hits: dict = {}
    sparse_hits: dict = {}
    for q in all_queries:
        dense, sparse = embeddings.embed([q])
        indices, values = embeddings.sparse_to_qdrant(sparse[0])
        for p in vectorstore.dense_search(dense[0], config.TOP_N_HYBRID, source_types):
            if p.id not in dense_hits or p.score > dense_hits[p.id].score:
                dense_hits[p.id] = p
        for p in vectorstore.sparse_search(indices, values, config.TOP_N_HYBRID, source_types):
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
            "message": "No matching chunks found. Has anything been ingested yet?",
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

    final_chunks = [{"text": p.payload.get("text", ""), "meta": {k: v for k, v in p.payload.items() if k != "text"}} for p, _s in top_k]
    answer_text = llm.answer(query, final_chunks, mode)

    yield {"stage": "answer", "status": "done", "detail": {
        "mode": mode,
        "answer": answer_text,
        "citations": [
            {
                "chunk_number": i + 1, "id": p.id,
                "citation": citations.format_citation(p.payload or {}),
                "source_type": p.payload.get("source_type"),
                "meta": {k: v for k, v in p.payload.items() if k != "text"},
                "text_preview": p.payload.get("text", "")[:220],
            }
            for i, (p, _s) in enumerate(top_k)
        ],
        "total_elapsed_ms": int((time.time() - t0) * 1000),
    }}
