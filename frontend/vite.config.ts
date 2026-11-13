import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth/callback": process.env.API_PROXY_TARGET ?? "http://localhost:8000",
      "/eu": process.env.API_PROXY_TARGET ?? "http://localhost:8000",
      "/perguntar": process.env.API_PROXY_TARGET ?? "http://localhost:8000",
      "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8000",
      "/health": process.env.API_PROXY_TARGET ?? "http://localhost:8000",
    },
  },
});
