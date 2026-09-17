import { expect } from "@playwright/test";
import { createHmac } from "node:crypto";

export const PASSWORD = process.env.LMS_DEMO_PASSWORD ?? "";
export const ADMIN = process.env.E2E_ADMIN ?? "admin";
export const TEACHER = process.env.E2E_TEACHER ?? "gv.tranminhhung";
export const SESSION_KEY = "lms.analytics.session";

export function requirePassword(test) {
  test.skip(!PASSWORD, "Cần biến LMS_DEMO_PASSWORD");
}

export async function login(page, username) {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập").fill(username);
  await page.getByLabel("Mật khẩu").fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/** Đăng nhập qua API (không qua giao diện) – trả về token. */
export async function apiToken(request, username) {
  const res = await request.post("/api/v1/auth/login", { data: { username, password: PASSWORD } });
  expect(res.status(), `đăng nhập ${username}`).toBe(200);
  return (await res.json()).access_token;
}

export const bearer = (token) => ({ Authorization: `Bearer ${token}` });

/** Ký JWT HS256 (chỉ dùng trong test, cần E2E_JWT_SECRET = BACKEND_JWT_SECRET). */
export function signToken(payload, secret) {
  const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString("base64url");
  const body = `${b64({ alg: "HS256", typ: "JWT" })}.${b64(payload)}`;
  return `${body}.${createHmac("sha256", secret).update(body).digest("base64url")}`;
}

/** Chọn một giá trị trong Select của Ant Design có aria-label (nhấn vào khung, không vào ô nhập ẩn bên trong). */
export async function chooseOption(page, label, optionTitle) {
  await page.locator(`.ant-select[aria-label="${label}"]`).click();
  await page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden)").getByTitle(optionTitle, { exact: true }).click();
}

/** Trang không được cuộn ngang (chỉ bảng/biểu đồ được cuộn trong khung riêng). */
export async function horizontalOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}

export async function waitForCharts(page, min = 1) {
  await expect(async () => {
    expect(await page.locator("canvas").count()).toBeGreaterThanOrEqual(min);
  }).toPass();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
}
