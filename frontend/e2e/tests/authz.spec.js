/**
 * Phân quyền (SPEC 6.3): GV A gọi API môn của GV B -> 403; GV gọi /admin/* -> 403; token hết hạn -> 401;
 * giao diện: phiên không hợp lệ quay về đăng nhập, GV không vào được trang Admin.
 */
import { expect, test } from "@playwright/test";
import { ADMIN, SESSION_KEY, TEACHER, apiToken, bearer, login, requirePassword, signToken } from "./helpers.js";

test.beforeEach(() => requirePassword(test));

test("GV gọi API môn của GV khác -> 403, môn không tồn tại -> 404", async ({ request }) => {
  const teacher = await apiToken(request, TEACHER);
  const admin = await apiToken(request, ADMIN);
  const mine = (await (await request.get("/api/v1/teacher/courses", { headers: bearer(teacher) })).json()).items.map((c) => c.course_id);
  const faculty = (await (await request.get("/api/v1/filters", { headers: bearer(admin) })).json()).faculties[0].id;
  const all = (await (await request.get(`/api/v1/admin/enrollment/faculties/${faculty}/courses`, { headers: bearer(admin) })).json()).items;
  const other = all.find((c) => !mine.includes(c.course_id));
  expect(other, "cần một môn không thuộc GV").toBeTruthy();

  for (const suffix of ["/students", "/risk-summary", "/progress", "/export"]) {
    const res = await request.get(`/api/v1/teacher/courses/${other.course_id}${suffix}`, { headers: bearer(teacher) });
    expect(res.status(), suffix).toBe(403);
  }
  expect((await request.get("/api/v1/teacher/courses/999999/students", { headers: bearer(teacher) })).status()).toBe(404);
});

test("GV gọi /admin/* -> 403, Admin gọi /teacher/* -> 403, không token -> 401", async ({ request }) => {
  const teacher = await apiToken(request, TEACHER);
  const admin = await apiToken(request, ADMIN);
  for (const url of ["/api/v1/admin/overview/kpis", "/api/v1/admin/traffic/hourly", "/api/v1/admin/reports/preview?report_type=risk"]) {
    expect((await request.get(url, { headers: bearer(teacher) })).status(), url).toBe(403);
    expect((await request.get(url)).status(), url).toBe(401);
  }
  expect((await request.get("/api/v1/teacher/courses", { headers: bearer(admin) })).status()).toBe(403);
});

test("token hết hạn hoặc bị sửa -> 401", async ({ request }) => {
  const token = await apiToken(request, TEACHER);
  const [header, payload, signature] = token.split(".");
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString());
  const tampered = `${header}.${Buffer.from(JSON.stringify({ ...claims, role: "ADMIN", sub: "2" })).toString("base64url")}.${signature}`;
  const res = await request.get("/api/v1/auth/me", { headers: bearer(tampered) });
  expect(res.status()).toBe(401);

  const secret = process.env.E2E_JWT_SECRET;
  test.skip(!secret, "Đặt E2E_JWT_SECRET để kiểm tra token hết hạn");
  const now = Math.floor(Date.now() / 1000);
  const expired = signToken({ sub: claims.sub, role: claims.role, iat: now - 7200, exp: now - 60 }, secret);
  const expiredRes = await request.get("/api/v1/auth/me", { headers: bearer(expired) });
  expect(expiredRes.status()).toBe(401);
  expect((await expiredRes.json()).detail).toBe("Phiên đăng nhập đã hết hạn");
});

test("giao diện: token không còn hợp lệ -> tự đăng xuất về trang đăng nhập", async ({ page }) => {
  await page.addInitScript(([key]) => {
    localStorage.setItem(key, JSON.stringify({
      token: "invalid.token.value", expiresAt: Date.now() + 3_600_000,
      user: { id: 3, username: "gv.tranminhhung", full_name: "GV", role: "TEACHER" },
    }));
  }, [SESSION_KEY]);
  await page.goto("/teacher");
  await expect(page).toHaveURL(/\/login$/);
});

test("giao diện: GV mở trang Admin bị chuyển về trang GV; mở môn của GV khác thấy thông báo", async ({ page, request }) => {
  await login(page, TEACHER);
  await page.goto("/admin/reports");
  await expect(page).toHaveURL(/\/teacher/);

  const admin = await apiToken(request, ADMIN);
  const teacher = await apiToken(request, TEACHER);
  const mine = (await (await request.get("/api/v1/teacher/courses", { headers: bearer(teacher) })).json()).items.map((c) => c.course_id);
  const faculty = (await (await request.get("/api/v1/filters", { headers: bearer(admin) })).json()).faculties[0].id;
  const other = (await (await request.get(`/api/v1/admin/enrollment/faculties/${faculty}/courses`, { headers: bearer(admin) })).json())
    .items.find((c) => !mine.includes(c.course_id));
  await page.goto(`/teacher/courses/${other.course_id}/risk`);
  await expect(page.getByText("Bạn không phụ trách môn học này")).toBeVisible();
});
