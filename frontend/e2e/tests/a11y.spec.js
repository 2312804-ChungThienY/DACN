/**
 * Khả năng tiếp cận (SPEC 6.3): axe-core với bộ quy tắc WCAG 2.1 A/AA (gồm tương phản màu).
 * Không chấp nhận vi phạm mức "serious" hoặc "critical". Nội dung vẽ trên canvas không được axe kiểm tra –
 * biểu đồ có role="img" + aria-label và nút xem dạng bảng.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { ADMIN, TEACHER, login, requirePassword, waitForCharts } from "./helpers.js";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function audit(page, testInfo, name) {
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  await testInfo.attach(`axe-${name}.json`, { body: JSON.stringify(result.violations, null, 2), contentType: "application/json" });
  const blocking = result.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  const summary = blocking.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} phần tử – ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
  expect(summary, `Vi phạm WCAG trên ${name}`).toEqual([]);
}

test("trang đăng nhập", async ({ page }, testInfo) => {
  await page.goto("/login");
  await audit(page, testInfo, "login");
});

test("Admin – tổng quan", async ({ page }, testInfo) => {
  requirePassword(test);
  await login(page, ADMIN);
  await waitForCharts(page, 3);
  await audit(page, testInfo, "admin-overview");
});

test("Giảng viên – cảnh báo và Modal chi tiết", async ({ page }, testInfo) => {
  requirePassword(test);
  await login(page, TEACHER);
  await expect(page.getByText("Bảng cảnh báo sinh viên", { exact: true })).toBeVisible();
  await waitForCharts(page, 1);
  await audit(page, testInfo, "teacher-risk");
  await page.getByRole("button", { name: "Chi tiết" }).first().click();
  await expect(page.getByRole("dialog").getByText("So sánh với trung bình lớp")).toBeVisible();
  await page.waitForTimeout(600);
  await audit(page, testInfo, "teacher-modal");
});
