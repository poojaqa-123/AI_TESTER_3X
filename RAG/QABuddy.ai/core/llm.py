"""LLM calls (query rewriting + grounded generation). Uses the OpenAI-compatible
chat completions API against whichever provider is configured (OpenRouter if
OPENROUTER_API_KEY is set, else Groq). Supports multiple answer "modes" tuned
for QABuddy.ai's QA use cases, each still grounded strictly in retrieved chunks
and citing them inline as [Chunk N]."""

import json
import re

from openai import OpenAI

from . import config

_client = None

REWRITE_SYSTEM = (
    "You rewrite search queries into alternate phrasings to improve retrieval recall "
    "over a QA knowledge base spanning test automation code, test cases, product docs, "
    "meeting notes, and CI logs. Given the user's question, produce exactly {n} alternate "
    "phrasings that preserve the original intent but vary vocabulary and structure. "
    "Respond with ONLY a JSON array of {n} strings — no markdown, no commentary."
)

MODE_SYSTEM_PROMPTS = {
    "answer": (
        "You are QABuddy, a QA knowledge-base assistant for our company's testers. Use ONLY "
        "the provided chunks (which may come from Selenium/Playwright framework code, test "
        "cases, PRDs/company docs, meeting notes, or Jenkins logs) to answer. Do not invent "
        "facts that aren't in the context. Cite the chunks you used inline like [Chunk N]. "
        "If the answer isn't in the provided chunks, say so plainly — this is for onboarding "
        "and day-to-day self-serve Q&A, so be clear and concise."
    ),
    "rca": (
        "You are QABuddy performing test-failure root-cause analysis. Using ONLY the provided "
        "chunks (Jenkins log failure/summary blocks, related test-case definitions, and framework "
        "code), identify: (1) what failed, (2) the likely root cause, (3) whether it looks like a "
        "product bug, a flaky/environmental issue, or a test-script defect, and (4) a suggested "
        "next step. Cite chunks inline like [Chunk N]. If the provided context doesn't contain "
        "enough evidence to determine a cause, say so plainly rather than guessing."
    ),
    "test_design": (
        "You are QABuddy, a QA test-case author. Using the retrieved similar test cases, PRD/"
        "requirement excerpts, and framework code as context, either draft NEW test case(s) or "
        "identify GAPS (missing coverage) for the user's request — infer which from their "
        "question. When drafting, output structured fields: Title, Preconditions, Steps "
        "(numbered), Test Data, Expected Result, Priority, Tags. When identifying gaps, list "
        "each gap with why it isn't covered by the retrieved test cases. Cite chunks inline "
        "like [Chunk N]."
    ),
    "framework_help": (
        "You are QABuddy, an expert on our Selenium and Playwright test-automation frameworks. "
        "Using ONLY the retrieved framework code chunks (and any related test cases/docs) as "
        "ground truth for our actual conventions, answer coding questions, suggest best-practice "
        "fixes, or explain how existing utilities work. Prefer reusing what's already in the "
        "framework over inventing new patterns. Cite chunks inline like [Chunk N], referencing "
        "file paths/line numbers where useful."
    ),
}


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            raise RuntimeError("No LLM API key configured — set GROQ_API_KEY or OPENROUTER_API_KEY in .env")
        _client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


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
    system = MODE_SYSTEM_PROMPTS.get(mode, MODE_SYSTEM_PROMPTS["answer"])
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
