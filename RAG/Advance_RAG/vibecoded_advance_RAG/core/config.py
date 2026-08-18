import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Pipeline tunables (also settable via .env) --------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))
TOP_N_HYBRID = int(os.getenv("TOP_N_HYBRID", 20))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", 4))
RRF_K = int(os.getenv("RRF_K", 60))
REWRITE_ENABLED = os.getenv("REWRITE_ENABLED", "true").lower() in ("1", "true", "yes")
N_REWRITES = 3

# --- Storage ---------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL") or None
QDRANT_PATH = os.getenv("QDRANT_PATH", str(ROOT / "qdrant_data"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "vwo_test_cases")
UPLOAD_DIR = ROOT / "uploads"

# --- Models ------------------------------------------------------------
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
    # deepseek models have been decommissioned on Groq; gpt-oss-120b is the
    # current largest/most capable model available there.
    GEN_MODEL = os.getenv("GEN_MODEL", "openai/gpt-oss-120b")
    REWRITE_MODEL = os.getenv("REWRITE_MODEL", "llama-3.1-8b-instant")
else:
    LLM_PROVIDER = None
    LLM_BASE_URL = None
    LLM_API_KEY = None
    GEN_MODEL = None
    REWRITE_MODEL = None

PORT = int(os.getenv("PORT", 5050))
