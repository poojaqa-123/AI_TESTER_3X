# Prompt: Build a Vibe-Coded RAG Knowledge Base & QA Assistant

You are a **15+ year Senior AI/RAG Architect, Backend Engineer, Frontend Engineer, and QA Automation Architect**.

I want you to design and build a **production-quality RAG (Retrieval-Augmented Generation) application** for a QA/engineering knowledge base.

The goal is to build a simple but extensible RAG system where I can upload engineering artifacts, ingest them into a knowledge base, retrieve relevant chunks, and ask questions through a chat interface.

Do not blindly follow my technology choices. Where there are better modern open-source alternatives, recommend them and explain the trade-offs before implementation.

---

# 1. Overall Goal

Build a RAG application with these major capabilities:

```text
                    ┌─────────────────────┐
                    │      Frontend       │
                    │  Claude-like UI     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      RAG API        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         Query Rewrite      Retriever         LLM
              │                │                │
              │                ▼                │
              │          Vector Database       │
              │                │                │
              │                ▼                │
              │          Top-K Chunks           │
              │                │                │
              └────────────────┴────────────────┘
                               │
                               ▼
                         Final Answer
```

The application should make the entire RAG pipeline observable to the user.

---

# 2. Phase 1 — Data Ingestion

The system should support ingestion of the following sources:

### Documents

* PRD files
* PDF
* DOCX
* TXT
* Markdown

### Structured data

* CSV
* JSON

### Engineering / QA sources

* JIRA tickets
* Selenium repository
* Playwright repository
* Java/Python/JavaScript/TypeScript source code
* Test cases
* API specifications
* README files
* Configuration files

Design the ingestion layer so additional sources can easily be added later.

Use a common document model such as:

```json
{
  "document_id": "...",
  "source_type": "jira|prd|csv|code|pdf|etc",
  "source_name": "...",
  "file_path": "...",
  "content": "...",
  "metadata": {},
  "created_at": "...",
  "updated_at": "..."
}
```

---

# 3. Document Processing Pipeline

Implement the following pipeline:

```text
Upload
  ↓
File Validation
  ↓
Document Parsing
  ↓
Text Extraction
  ↓
Cleaning / Normalization
  ↓
Metadata Extraction
  ↓
Chunking
  ↓
Embedding
  ↓
Vector Storage
  ↓
Indexing
```

Every stage should expose useful metrics.

For example:

```text
Document: login_prd.pdf

Pages: 12
Characters extracted: 38,421
Chunks created: 87
Average chunk size: 441 tokens
Embedding model: BGE
Embeddings generated: 87
Vector DB: Qdrant
Status: SUCCESS
```

---

# 4. Embedding Model

I initially considered **BGE**.

Evaluate modern embedding models and recommend the best option for this project.

Compare at least:

* BGE
* BGE-M3
* multilingual BGE
* modern open-source embedding alternatives

Consider:

* Retrieval quality
* Code retrieval
* Technical documentation retrieval
* Multilingual support
* Local execution
* CPU/GPU requirements
* Embedding dimensions
* Speed
* Licensing
* Ease of deployment

For the first implementation, prefer an **open-source model that can run locally**.

Explain your recommendation before implementing it.

---

# 5. Vector Database

I am considering:

### Qdrant

Open-source and can run locally using Docker.

### Pinecone

Managed/paid.

Evaluate both.

For the initial MVP, prefer **Qdrant** because I want the project to be inexpensive and locally runnable.

However, design the vector storage layer behind an abstraction such as:

```text
VectorStore
    ├── QdrantVectorStore
    └── PineconeVectorStore
```

This should allow switching vector databases later without rewriting the RAG pipeline.

---

# 6. Chunking Strategy

Do not simply use a fixed character count.

Design an appropriate chunking strategy based on the source.

For example:

### PRD / Documentation

Use semantic/paragraph-aware chunking.

### Code

Prefer structure-aware chunking:

```text
Class
  ↓
Method
  ↓
Method body
```

Preserve:

* file path
* class name
* method name
* language
* repository
* branch
* line numbers where possible

### JIRA

Preserve:

* ticket ID
* title
* description
* acceptance criteria
* comments
* status
* priority
* labels

### CSV

Determine whether rows, groups of rows, or logical records should be embedded.

Create a configurable chunking system.

Allow configuration such as:

```yaml
chunking:
  strategy: semantic
  chunk_size: 500
  chunk_overlap: 75
```

Explain why the selected defaults are appropriate.

---

# 7. Metadata

Every chunk must contain useful metadata.

Example:

```json
{
  "document_id": "DOC-123",
  "chunk_id": "DOC-123-42",
  "source_type": "jira",
  "source_name": "PROJ-123",
  "file_name": "PROJ-123",
  "repository": null,
  "file_path": null,
  "language": null,
  "page_number": null,
  "chunk_index": 42,
  "created_at": "...",
  "updated_at": "..."
}
```

Metadata should be used for filtering during retrieval.

---

# 8. Collection Design

Design the Qdrant collection carefully.

Document:

* collection name
* vector dimensions
* distance metric
* payload structure
* indexes
* metadata filters

Example conceptual structure:

```text
Collection: engineering_knowledge

Vector
  └── embedding

Payload
  ├── document_id
  ├── chunk_id
  ├── source_type
  ├── source_name
  ├── file_path
  ├── repository
  ├── language
  ├── content
  └── metadata
```

Explain why the selected distance metric is appropriate.

---

# 9. Ranker / Reranking

Implement a two-stage retrieval pipeline:

```text
User Query
    ↓
Embedding
    ↓
Vector Search
    ↓
Top 20 chunks
    ↓
Reranker
    ↓
Top 5 chunks
    ↓
LLM
```

Evaluate whether a reranker should be used.

Possible approaches:

* Cross-encoder reranker
* BGE reranker
* Lightweight reranking
* No reranking for very small datasets

For the MVP, select a practical open-source reranker.

Expose:

```text
Initial retrieved chunks: 20
Reranked chunks: 5
```

---

# 10. Retrieval

When a user asks a question:

```text
Question
   ↓
Query preprocessing
   ↓
Query embedding
   ↓
Vector retrieval
   ↓
Metadata filtering
   ↓
Reranking
   ↓
Top 5 chunks
   ↓
LLM
   ↓
Answer
```

The UI must show the retrieved chunks.

For every chunk display:

```text
Rank: #1
Score: 0.91

Source:
jira/PROJ-123

Content:
...

Metadata:
...
```

---

# 11. RAG Pipeline Visualization

This is an important requirement.

The UI should visually show the pipeline:

```text
User Question
      ↓
Query Processing
      ↓
Embedding
      ↓
Vector Search
      ↓
Retrieved 20 Chunks
      ↓
Reranking
      ↓
Top 5 Chunks
      ↓
LLM
      ↓
Final Answer
```

Each stage should display execution information.

Example:

```text
Embedding
✓ Completed
Model: BGE-M3
Time: 182 ms

Vector Search
✓ Completed
Candidates: 20
Time: 34 ms

Reranker
✓ Completed
Input: 20
Output: 5
Time: 241 ms

LLM
✓ Completed
Model: ...
Time: 1.8 sec
```

---

# 12. Frontend

Build a modern UI inspired by the clean/creamy style of Claude Code.

Do NOT clone Claude's UI exactly.

Use a clean AI developer-tool aesthetic.

The application should have the following main sections:

```text
┌─────────────────────────────────────────────┐
│ RAG Knowledge Assistant                     │
├───────────────┬─────────────────────────────┤
│               │                             │
│ Knowledge     │          Chat               │
│ Base          │                             │
│               │                             │
│ Upload        │                             │
│ Ingest        │                             │
│ Documents     │                             │
│ Chunks        │                             │
│ Retrieval     │                             │
│ Pipeline      │                             │
│               │                             │
└───────────────┴─────────────────────────────┘
```

---

# 13. Required UI Sections

## Dashboard

Show:

```text
Documents: 142
Chunks: 8,921
Vectors: 8,921
Sources:
  PRD: 32
  JIRA: 51
  Code: 45
  CSV: 14
```

---

## Upload

Allow users to:

* Upload files
* Drag and drop
* Select source type
* Add metadata
* Upload multiple files

Show upload status.

---

## Ingestion

Show:

```text
File
 ↓
Parsing
 ↓
Cleaning
 ↓
Chunking
 ↓
Embedding
 ↓
Vector DB
```

Display progress and errors.

---

# 14. Knowledge Base Explorer

Create a simple knowledge-base browser.

Example:

```text
Knowledge Base

├── PRD
│   ├── login.md
│   ├── interview.md
│   └── payments.md
│
├── JIRA
│   ├── AUTH-123
│   ├── INT-456
│   └── PAY-789
│
├── Selenium
│   ├── tests/
│   ├── pages/
│   └── utils/
│
└── Playwright
    ├── tests/
    ├── pages/
    └── fixtures/
```

Users should be able to click a document and inspect:

* Metadata
* Extracted text
* Number of chunks
* Individual chunks
* Embedding status
* Ingestion timestamp

---

# 15. Chat

Create a ChatGPT/Claude-like chat interface.

User can ask:

```text
Why does the login API return 403?

Which JIRA tickets are related to login failures?

Show me the existing Playwright tests for login.

What does the PRD say about authentication?

Which API endpoints are covered by automation?
```

The answer should include citations to the retrieved knowledge.

Example:

```text
The login endpoint returns 403 when the user does not
have the required enterprise access.

Sources:
[1] JIRA: AUTH-123
[2] PRD: authentication.md
[3] Playwright: tests/login.spec.ts
```

---

# 16. Top 5 Retrieved Chunks

The UI MUST always provide an expandable section:

```text
Retrieved Context

▼ #1 — Score 0.94
   Source: AUTH-123

▼ #2 — Score 0.91
   Source: authentication.md

▼ #3 — Score 0.87
   Source: login.spec.ts

▼ #4 — Score 0.84
   Source: AUTH-456

▼ #5 — Score 0.81
   Source: auth_service.py
```

Users should be able to inspect the actual chunk content.

---

# 17. RAG Debug Mode

Add a **Debug RAG** toggle.

When enabled, show:

```text
Query
↓
Normalized Query
↓
Embedding
↓
Vector Search
↓
Candidate Chunks
↓
Reranker
↓
Top 5
↓
Prompt sent to LLM
↓
LLM response
```

This is especially important because this application is intended as a learning and debugging tool.

---

# 18. Backend

Build a clean backend architecture.

Suggested structure:

```text
backend/
├── api/
├── ingestion/
│   ├── loaders/
│   ├── parsers/
│   ├── chunking/
│   └── embeddings/
├── retrieval/
│   ├── retriever.py
│   ├── reranker.py
│   └── filters.py
├── vectorstore/
│   ├── base.py
│   └── qdrant.py
├── llm/
├── models/
├── services/
├── config/
└── tests/
```

Keep components loosely coupled.

---

# 19. API Endpoints

Create APIs similar to:

```text
POST   /documents/upload
POST   /documents/ingest
GET    /documents
GET    /documents/{id}
GET    /documents/{id}/chunks

POST   /query
POST   /chat

GET    /retrieval/{query_id}
GET    /pipeline/{query_id}

GET    /knowledge-base
DELETE /documents/{id}
```

Use proper request/response models.

---

# 20. LLM

Make the LLM provider configurable.

Do not hard-code one provider.

Use an abstraction:

```text
LLMProvider
   ├── AnthropicProvider
   ├── OpenAIProvider
   └── LocalProvider
```

Configuration should allow changing the model without changing application code.

---

# 21. Configuration

Use environment variables:

```env
LLM_PROVIDER=
LLM_MODEL=

EMBEDDING_MODEL=

QDRANT_URL=
QDRANT_COLLECTION=

RERANKER_MODEL=
```

Never hard-code API keys.

Provide:

```text
.env.example
```

---

# 22. Docker

The entire application should be runnable locally.

Provide Docker Compose for:

```text
Frontend
Backend
Qdrant
```

Example:

```text
docker compose up
```

should start the complete application.

---

# 23. Testing

Because this is a QA-focused application, include automated tests.

### Unit Tests

Test:

* chunking
* metadata extraction
* embeddings
* retrieval
* reranking
* document parsing

### API Tests

Test:

```text
/upload
/ingest
/query
/chat
/documents
```

### E2E Tests

Test:

```text
Upload document
      ↓
Ingest
      ↓
Chunks created
      ↓
Embeddings generated
      ↓
Vector stored
      ↓
Ask question
      ↓
Retrieve chunks
      ↓
Generate answer
      ↓
Display citations
```

Use a clean test framework and explain the test architecture.

---

# 24. Observability

Track:

* ingestion time
* chunk count
* embedding latency
* retrieval latency
* reranking latency
* LLM latency
* token usage
* number of retrieved chunks
* top-K scores
* errors

Make these available in the UI.

---

# 25. Error Handling

Handle gracefully:

* Unsupported file
* Corrupt file
* Empty document
* Embedding failure
* Qdrant unavailable
* LLM unavailable
* Timeout
* Invalid API key
* Duplicate document
* Failed ingestion

Do not expose secrets or internal stack traces to users.

---

# 26. Important Architecture Decisions

Before writing code, provide a short architecture proposal containing:

1. Recommended embedding model
2. Recommended vector database
3. Recommended reranker
4. Chunking strategy
5. Recommended LLM
6. Backend framework
7. Frontend framework
8. Storage strategy
9. Metadata schema
10. Qdrant collection design
11. Folder structure
12. Docker architecture
13. Testing strategy

Explain the reasoning and trade-offs.

---

# 27. Preferred MVP Stack

Unless you identify a strong reason otherwise, evaluate this stack:

```text
Frontend:
React + TypeScript

Backend:
Python + FastAPI

Vector DB:
Qdrant

Embedding:
BGE-M3 or best current open-source alternative

Reranker:
BGE reranker or best practical open-source alternative

LLM:
Provider abstraction supporting Claude/OpenAI/local models

Containerization:
Docker Compose

Testing:
Pytest + API/E2E testing
```

Keep the architecture modular so components can be replaced later.

---

# 28. Development Approach

Do NOT attempt to build everything at once.

Implement in phases.

### Phase 1

Build:

```text
Upload
 ↓
Parse
 ↓
Chunk
 ↓
Embed
 ↓
Qdrant
```

### Phase 2

Build:

```text
Query
 ↓
Retrieve
 ↓
Rerank
 ↓
LLM
```

### Phase 3

Build:

```text
Chat UI
```

### Phase 4

Build:

```text
RAG Pipeline Visualization
```

### Phase 5

Build:

```text
Knowledge Base Explorer
```

### Phase 6

Add:

```text
JIRA ingestion
Git repository ingestion
```

### Phase 7

Add:

```text
Testing
Observability
Docker
Performance optimization
```

---

# 29. Important Rules for Implementation

Before modifying or creating files:

1. Inspect the existing project structure.
2. Do not unnecessarily rewrite existing code.
3. Follow existing coding conventions.
4. Keep modules small and maintainable.
5. Add type hints.
6. Add meaningful error handling.
7. Add tests alongside functionality.
8. Never hard-code secrets.
9. Use environment variables for configuration.
10. Document important architecture decisions.

When you finish each phase:

* Run tests.
* Run linting/type checks where applicable.
* Verify the application actually works.
* Report what was implemented.
* Report files created/modified.
* Report known limitations.
* Suggest the next phase.

---

# 30. Start Here

Do NOT start coding immediately.

First:

1. Analyze this requirement.
2. Identify missing requirements.
3. Propose the architecture.
4. Recommend the embedding model.
5. Recommend the vector database.
6. Recommend the reranker.
7. Recommend the LLM strategy.
8. Recommend the chunking strategy.
9. Show the complete project folder structure.
10. Explain the data flow.
11. Explain the Qdrant collection schema.
12. Explain the API design.
13. Explain the UI design.
14. Explain the testing strategy.

Then wait for approval before implementing Phase 1.

The goal is not just to build a basic chatbot. The goal is to build a **transparent RAG engineering/QA knowledge platform where users can see, understand, debug, and evaluate every stage of the RAG pipeline.**
