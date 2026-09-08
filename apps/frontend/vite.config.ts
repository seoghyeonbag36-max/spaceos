import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    // 프록시 대상은 환경변수로 바꿀 수 있다 — 백엔드를 다른 포트로 띄운 채
    // 렌더 검증(scripts/render_validate.py)을 돌릴 때 쓴다. 미설정이면 종전 그대로.
    proxy: {
      "/api": process.env.SPACEOS_API_TARGET ?? "http://localhost:8000",
    },
  },
});
