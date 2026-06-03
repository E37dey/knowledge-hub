// Dashboard — the user's own documents, with upload and delete.
//
// Every call goes through apiRequest, which attaches the JWT; the backend
// scopes all three operations to the token's user, so this component never
// has to think about isolation — it simply cannot see another user's docs.

import { useEffect, useRef, useState } from 'react';

import { apiRequest } from '../api/client.js';
import DocumentCard from '../components/DocumentCard.jsx';

export default function Dashboard() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileInput = useRef(null);

  async function loadDocuments() {
    setLoading(true);
    setError(null);
    try {
      setDocs(await apiRequest('/documents'));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      // No `json` here — apiRequest leaves Content-Type unset so the browser
      // adds the multipart boundary itself.
      await apiRequest('/documents/upload', { method: 'POST', body: form });
      await loadDocuments();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  async function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.filename}"? This removes its vectors too.`)) {
      return;
    }
    setError(null);
    try {
      await apiRequest(`/documents/${doc.id}`, { method: 'DELETE' });
      await loadDocuments();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <div className="page-head">
        <h2>Your documents</h2>
        <label className="btn btn-primary">
          {uploading ? 'Uploading…' : 'Upload PDF'}
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf"
            hidden
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : docs.length === 0 ? (
        <p className="muted">No documents yet. Upload a PDF to get started.</p>
      ) : (
        <ul className="doc-list">
          {docs.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} onDelete={handleDelete} />
          ))}
        </ul>
      )}
    </section>
  );
}
