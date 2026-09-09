import os

# bge-m3 (~2.3GB) and bge-reranker-v2-m3 (~570MB) are lazy-loaded once per
# process (core/embeddings.py, core/reranker.py) and never unloaded. Running
# multiple gunicorn *worker processes* would load a separate copy of both
# models into memory per worker — expensive on a modest droplet for no
# retrieval-quality benefit, since the actual embed/rerank calls are CPU-bound
# anyway. So: one worker, several threads for request concurrency (SSE chat
# streams and ingestion runs are I/O/CPU-bound, not memory-bound per request).
bind = f"0.0.0.0:{os.getenv('PORT', 8060)}"
workers = 1
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", 4))
timeout = 300  # ingestion/embedding/reranking + SSE streaming can run long
graceful_timeout = 30
