import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server gọi API qua proxy /api -> FastAPI (python -m uvicorn backend.app.main:app --port 8000)
const API_TARGET = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: API_TARGET, changeOrigin: true } },
  },
  preview: {
    port: 4173,
    proxy: { "/api": { target: API_TARGET, changeOrigin: true } },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // Chỉ tách thư viện biểu đồ (không phụ thuộc antd); antd và react để Vite tự chia, tránh chunk vòng lặp
        manualChunks: (id) => (/node_modules[\\/](chart\.js|react-chartjs-2|chartjs-)/.test(id) ? "charts" : undefined),
      },
    },
  },
  test: { environment: "node", include: ["src/**/*.test.js"] },
});
