"""LLM calls (query rewriting + grounded generation). Uses the OpenAI-compatible
chat completions API against whichever provider is configured (OpenRouter if
OPENROUTER_API_KEY is set, else Groq)."""

import json
import re

from openai import OpenAI

from . import config

_client = None

GENERATE_TRIGGERS = [
    "create a new test case", "create test case", "write a test case",
    "generate a test case", "draft a test case", "new test case for",
    "add a test case",
]

REWRITE_SYSTEM = (
    "You rewrite search queries into alternate phrasings to improve retrieval recall "
    "over a QA test-case knowledge base (VWO test cases). Given the user's question, "
    "produce exactly {n} alternate phrasings that preserve the original intent but vary "
    "vocabulary and structure. Respond with ONLY a JSON array of {n} strings — no markdown, "
    "no commentary."
)

ANSWER_SYSTEM = (
    "You are a QA assistant answering questions about a test-case knowledge base "
    "(VWO test cases exported from Jira). Use ONLY the provided chunks to answer — do not "
    "invent test cases that aren't in the context. Cite the chunks you used inline like "
    "[Chunk N]. If the answer isn't in the provided chunks, say so plainly."
)

GENERATE_SYSTEM = (
    "You are a QA test-case author. Using the retrieved similar test cases as style/structure "
    "templates, draft a NEW test case for the user's request. Output a structured test case with "
    "these fields: Title, Preconditions, Steps (numbered), Test Data, Expected Result, Priority, "
    "Tags. Cite which retrieved chunks inspired the draft like [Chunk N]."
)


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            raise RuntimeError("No LLM API key configured — set GROQ_API_KEY or OPENROUTER_API_KEY in .env")
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


def is_generate_intent(query: str) -> bool:
    q = query.lower()
    return any(t in q for t in GENERATE_TRIGGERS)


def generate_rewrites(query: str, n: int = None) -> list[str]:
    n = n or config.N_REWRITES
    if not config.REWRITE_ENABLED or not config.LLM_API_KEY:
        return []
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=config.REWRITE_MODEL,
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM.format(n=n)},
                {"role": "user", "content": query},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        content = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", content, re.DOTALL)
        raw = match.group(0) if match else content
        rewrites = json.loads(raw)
        return [str(r).strip() for r in rewrites if str(r).strip()][:n]
    except Exception:
        return []


def answer(query: str, chunks: list[dict], mode: str = "answer") -> str:
    client = get_client()
    context = "\n\n".join(f"[Chunk {i + 1}] {c['text']}" for i, c in enumerate(chunks))
    system = GENERATE_SYSTEM if mode == "generate" else ANSWER_SYSTEM
    resp = client.chat.completions.create(
        model=config.GEN_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Context chunks:\n\n{context}\n\nQuestion: {query}"},
        ],
        temperature=0.3,
        max_tokens=1400,
    )
    return resp.choices[0].message.content
