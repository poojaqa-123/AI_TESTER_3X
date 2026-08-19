import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Per-source-type chunking (chars; ~4 chars/token) ----------------------
# (chunk_size, overlap) pairs. `log` chunks are sized per failure-block instead
# (see core/chunking/log_chunker.py) — its entry here is only a fallback cap.
CHUNK_PROFILES = {
    "code": (int(os.getenv("CHUNK_SIZE_CODE", 1800)), int(os.getenv("CHUNK_OVERLAP_CODE", 250))),
    "test_case": (int(os.getenv("CHUNK_SIZE_TEST_CASE", 1000)), int(os.getenv("CHUNK_OVERLAP_TEST_CASE", 150))),
    "doc": (int(os.getenv("CHUNK_SIZE_DOC", 900)), int(os.getenv("CHUNK_OVERLAP_DOC", 150))),
    "transcript": (int(os.getenv("CHUNK_SIZE_TRANSCRIPT", 800)), int(os.getenv("CHUNK_OVERLAP_TRANSCRIPT", 150))),
    "chart": (int(os.getenv("CHUNK_SIZE_CHART", 900)), int(os.getenv("CHUNK_OVERLAP_CHART", 150))),
    "log": (int(os.getenv("CHUNK_SIZE_LOG", 1500)), int(os.getenv("CHUNK_OVERLAP_LOG", 0))),
}

TOP_N_HYBRID = int(os.getenv("TOP_N_HYBRID", 20))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", 4))
RRF_K = int(os.getenv("RRF_K", 60))
REWRITE_ENABLED = os.getenv("REWRITE_ENABLED", "true").lower() in ("1", "true", "yes")
N_REWRITES = 3

# --- Storage -----------------------------------------------------------
# Standalone Qdrant (Docker service) is the default for QABuddy — embedded
# mode's file lock only allows one process, which breaks under gunicorn's
# multiple worker processes in a 24x7 deployment. Set QDRANT_PATH instead of
# QDRANT_URL only for local single-process experimentation.
QDRANT_URL = os.getenv("QDRANT_URL") or "http://localhost:6333"
QDRANT_PATH = os.getenv("QDRANT_PATH") or None
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "qabuddy_kb")

DATA_SOURCES_DIR = ROOT / "data_sources"
UPLOAD_DIR = ROOT / "uploads"

SOURCE_FOLDERS = {
    "01_selenium_framework": "code",
    "02_playwright_framework": "code",
    "03_test_cases": "test_case",
    "05_company_docs": "doc",
    "07_meeting_notes": "transcript",
    "08_lucid_charts": "chart",
    "09_prd_srs_brd_frd": "doc",
    "10_jenkins_logs": "log",
}
# 04_jira_tickets and 06_figma_designs are intentionally excluded — Phase 2.

# --- Models --------------------------------------------------------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
BGE_USE_FP16 = os.getenv("BGE_USE_FP16", "1") in ("1", "true", "True")
INGEST_BATCH = int(os.getenv("INGEST_BATCH", 16))

# --- LLM provider: OpenRouter takes priority if configured, else Groq ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or None
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or None

if OPENROUTER_API_KEY:
    LLM_PROVIDER = "openrouter"
    LLM_BASE_URL = "https://openrouter.ai/api/v1"
    LLM_API_KEY = OPENROUTER_API_KEY
    GEN_MODEL = os.getenv("GEN_MODEL", "deepseek/deepseek-chat")
    REWRITE_MODEL = os.getenv("REWRITE_MODEL", "meta-llama/llama-3.1-8b-instruct")
elif GROQ_API_KEY:
    LLM_PROVIDER = "groq"
    LLM_BASE_URL = "https://api.groq.com/openai/v1"
    LLM_API_KEY = GROQ_API_KEY
    GEN_MODEL = os.getenv("GEN_MODEL", "openai/gpt-oss-120b")
    REWRITE_MODEL = os.getenv("REWRITE_MODEL", "llama-3.1-8b-instant")
else:
    LLM_PROVIDER = None
    LLM_BASE_URL = None
    LLM_API_KEY = None
    GEN_MODEL = None
    REWRITE_MODEL = None

# 5060/5061 are on Chrome's (and other browsers') hardcoded unsafe-ports list
# (reserved for SIP) — pick anything else, 8060 is arbitrary but safe.
PORT = int(os.getenv("PORT", 8060))
