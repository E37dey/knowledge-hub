// Auth context — single source of truth for the logged-in user.
//
//   * `token` is seeded synchronously from localStorage so a refresh on a
//     protected page doesn't flash the login screen before hydration.
//   * Whenever the token changes, we hit GET /me to load the full user
//     record. Using /me (instead of decoding the JWT client-side) means one
//     fewer dependency AND it validates the token against the server — a
//     stale/forged token resolves to a 401 and we log out cleanly.
//   * register() auto-logs-in by delegating to login() after creating the
//     account, so the user lands authenticated in one step.

import { createContext, useContext, useEffect, useState } from 'react';

import { apiRequest, getToken, setToken } from '../api/client.js';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [user, setUser] = useState(null);
  // `loading` covers the initial hydration so ProtectedRoute can wait
  // instead of bouncing a logged-in user to /login on a hard refresh.
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    let active = true;

    async function hydrate() {
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        const me = await apiRequest('/me');
        if (active) setUser(me);
      } catch {
        // Token invalid/expired — apiRequest already cleared it.
        if (active) {
          setTokenState(null);
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    hydrate();
    return () => {
      active = false;
    };
  }, [token]);

  async function login(email, password) {
    const data = await apiRequest('/auth/login', {
      method: 'POST',
      json: { email, password },
    });
    setToken(data.access_token);
    const me = await apiRequest('/me');
    setTokenState(data.access_token);
    setUser(me);
    return me;
  }

  async function register(email, password) {
    await apiRequest('/auth/register', {
      method: 'POST',
      json: { email, password },
    });
    return login(email, password);
  }

  function logout() {
    setToken(null);
    setTokenState(null);
    setUser(null);
  }

  const value = { user, token, loading, login, register, logout };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>.');
  return ctx;
}
