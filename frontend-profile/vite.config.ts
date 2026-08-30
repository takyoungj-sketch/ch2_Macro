import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// frontend-profile — 지역 프로필 독립 앱 (D-027, docs/REGIONAL_PROFILE_ARCHITECTURE.md §12)
export default defineConfig({
  plugins: [react()],
  base: "/profile/",
  resolve: {
      alias: {
        "@ch2/macro-shell": path.resolve(__dirname, "../shared/macro-shell"),
        "@ch2/region-picker": path.resolve(__dirname, "../shared/region-picker"),
        "@ch2/stats-glossary": path.resolve(__dirname, "../shared/stats-glossary"),
        "@ch2/ai-assistant": path.resolve(__dirname, "../shared/ai-assistant"),
        clsx: path.resolve(__dirname, "node_modules/clsx"),
        axios: path.resolve(__dirname, "node_modules/axios"),
      },
  },
  server: {
    host: "127.0.0.1",
    port: 5177,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
