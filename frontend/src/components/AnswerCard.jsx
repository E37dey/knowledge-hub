// Renders Claude's answer. Two jobs beyond printing text:
//   1. Detect the exact refusal sentence and show it as a distinct banner
//      rather than a normal answer — the grounding guarantee made visible.
//   2. Highlight inline [filename, p.N] citations as badges by splitting on
//      the bracket pattern (the same format the backend prompt enforces).

const REFUSAL = "I don't have information on this in the provided documents.";

// SPLIT keeps the bracketed citations as captured pieces; IS_CITATION tests
// each piece. IS_CITATION is intentionally NOT global — a /g regex shares
// lastIndex across .test() calls and would flip-flop inside the map below.
const SPLIT = /(\[[^\]]+\])/g;
const IS_CITATION = /^\[[^\]]+\]$/;

export default function AnswerCard({ answer, responseTimeMs }) {
  if (answer.trim() === REFUSAL) {
    return (
      <div className="answer-card refusal">
        <p className="answer-text">{answer}</p>
      </div>
    );
  }

  const parts = answer.split(SPLIT);

  return (
    <div className="answer-card">
      <p className="answer-text">
        {parts.map((part, i) =>
          IS_CITATION.test(part) ? (
            <span key={i} className="citation">
              {part}
            </span>
          ) : (
            <span key={i}>{part}</span>
          ),
        )}
      </p>
      {responseTimeMs != null && (
        <div className="answer-meta">answered in {responseTimeMs} ms</div>
      )}
    </div>
  );
}
