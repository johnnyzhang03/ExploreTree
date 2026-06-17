import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // dev only: forward the WebSocket to the backend so the origin-derived
      // WS_URL (ws://localhost:5173/ws) reaches FastAPI on :8000.
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
    headers: {
      "Cache-Control": "no-store",
    },
  },
});
