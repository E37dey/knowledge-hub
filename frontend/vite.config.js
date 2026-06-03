import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, the frontend runs on :5173 and the FastAPI backend on :8001.
// The /api prefix is rewritten away on the way out, so the frontend
// can call `/api/auth/login` and the backend sees `/auth/login`.
// This avoids any CORS configuration on the backend.
//
// Backend port note: the conventional :8000 is occupied on this machine by
// the SimplyPrint Bambu Lab printer service, so the backend runs on :8001
// here (start it with `py -m uvicorn app.main:app --port 8001`).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
