"""bge-m3 hybrid (dense + sparse) embeddings. Model loads lazily on first use
so app startup doesn't block on the ~2.3GB HF download/warm-up.
"""

import threading

from . import config

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from FlagEmbedding import BGEM3FlagModel

                _model = BGEM3FlagModel(config.EMBED_MODEL, use_fp16=config.BGE_USE_FP16)
    return _model


def embed(texts: list[str], batch_size: int = None):
    """Returns (dense_vecs: list[list[float]], sparse_weights: list[dict[str,float]])."""
    model = get_model()
    batch_size = batch_size or config.INGEST_BATCH
    out = model.encode(
        texts,
        batch_size=batch_size,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense = [[float(x) for x in vec] for vec in out["dense_vecs"]]
    sparse = out["lexical_weights"]
    return dense, sparse


def sparse_to_qdrant(sparse_weights: dict) -> tuple[list[int], list[float]]:
    indices = [int(k) for k in sparse_weights.keys()]
    values = [float(v) for v in sparse_weights.values()]
    return indices, values


def top_sparse_tokens(sparse_weights: dict, top_n: int = 5) -> list[dict]:
    ranked = sorted(sparse_weights.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    model = get_model()
    result = []
    for token_id, weight in ranked:
        try:
            token = model.tokenizer.decode([int(token_id)]).strip()
        except Exception:
            token = str(token_id)
        result.append({"token": token or str(token_id), "weight": round(float(weight), 4)})
    return result
