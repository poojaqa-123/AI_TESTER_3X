"""bge-reranker-v2-m3 cross-encoder re-ranking. Lazy-loaded (~570MB)."""

import threading

from . import config

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from FlagEmbedding import FlagReranker

                _model = FlagReranker(config.RERANK_MODEL, use_fp16=config.BGE_USE_FP16)
    return _model


def rerank(query: str, candidates: list[str]) -> list[float]:
    if not candidates:
        return []
    model = get_model()
    pairs = [[query, c] for c in candidates]
    scores = model.compute_score(pairs, normalize=True)
    if isinstance(scores, (int, float)):
        scores = [scores]
    return [float(s) for s in scores]
