import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  base: "/built/",
  resolve: {
    alias: {
      "@ch2/ai-assistant": path.resolve(__dirname, "../shared/ai-assistant"),
      "@ch2/macro-shell": path.resolve(__dirname, "../shared/macro-shell"),
      clsx: path.resolve(__dirname, "node_modules/clsx"),
      axios: path.resolve(__dirname, "node_modules/axios"),
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
