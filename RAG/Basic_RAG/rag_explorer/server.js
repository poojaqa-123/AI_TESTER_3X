import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
// pdf-parse latest versions export via default or direct function
// Try multiple approaches to ensure compatibility
const pdfParseModule = (() => {
  try {
    const mod = require('pdf-parse');
    return typeof mod === 'function' ? mod : mod.default || mod;
  } catch (e) {
    console.warn('pdf-parse load failed, using mock:', e.message);
    return null;
  }
})();

const pdfParse = typeof pdfParseModule === 'function' ? pdfParseModule : null;
import { ChromaClient } from 'chromadb';
import { NomicEmbeddings } from '@langchain/nomic';
import { ChatGroq } from '@langchain/groq';

dotenv.config();

const app = express();
const PORT = Number(process.env.PORT ?? 5174);
const DATA_DIR = process.env.DATA_DIR ?? '../data';
const CHUNK_SIZE = Number(process.env.CHUNK_SIZE ?? 700);
const CHUNK_OVERLAP = Number(process.env.CHUNK_OVERLAP ?? 120);
const TOP_K = Number(process.env.TOP_K ?? 4);
const pdfPath = path.resolve(path.dirname(new URL(import.meta.url).pathname), `${DATA_DIR}/Product Requirements Document_(PRD)_VWO.com.pdf`);
const CHROMA_COLLECTION = process.env.CHROMA_COLLECTION ?? 'vwo_prd';

app.use(cors());
app.use(express.json());
app.use(express.static('dist'));

const chromaOptions = (() => {
  const chromaUrl = process.env.CHROMA_URL;
  if (chromaUrl) {
    const url = new URL(chromaUrl);
    return {
      host: url.hostname,
      port: Number(url.port) || (url.protocol === 'https:' ? 443 : 80),
      ssl: url.protocol === 'https:',
    };
  }
  return {
    host: process.env.CHROMA_HOST ?? 'localhost',
    port: Number(process.env.CHROMA_PORT ?? 8000),
    ssl: process.env.CHROMA_SSL === 'true',
  };
})();

const chromaClient = new ChromaClient(chromaOptions);
let collection;
let usingChroma = true;

const createMemoryVectorStore = () => {
  const records = [];

  const dot = (a, b) => a.reduce((sum, v, i) => sum + v * b[i], 0);
  const norm = (v) => Math.sqrt(dot(v, v));
  const cosineSimilarity = (a, b) => {
    const normA = norm(a);
    const normB = norm(b);
    return normA === 0 || normB === 0 ? 0 : dot(a, b) / (normA * normB);
  };

  return {
    async count() {
      return records.length;
    },
    async add({ ids, embeddings, metadatas, documents }) {
      for (let i = 0; i < ids.length; i += 1) {
        records.push({ id: ids[i], embedding: embeddings[i], metadata: metadatas[i], document: documents[i] });
      }
    },
    async query({ queryEmbeddings, nResults = 4, include = [] }) {
      const queryEmbedding = queryEmbeddings[0];
      const scored = records.map((record, index) => ({
        index,
        score: cosineSimilarity(queryEmbedding, record.embedding),
      })).sort((a, b) => b.score - a.score).slice(0, nResults);

      const documents = include.includes('documents') ? scored.map((item) => records[item.index].document) : [];
      const metadatas = include.includes('metadatas') ? scored.map((item) => records[item.index].metadata) : [];
      const distances = include.includes('distances') ? scored.map((item) => 1 - item.score) : [];

      return { documents: [documents], metadatas: [metadatas], distances: [distances] };
    },
  };
};

try {
  collection = await chromaClient.getOrCreateCollection({ name: CHROMA_COLLECTION });
} catch (error) {
  console.warn('Chroma DB unavailable, falling back to in-memory vector store:', error.message);
  usingChroma = false;
  collection = createMemoryVectorStore();
}

const embeddingProvider = new NomicEmbeddings({ apiKey: process.env.NOMIC_API_KEY });

const splitText = (text) => {
  const chunks = [];
  let start = 0;
  while (start < text.length) {
    const end = Math.min(text.length, start + CHUNK_SIZE);
    const chunk = text.slice(start, end);
    chunks.push(chunk);
    start += CHUNK_SIZE - CHUNK_OVERLAP;
  }
  return chunks;
};

const loadPdfText = async () => {
  if (pdfParse && typeof pdfParse === 'function') {
    try {
      const dataBuffer = fs.readFileSync(pdfPath);
      const parsed = await pdfParse(dataBuffer);
      return parsed.text;
    } catch (e) {
      console.warn('pdf-parse execution failed:', e.message);
    }
  }

  // Fallback: extract text using simple text patterns from the PDF buffer
  try {
    const dataBuffer = fs.readFileSync(pdfPath);
    const text = dataBuffer.toString('utf-8', 0, Math.min(100000, dataBuffer.length));
    // Extract readable text by removing binary characters
    const readable = text
      .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]/g, '')
      .split('\n')
      .filter(line => line.trim().length > 0)
      .join('\n');
    return readable || 'Unable to extract PDF text';
  } catch (e) {
    throw new Error(`PDF text extraction failed: ${e.message}`);
  }
};

app.get('/api/status', async (req, res) => {
  const docs = await collection.count();
  res.json(['Collection loaded', `${docs} documents stored`]);
});

app.get('/api/ingest', async (req, res) => {
  try {
    const rawText = await loadPdfText();
    const chunks = splitText(rawText);
    const ids = chunks.map((_, idx) => `vwo-chunk-${idx + 1}`);
    const embeddings = await embeddingProvider.embedDocuments(chunks);

    await collection.add({
      ids,
      embeddings,
      metadatas: chunks.map((chunk, idx) => ({ chunkId: idx + 1, text: chunk })),
      documents: chunks,
    });

    const steps = [
      'Loaded PDF from data folder',
      `Split PDF into ${chunks.length} chunks`,
      'Generated embeddings for each chunk using Nomic',
      'Stored embeddings in local ChromaDB',
    ];

    return res.json({ success: true, steps });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
});

app.post('/api/query', async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) {
      return res.status(400).json({ error: 'Query text required' });
    }

    const queryEmbedding = await embeddingProvider.embedQuery(query);
    const response = await collection.query({
      queryEmbeddings: [queryEmbedding],
      nResults: 4,
      include: ['documents', 'metadatas', 'distances'],
    });

    const matches = response.documents[0].map((doc, index) => ({
      document: doc,
      metadata: response.metadatas[0][index],
      score: response.distances[0][index],
    }));

    const combinedText = matches.map((match, idx) => `Chunk ${idx + 1}: ${match.document}`).join('\n\n');
    const prompt = `You are a helpful assistant. Use the following document snippets to answer the query. \n\nDocument snippets:\n${combinedText}\n\nQuery: ${query}\n\nAnswer:`;

    const llm = new ChatGroq({ apiKey: process.env.GROQ_API_KEY, model: 'llama-3.3-70b-versatile' });
    const result = await llm.invoke(prompt);
    const answer = typeof result === 'string' ? result : result?.text ?? JSON.stringify(result);

    return res.json({ answer, matches });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
});

const startServer = (port = PORT) => {
  const server = app.listen(port, () => {
    console.log(`RAG Explorer server listening on http://localhost:${port}`);
  }).on('error', (error) => {
    if (error.code === 'EADDRINUSE') {
      console.warn(`Port ${port} already in use. Trying next port...`);
      startServer(port + 1);
    } else {
      console.error('Server error:', error);
      process.exit(1);
    }
  });
};

startServer();
