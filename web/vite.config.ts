import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发模式：/ws 代理到 FastAPI（uvicorn 跑在 8000 端口）；
// 生产模式：uvicorn 直接托管 dist，WS 同源，不走这里。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
