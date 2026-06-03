// App root — auth context, router, and the protected/public route split.

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import NavBar from './components/NavBar.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import Ask from './pages/Ask.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Login from './pages/Login.jsx';
import Register from './pages/Register.jsx';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <NavBar />
        <main className="container">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/ask"
              element={
                <ProtectedRoute>
                  <Ask />
                </ProtectedRoute>
              }
            />
            {/* Unknown paths fall back to the (protected) dashboard. */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </BrowserRouter>
    </AuthProvider>
  );
}
