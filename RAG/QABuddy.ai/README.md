# QABuddy.ai

Self-hosted hybrid RAG assistant for QA engineers — grounded, cited answers over
Selenium/Playwright framework code, test cases, company docs, PRD/SRS/BRD/FRD,
meeting notes, Lucid charts, and Jenkins logs. Built per `prompt.md`.

**Phase 1 (this build):** all of the above, fully self-serve through the app's
**Sources** tab.
**Phase 2 (deferred, not built here):** JIRA ticket ingestion (`ingestion/jira_tickets.py`
is a stub — see `data_sources/04_jira_tickets/README.md`), Figma design ingestion,
hourly auto-reingestion, and live deployment to a real droplet.

## Architecture

- **Embeddings:** `BAAI/bge-m3` — one pass yields both dense and sparse vectors, so
  hybrid retrieval needs no separate BM25/SPLADE service.
- **Reranker:** `BAAI/bge-reranker-v2-m3` cross-encoder.
- **Vector DB:** Qdrant, run as a standalone Docker service (not embedded) so
  the app can run behind multiple request threads safely.
- **LLM:** Groq or OpenRouter (OpenAI-compatible), whichever API key is set —
  see `core/llm.py`.
- **Retrieval pipeline:** rewrite → dense+sparse search → RRF fuse → cross-encoder
  rerank → mode-specific grounded answer with per-source-type citations
  (`core/pipeline.py`, `core/citations.py`).

See `prompt.md` for the full spec and `deploy/DEPLOY.md` for the production
deployment runbook.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# start Qdrant (or point QDRANT_URL at an existing one)
docker run -p 6333:6333 -v $PWD/qdrant_data:/qdrant/storage qdrant/qdrant:v1.11.0

cp .env.example .env   # set GROQ_API_KEY or OPENROUTER_API_KEY
python app.py          # http://127.0.0.1:8060
```

## Adding data

Drop files into the relevant `data_sources/<NN_name>/` folder (see each
folder's README), then click **Ingest** in the **Sources** tab — or use the
matching CLI documented in that README. Test cases (CSV/XLSX) go through an
upload+column-picker flow in the same tab since embeddable vs. filterable
columns need a human decision.

## Chat modes

- **Answer** — general Q&A / onboarding self-serve.
- **RCA** — test-failure root-cause analysis over Jenkins logs + related tests/code.
- **Test design** — draft new test cases or surface coverage gaps.
- **Framework help** — Selenium/Playwright coding questions grounded in the actual framework code.

Use the **Search only** chips to restrict retrieval to specific source types.
