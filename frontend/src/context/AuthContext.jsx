// Auth context — single source of truth for the logged-in user state.
//
// Implemented in Task 6:
//   * On mount, hydrate from localStorage (`auth_token`).
//   * Expose: { user, token, login(email, password), logout(), register(email, password) }.
//   * After login/register, persist the token to localStorage and decode
//     the JWT to get the user id; optionally hit /auth/me for the full
//     user record.

import { createContext, useContext } from 'react';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // TODO: useState for { user, token }, useEffect for hydration
  const value = null;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
