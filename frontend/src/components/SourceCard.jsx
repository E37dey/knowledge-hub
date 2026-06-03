// One retrieved source chunk: its citation key, the similarity score as a
// percentage + bar, and a truncated preview of the chunk text.

export default function SourceCard({ source }) {
  const pct = Math.round((source.score ?? 0) * 100);

  return (
    <li className="source-card">
      <div className="source-head">
        <span className="source-file">
          [{source.filename}, p.{source.page}]
        </span>
        <span className="source-score">{pct}% match</span>
      </div>
      <div className="score-bar">
        <div className="score-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="source-text">{source.text}</p>
    </li>
  );
}
