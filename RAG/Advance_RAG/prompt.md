# Advanced RAG Explorer


Create the 5,00 VWO : https://app.vwo.com/#/login test cases in the /testcase folder for the Advance RAG as a CSV file with jira format. 


Generate the full Advance RAG application + RAG explorer,

here are the detais

You need to also create an HTML file with the proper animation and diagrams explaining the concepts with the RAG: how we have created it, what the components are, and everything we have done. It's like a README, but in an HTML format that I can upload somewhere to explain the concept of how I have created this advanced RAG through the vibe coding. 



End-to-end teaching demo for The Testing Academy. Upgrades `Basic_RAG_EXPLAIN`
with techniques that matter at scale on a real corpus (5,000 VWO test cases):

- **Hybrid retrieval** — `bge-m3` produces dense + sparse vectors from one model
- **Vector DB** — Qdrant (local Docker) with native dense + sparse + filters
- **Re-ranking** — `BAAI/bge-reranker-v2-m3` cross-encoder
- **Query rewriting** — alternate phrasings via Openrouter before retrieval
- **Generation** — Openrouter `deepseek v4 pro` (same as Basic)

UI uses a Claude-inspired theme (warm cream + coral) with a two-pane layout:
left = pipeline stage tracker (live), right = active content / chat.

---

## Pipeline

```
Stage 1 (Ingest):
  CSV/XLSX -> rows -> assemble docs -> chunk (1 row = 1 chunk if small) ->
  bge-m3 (dense + sparse) -> Qdrant collection 'vwo_test_cases'

Stage 2 (Chat):
  Question -> rewrite (Openrouter) -> embed -> dense + sparse search ->
  RRF fuse -> bge-reranker-v2-m3 -> Openrouter -> grounded answer
```

---

## Setup

```bash
cd RAG/Advance_RAG/vibecoded_advance_RAG
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Qdrant runs **embedded** by default (file store at `./qdrant_data/`) — **no Docker
required**. To use a Qdrant server instead, set `QDRANT_URL=http://host:6333`
in `.env`.

`.env` is pre-populated with the same `GROQ_API_KEY` as Basic.

---

## Run

```bash
source .venv/bin/activate
python app.py
# open http://127.0.0.1:5050
```

The first request hits cold model loaders (bge-m3 ~2.3 GB, bge-reranker ~570 MB
first time from HF cache) — subsequent requests are fast.

### CLI ingestion (optional)

```bash
python ingest.py data/test_cases.csv \
  --text-cols title,steps,expected,tags \
  --meta-cols id,jira_id,priority,module
```

---

## What you can see in the UI

### `/upload`
- File picker accepts `.csv`, `.xlsx`, `.xls`.
- After upload: row count, columns, first 5 rows, dtypes.
- Pick text columns (concatenated into the embedded document) and metadata
  columns (kept in Qdrant payload for filtering).

### `/ingest` (live SSE)
- Stage tracker shows: Read -> Build docs -> Chunk -> Embed -> Index.
- For each stage, a card on the right shows what happened:
  - **Chunk**: histogram, total chunks, avg/min/max chars, sample chunks with
    overlap highlighted in coral.
  - **Embed**: progress bar, dense vector preview (first 8 dims), sparse top-5
    tokens by weight.
  - **Index**: Qdrant collection info, link to dashboard.

### `/chunks`
- Paginated viewer (50/page) over the entire collection.
- Search box (substring) + filters (`priority`, `module`, `jira_id`).
- Each chunk card: ids, payload, dense preview, sparse preview, full text.
- Chunks used in the most recent chat answer are outlined in coral.

### `/chat`
- Chat box on the right; pipeline stage tracker on the left updates per query.
- After each turn the assistant shows:
  - The 3 query rewrites
  - Dense top-N vs sparse top-N vs RRF-fused top-N
  - Re-rank before/after table
  - Final answer with `[Chunk N]` citations
- Two modes auto-detected:
  - **Answer**: grounded Q&A on test cases.
  - **Generate**: types like "create a new test case for JIRA VWO-1234" produce
    a structured test case (Title / Preconditions / Steps / Expected / Priority
    / Tags) using retrieved similar test cases as templates.

---

## Tunables (top of `app.py`)

| Knob               | Default | Meaning                                          |
|--------------------|---------|--------------------------------------------------|
| `CHUNK_SIZE`       | 1000    | Max chars per chunk before splitting             |
| `CHUNK_OVERLAP`    | 150     | Chars repeated between adjacent chunks           |
| `TOP_N_HYBRID`     | 20      | Candidates per dense / sparse search             |
| `TOP_K_RERANK`     | 4       | Final chunks sent to LLM after rerank            |
| `RRF_K`            | 60      | Reciprocal Rank Fusion smoothing constant        |
| `REWRITE_ENABLED`  | True    | Use Groq to generate alt phrasings before search |

---

## Troubleshooting

- **Connection refused on 6333** — only relevant if you set `QDRANT_URL` to a server. Default is embedded; nothing to start.
- **Groq 401** — `.env` is missing or `GROQ_API_KEY` is wrong.
- **First query is slow** — bge-m3 + reranker downloading + warming. Subsequent calls are sub-second.
- **Out-of-memory on bge-m3** — set `BGE_USE_FP16=1` (default) and reduce `INGEST_BATCH=16`.
- **Port 5050 busy** — change `PORT` env var.