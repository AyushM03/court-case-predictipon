/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the FastAPI app runs on :8000 (uvicorn court_delay.api:app) and serves /api/*.
// Figures come from public/figures (scripts/copy-figures.mjs runs before every build).
// In production the built files are served by FastAPI (local, Docker) or by Vercel (D-019).
const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": api },
  },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/setupTests.ts" },
});
