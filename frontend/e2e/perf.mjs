/**
 * Đo tải trang Dashboard (SPEC 6.2 dòng "Tải trang": biểu đồ đầu tiên < 1 s, LCP < 2,5 s, TTI < 3 s, cache lạnh).
 * Chạy trên bản build production (npm run build && npm run preview, hoặc Nginx trong docker).
 *
 * Mỗi lần đo dùng một context trình duyệt mới (cache lạnh), phiên đăng nhập được đặt sẵn vào localStorage
 * để chỉ đo trang Dashboard. 2 cấu hình: máy bình thường và CPU chậm 4 lần (giả lập máy yếu).
 *   - firstChartMs: thời điểm thẻ <canvas> biểu đồ đầu tiên xuất hiện
 *   - lcpMs: Largest Contentful Paint
 *   - ttiApproxMs: max(DOMContentLoaded, kết thúc long task cuối) – xấp xỉ định nghĩa TTI của Lighthouse
 *   - tbtMs: tổng thời gian long task vượt 50 ms
 *
 *   $env:LMS_DEMO_PASSWORD = "..."; $env:PERF_BASE_URL = "http://127.0.0.1:4173"; node e2e/perf.mjs
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const BASE = process.env.PERF_BASE_URL ?? "http://127.0.0.1:4173";
const PASSWORD = process.env.LMS_DEMO_PASSWORD;
const RUNS = Number(process.env.PERF_RUNS ?? 5);
const OUT = process.env.PERF_OUT ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../perf/results/frontend_perf.json");
const SESSION_KEY = "lms.analytics.session";
if (!PASSWORD) { console.error("Cần LMS_DEMO_PASSWORD"); process.exit(2); }

const PAGES = [
  { name: "admin_overview", username: "admin", path: "/admin", charts: 3 },
  { name: "teacher_risk", username: process.env.PERF_TEACHER ?? "gv.tranminhhung", path: "/teacher", charts: 1 },
];
const PROFILES = [{ name: "binh_thuong", cpu: 1 }, { name: "cpu_cham_4x", cpu: 4 }];
const TARGETS = { firstChartMs: 1000, lcpMs: 2500, ttiApproxMs: 3000 };

async function session(username) {
  const res = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`Đăng nhập ${username}: ${res.status}`);
  const data = await res.json();
  return { token: data.access_token, user: data.user, expiresAt: Date.now() + data.expires_in * 1000 };
}

function initScript([key, value]) {
  localStorage.setItem(key, value);
  window.__perf = { longTasks: [], lcp: null, firstChart: null };
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) window.__perf.longTasks.push({ start: e.startTime, duration: e.duration });
  }).observe({ type: "longtask", buffered: true });
  new PerformanceObserver((list) => {
    const entries = list.getEntries();
    window.__perf.lcp = entries[entries.length - 1].startTime;
  }).observe({ type: "largest-contentful-paint", buffered: true });
  const watch = () => new MutationObserver((_, observer) => {
    if (document.querySelector("canvas")) { window.__perf.firstChart = performance.now(); observer.disconnect(); }
  }).observe(document.documentElement, { childList: true, subtree: true });
  if (document.documentElement) watch(); else document.addEventListener("DOMContentLoaded", watch);
}

const median = (values) => { const s = [...values].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

const browser = await chromium.launch({ channel: process.env.PERF_CHANNEL ?? "chrome", headless: true });
const results = [];
try {
  for (const target of PAGES) {
    const auth = JSON.stringify(await session(target.username));
    for (const profile of PROFILES) {
      const runs = [];
      for (let i = 0; i < RUNS; i += 1) {
        const context = await browser.newContext({ viewport: { width: 1366, height: 800 } });
        await context.addInitScript(initScript, [SESSION_KEY, auth]);
        const page = await context.newPage();
        const cdp = await context.newCDPSession(page);
        await cdp.send("Emulation.setCPUThrottlingRate", { rate: profile.cpu });
        await page.goto(BASE + target.path, { waitUntil: "load" });
        await page.waitForFunction((n) => document.querySelectorAll("canvas").length >= n, target.charts, { timeout: 60_000 });
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(1500);
        const m = await page.evaluate(() => {
          const nav = performance.getEntriesByType("navigation")[0];
          const tasks = window.__perf.longTasks;
          const lastLongTaskEnd = tasks.length ? Math.max(...tasks.map((t) => t.start + t.duration)) : 0;
          return {
            ttfbMs: nav.responseStart, domContentLoadedMs: nav.domContentLoadedEventEnd, loadMs: nav.loadEventEnd,
            firstChartMs: window.__perf.firstChart, lcpMs: window.__perf.lcp,
            ttiApproxMs: Math.max(nav.domContentLoadedEventEnd, lastLongTaskEnd),
            tbtMs: tasks.reduce((sum, t) => sum + Math.max(0, t.duration - 50), 0),
            transferKB: performance.getEntriesByType("resource").reduce((s, r) => s + (r.transferSize || 0), nav.transferSize || 0) / 1024,
          };
        });
        runs.push(m);
        await context.close();
      }
      const summary = Object.fromEntries(Object.keys(runs[0]).map((k) => [k, Math.round(median(runs.map((r) => r[k])) * 10) / 10]));
      const passed = Object.entries(TARGETS).every(([k, limit]) => summary[k] != null && summary[k] < limit);
      results.push({ page: target.name, profile: profile.name, cpuThrottle: profile.cpu, runs: RUNS, median: summary, passed, raw: runs });
      console.log(`${passed ? "OK " : "!! "}${target.name.padEnd(16)} ${profile.name.padEnd(12)} biểu đồ đầu ${summary.firstChartMs} ms · LCP ${summary.lcpMs} ms · TTI~ ${summary.ttiApproxMs} ms · TBT ${summary.tbtMs} ms · ${summary.transferKB} KB`);
    }
  }
} finally {
  await browser.close();
}
mkdirSync(path.dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ base: BASE, targets: TARGETS, measuredAt: new Date().toISOString(), results }, null, 2));
console.log(`Đã ghi ${OUT}`);
