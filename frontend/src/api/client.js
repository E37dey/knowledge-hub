// Fetch wrapper. One place that knows about the token + base URL + error
// handling, so no component ever touches `fetch`, headers, or localStorage
// for auth directly.
//
//   * Base URL is `/api` — Vite proxies that to the FastAPI backend in dev
//     (see vite.config.js), so there is no CORS to configure.
//   * The JWT is read from localStorage on every call and sent as
//     `Authorization: Bearer <token>`.
//   * Pass a plain object as `json` to send a JSON body; pass a FormData
//     instance as `body` for multipart uploads (we must NOT set
//     Content-Type ourselves then — the browser adds the multipart boundary).
//   * Non-2xx throws an ApiError carrying the server's `detail` string.
//   * A 401 clears the stored token so the next ProtectedRoute render bounces
//     the user to /login.

const BASE_URL = '/api';
const TOKEN_KEY = 'auth_token';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function apiRequest(path, options = {}) {
  const { json, headers: extraHeaders, ...rest } = options;
  const headers = { ...extraHeaders };

  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let body = rest.body;
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...rest, headers, body });

  // Expired / invalid token: drop it so the app falls back to /login.
  if (res.status === 401) {
    setToken(null);
    throw new ApiError('Your session has expired. Please log in again.', 401);
  }

  if (res.status === 204) return null;

  // Some error bodies are empty; guard the JSON parse.
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `Request failed (${res.status})`;
    throw new ApiError(
      typeof detail === 'string' ? detail : JSON.stringify(detail),
      res.status,
    );
  }

  return data;
}
