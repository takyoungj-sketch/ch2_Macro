import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  base: "/lab/",
  resolve: {
    alias: {
      "@ch2/macro-shell": path.resolve(__dirname, "../shared/macro-shell"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5179,
    fs: { allow: [path.resolve(__dirname, "..")] },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
