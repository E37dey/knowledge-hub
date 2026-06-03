// App root — routes + auth context wrapper.
//
// Implemented in Task 6:
//   * <AuthProvider> wraps the tree, exposes user + token + login/logout.
//   * <BrowserRouter> + <Routes>:
//       /login     -> <Login />
//       /register  -> <Register />
//       /          -> <Dashboard />  (protected)
//       /ask       -> <Ask />        (protected)
//   * <ProtectedRoute> redirects to /login when there is no token.

export default function App() {
  return (
    <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      <h1>Knowledge Hub</h1>
      <p>Scaffold — wiring lands in Task 6.</p>
    </div>
  );
}
