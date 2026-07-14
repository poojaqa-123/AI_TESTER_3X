# Basic RAG Explorer

A React-based demonstration app that ingests a PDF, chunks it, generates Nomic embeddings, stores them in a local ChromaDB collection, and answers questions using Groq (OpenGPT 120B).

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Create a `.env` file with your API keys:
   ```env
   NOMIC_API_KEY=your_nomic_api_key
   GROQ_API_KEY=your_groq_api_key
   ```

3. Start the app:
   ```bash
   npm run dev
   ```

## How it works

- `server.js` reads `data/Product Requirements Document_(PRD)_VWO.com.pdf`.
- It splits the PDF text into overlapping chunks.
- It uses `@langchain/nomic` to generate embeddings.
- It stores the embeddings in a local ChromaDB collection.
- The React frontend calls `/api/ingest` and `/api/query`.
- Query results return the top 4 chunks and generate an answer using `@langchain/groq`.

## Important Notes

- ChromaDB requires the `chromadb` backend. The `chromadb` JS client expects a running Chroma server or a default embedding function.
- If using local development, ensure the server can connect to Chroma. You may need to install and run the Chroma CLI or configure environment variables.
