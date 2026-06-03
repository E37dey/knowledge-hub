// Ask page — question form, grounded answer, source cards, and a per-user
// history panel. The history is loaded from /query/history (already scoped
// to the JWT user) and clicking an item replays its stored answer.

import { useEffect, useState } from 'react';

import { apiRequest } from '../api/client.js';
import AnswerCard from '../components/AnswerCard.jsx';
import SourceCard from '../components/SourceCard.jsx';

export default function Ask() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  async function loadHistory() {
    try {
      setHistory(await apiRequest('/query/history'));
    } catch {
      // History is a non-critical panel — don't block the page on it.
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiRequest('/query', {
        method: 'POST',
        json: { question, top_k: 5 },
      });
      setResult(res);
      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  }

  function replay(item) {
    setQuestion(item.question);
    setResult({
      answer: item.answer,
      sources: item.sources,
      response_time_ms: item.response_time_ms,
    });
  }

  return (
    <section className="ask-layout">
      <div className="ask-main">
        <h2>Ask your documents</h2>
        <form onSubmit={handleSubmit} className="ask-form">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the supply voltage range of the LM358?"
            rows={3}
          />
          <button className="btn btn-primary" disabled={asking}>
            {asking ? 'Thinking…' : 'Ask'}
          </button>
        </form>

        {error && <p className="error">{error}</p>}

        {result && (
          <>
            <AnswerCard
              answer={result.answer}
              responseTimeMs={result.response_time_ms}
            />
            {result.sources?.length > 0 && (
              <>
                <h3>Sources</h3>
                <ul className="source-list">
                  {result.sources.map((source, i) => (
                    <SourceCard key={i} source={source} />
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </div>

      <aside className="ask-history">
        <h3>History</h3>
        {history.length === 0 ? (
          <p className="muted">No questions yet.</p>
        ) : (
          <ul className="history-list">
            {history.map((item) => (
              <li
                key={item.id}
                className="history-item"
                onClick={() => replay(item)}
              >
                <span className="history-q">{item.question}</span>
                <span className="history-time">
                  {new Date(item.created_at).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </section>
  );
}
