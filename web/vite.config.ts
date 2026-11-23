import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        // In Docker: `api` resolves via Docker DNS to the API container.
        // Native dev: set VITE_API_TARGET=http://172.18.0.1:8001 in the shell.
        target: process.env.VITE_API_TARGET || "http://api:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
