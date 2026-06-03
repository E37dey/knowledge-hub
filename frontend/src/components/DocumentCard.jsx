// One row in the documents list: filename, a status badge, chunk count,
// upload time, and a delete action.

const STATUS_CLASS = {
  indexed: 'badge-ok',
  processing: 'badge-warn',
  failed: 'badge-err',
};

export default function DocumentCard({ doc, onDelete }) {
  const badgeClass = STATUS_CLASS[doc.status] || 'badge-warn';

  return (
    <li className="doc-card">
      <div className="doc-main">
        <span className="doc-name" title={doc.filename}>
          {doc.filename}
        </span>
        <span className={`badge ${badgeClass}`}>{doc.status}</span>
      </div>
      <div className="doc-meta">
        <span>{doc.chunk_count} chunks</span>
        <span>{new Date(doc.uploaded_at).toLocaleString()}</span>
        <button className="btn btn-ghost btn-sm" onClick={() => onDelete(doc)}>
          Delete
        </button>
      </div>
    </li>
  );
}
