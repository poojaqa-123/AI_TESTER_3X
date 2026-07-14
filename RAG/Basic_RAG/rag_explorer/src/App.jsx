import { useEffect, useState } from 'react';

const fetchJson = async (url, options = {}) => {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
};

function App() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [steps, setSteps] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState('idle');

  useEffect(() => {
    fetchJson('/api/status')
      .then(setSteps)
      .catch(() => setSteps([]));
  }, []);

  const ingestDocument = async () => {
    setLoading(true);
    setIngestionStatus('ingesting');
    try {
      const payload = await fetchJson('/api/ingest');
      setSteps(payload.steps);
      setIngestionStatus('done');
    } catch (error) {
      setIngestionStatus('error');
      setAnswer(error.message);
    } finally {
      setLoading(false);
    }
  };

  const askQuestion = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setAnswer('');
    setChunks([]);

    try {
      const payload = await fetchJson('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      setAnswer(payload.answer);
      setChunks(payload.matches || []);
    } catch (error) {
      setAnswer(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <header>
        <h1>RAG Explorer</h1>
        <p>Demonstrates PDF ingestion, chunking, embeddings, storage, retrieval, and answer generation.</p>
      </header>

      <section className="panel">
        <h2>1. Ingest PDF</h2>
        <p>Reads the PDF from <code>data/Product Requirements Document_(PRD)_VWO.com.pdf</code> and stores its embeddings locally.</p>
        <button onClick={ingestDocument} disabled={loading}>Start ingestion</button>
        <div className="status-row">
          <strong>Status:</strong> {ingestionStatus}
        </div>
        <div className="status-log">
          {steps.map((step, index) => (
            <div key={index} className="step-row">
              <span>{step}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>2. Ask a Question</h2>
        <div className="query-row">
          <input
            value={query}
            placeholder="Ask something about the VWO PRD..."
            onChange={(event) => setQuery(event.target.value)}
          />
          <button onClick={askQuestion} disabled={loading || !query.trim()}>Query</button>
        </div>
        {loading && <p>Processing...</p>}
        {answer && (
          <div className="result-card">
            <h3>Answer</h3>
            <p>{answer}</p>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>3. Retrieved Chunks</h2>
        <p>Top 4 document chunks retrieved for the query.</p>
        {chunks.length === 0 ? (
          <p>No chunks returned yet.</p>
        ) : (
          <div className="chunk-list">
            {chunks.map((chunk, idx) => (
              <article key={idx} className="chunk-card">
                <h4>Chunk {idx + 1}</h4>
                <p>{chunk.metadata?.text || chunk.document || chunk.page || 'No text available'}</p>
                <div className="chunk-meta">
                  <span>Score: {chunk.score?.toFixed(4)}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default App;
