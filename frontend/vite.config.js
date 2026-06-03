import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, the frontend runs on :5173 and the FastAPI backend on :8000.
// The /api prefix is rewritten away on the way out, so the frontend
// can call `/api/auth/login` and the backend sees `/auth/login`.
// This avoids any CORS configuration on the backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
