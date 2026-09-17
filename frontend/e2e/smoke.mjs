/**
 * Kiểm tra nhanh giao diện bằng trình duyệt thật (playwright-core + Chrome/Edge đã cài sẵn, không tải trình duyệt).
 * Đi qua các luồng chính của Admin và Giảng viên, chụp màn hình, và THẤT BẠI nếu có lỗi JavaScript,
 * lỗi console hoặc API trả mã >= 400.
 *
 * Tiền điều kiện: API chạy ở :8000, frontend chạy ở :5173 (npm run dev) hoặc :4173 (npm run preview).
 *   $env:LMS_DEMO_PASSWORD = "<mật khẩu tài khoản demo>"
 *   npm run smoke                                  # ảnh lưu ở e2e/screenshots
 *
 * Biến tùy chọn: SMOKE_BASE_URL, SMOKE_OUT, SMOKE_CHANNEL (chrome | msedge), SMOKE_ADMIN, SMOKE_TEACHER.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";

const BASE = process.env.SMOKE_BASE_URL ?? "http://localhost:5173";
const OUT = process.env.SMOKE_OUT ?? "e2e/screenshots";
const PASSWORD = process.env.LMS_DEMO_PASSWORD;
const ADMIN = process.env.SMOKE_ADMIN ?? "admin";
const TEACHER = process.env.SMOKE_TEACHER ?? "gv.tranminhhung";

if (!PASSWORD) {
  console.error("Cần đặt biến LMS_DEMO_PASSWORD (mật khẩu tài khoản demo).");
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

const problems = [];
const steps = [];

function watch(page, label) {
  page.on("console", (m) => { if (m.type() === "error") problems.push(`[${label}] console.error: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`[${label}] lỗi JavaScript: ${e.message}`));
  page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) problems.push(`[${label}] API ${r.status()} ${r.url()}`); });
}

async function settle(page) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(700);           // chờ animation Chart.js (250 ms) vẽ xong
}

async function shot(page, name, options = {}) {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true, ...options });
  steps.push(name);
  console.log(`✔ ${name}`);
}

async function login(page, username) {
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Tên đăng nhập").fill(username);
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
}

async function expectCanvasCount(page, min, label) {
  const count = await page.locator("canvas").count();
  if (count < min) problems.push(`[${label}] chỉ có ${count} biểu đồ, cần >= ${min}`);
}

const browser = await chromium.launch({ channel: process.env.SMOKE_CHANNEL ?? "chrome", headless: true });
try {
  // ------------------------------------------------------------------ đăng nhập sai
  {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    await page.goto(`${BASE}/login`);
    await page.getByLabel("Tên đăng nhập").fill(ADMIN);
    await page.getByLabel("Mật khẩu").fill("sai-mat-khau");
    await page.getByRole("button", { name: "Đăng nhập" }).click();
    await page.getByText("Sai tên đăng nhập hoặc mật khẩu").waitFor();
    await shot(page, "00_login_error");
    await context.close();
  }

  // ------------------------------------------------------------------ Admin
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
    const page = await context.newPage();
    watch(page, "admin");
    await login(page, ADMIN);
    await page.waitForURL(/\/admin$/);
    await page.getByText("Tổng môn học").waitFor();
    await settle(page);
    await expectCanvasCount(page, 3, "admin tổng quan");
    await shot(page, "01_admin_overview");

    await page.getByRole("row", { name: /Khoa Công nghệ Thông tin/ }).first().click();
    await page.getByRole("button", { name: "Xem SV" }).first().waitFor();
    await settle(page);
    await page.getByRole("button", { name: "Xem SV" }).first().click();
    await page.getByText(/SV đăng ký ·/).waitFor();
    await settle(page);
    await shot(page, "02_admin_drilldown_students");

    await page.getByRole("link", { name: "Lưu lượng" }).click();
    await page.getByText("Top 10 giờ đông nhất").waitFor();
    await settle(page);
    await expectCanvasCount(page, 2, "admin lưu lượng");
    await shot(page, "03_admin_traffic");

    await page.getByRole("link", { name: "Báo cáo" }).click();
    await page.getByRole("button", { name: "Xem trước" }).click();
    await page.getByText(/dòng$/).first().waitFor();
    await settle(page);
    await shot(page, "04_admin_reports_preview");

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: /Xuất Excel/ }).click(),
    ]);
    console.log(`✔ tải file ${download.suggestedFilename()}`);
    if (!download.suggestedFilename().endsWith(".xlsx")) problems.push(`[admin] file tải về sai: ${download.suggestedFilename()}`);
    await context.close();
  }

  // ------------------------------------------------------------------ Giảng viên
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    watch(page, "teacher");
    await login(page, TEACHER);
    await page.waitForURL(/\/teacher\/courses\/\d+\/risk$/);
    await page.getByText("Bảng cảnh báo sinh viên").waitFor();
    await settle(page);
    await shot(page, "05_teacher_risk");

    await page.getByRole("button", { name: /Nguy cơ cao/ }).first().click();          // dòng chú thích doughnut -> lọc
    await settle(page);
    await page.getByRole("button", { name: "Chi tiết" }).first().click();
    await page.getByRole("dialog").getByText("So sánh với trung bình lớp").waitFor();
    await settle(page);
    await shot(page, "06_teacher_student_modal", { fullPage: false });
    await page.keyboard.press("Escape");

    await page.getByRole("link", { name: "Tiến độ lớp" }).click();
    await page.getByText("Tiến độ theo chương / tuần").waitFor();
    await settle(page);
    await expectCanvasCount(page, 2, "gv tiến độ");
    await shot(page, "07_teacher_progress");

    await page.goto(`${BASE}/admin`);                                                   // GV không vào được trang Admin
    await page.waitForURL(/\/teacher/);
    console.log("✔ giảng viên bị chuyển khỏi /admin");
    await context.close();
  }

  // ------------------------------------------------------------------ màn hình điện thoại
  {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    watch(page, "mobile");
    await login(page, TEACHER);
    await page.getByText("Bảng cảnh báo sinh viên").waitFor();
    await settle(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 1) problems.push(`[mobile] trang cuộn ngang ${overflow}px`);
    await shot(page, "08_mobile_teacher_risk");
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(`\n${steps.length} ảnh chụp trong ${OUT}`);
if (problems.length) {
  console.error(`\n${problems.length} vấn đề:\n${problems.join("\n")}`);
  process.exit(1);
}
console.log("Không có lỗi JavaScript, lỗi console hay lỗi API.");
