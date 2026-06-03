// Gate for authenticated-only routes. While the auth context is still
// hydrating from /auth/me we render nothing decisive — bouncing to /login
// here would log out anyone who refreshes a protected page.

import { Navigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';

export default function ProtectedRoute({ children }) {
  const { token, loading } = useAuth();

  if (loading) return <p className="muted centered">Loading…</p>;
  if (!token) return <Navigate to="/login" replace />;
  return children;
}
