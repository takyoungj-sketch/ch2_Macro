import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    base: "/land/",
    resolve: {
      alias: {
        "@ch2/ai-assistant": path.resolve(__dirname, "../shared/ai-assistant"),
        "@ch2/macro-shell": path.resolve(__dirname, "../shared/macro-shell"),
        "@ch2/region-picker": path.resolve(__dirname, "../shared/region-picker"),
        clsx: path.resolve(__dirname, "node_modules/clsx"),
        axios: path.resolve(__dirname, "node_modules/axios"),
      },
    },
    server: {
      port: Number(env.VITE_DEV_PORT ?? 5173),
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
