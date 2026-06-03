// Fetch wrapper. One place that knows about the token + base URL + error handling.
//
// Implemented in Task 6:
//   * Read the JWT from localStorage on every call.
//   * Attach `Authorization: Bearer <token>` if present.
//   * Base URL is `/api` — Vite proxies that to the FastAPI backend in dev.
//   * On 401: clear the stored token and let the caller redirect to /login.
//   * Parse JSON; throw on non-2xx with the server-supplied `detail`.

export async function apiRequest(path, options = {}) {
  // TODO: implement
  throw new Error('apiRequest not implemented');
}
