import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  base: "/rent/",
  resolve: {
    alias: {
      "@ch2/macro-shell": path.resolve(__dirname, "../shared/macro-shell"),
      "@ch2/stats-glossary": path.resolve(__dirname, "../shared/stats-glossary"),
      "@ch2/stats-table-filter": path.resolve(__dirname, "../shared/stats-table-filter"),
      "@ch2/ai-assistant": path.resolve(__dirname, "../shared/ai-assistant"),
      "@ch2/ai2-entry": path.resolve(__dirname, "../shared/ai2-entry"),
      clsx: path.resolve(__dirname, "node_modules/clsx"),
      axios: path.resolve(__dirname, "node_modules/axios"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5178,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
