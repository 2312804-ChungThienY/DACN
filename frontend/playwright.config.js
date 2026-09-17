/**
 * E2E (SPEC 6.3) – Playwright Test chạy trên Chrome đã cài sẵn (channel "chrome"), không tải trình duyệt.
 *
 * Tiền điều kiện: API ở :8000 và frontend (npm run dev hoặc npm run preview, hoặc docker ở :8080).
 *   $env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
 *   $env:E2E_BASE_URL = "http://127.0.0.1:5173"     # mặc định
 *   $env:E2E_JWT_SECRET = "<BACKEND_JWT_SECRET>"     # tùy chọn: bật test token hết hạn
 *   npx playwright test
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e/tests",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["json", { outputFile: "test-results/results.json" }],
  ],
  globalTeardown: "./e2e/global-teardown.js",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
    channel: process.env.E2E_CHANNEL ?? "chrome",
    headless: true,
    locale: "vi-VN",
    timezoneId: "Asia/Ho_Chi_Minh",
    viewport: { width: 1366, height: 800 },
    acceptDownloads: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
