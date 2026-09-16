import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "/insight/",
  resolve: {
    alias: {
      "@ch2/macro-shell": path.resolve(here, "../shared/macro-shell"),
      "@ch2/ai-assistant": path.resolve(here, "../shared/ai-assistant"),
      "@ch2/stats-glossary": path.resolve(here, "../shared/stats-glossary"),
      clsx: path.resolve(here, "node_modules/clsx"),
      axios: path.resolve(here, "node_modules/axios"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5180,
    fs: { allow: [path.resolve(here, "..")] },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
