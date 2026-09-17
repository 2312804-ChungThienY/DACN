/** E2E Giảng viên (SPEC 6.3): lọc ĐỎ → mở Modal → gửi can thiệp → thấy trong lịch sử; tiến độ lớp. */
import { expect, test } from "@playwright/test";
import { TEACHER, login, requirePassword, waitForCharts } from "./helpers.js";

test.beforeEach(async ({ page }) => {
  requirePassword(test);
  await login(page, TEACHER);
  await expect(page).toHaveURL(/\/teacher\/courses\/\d+\/risk$/);
});

test("lọc Nguy cơ cao → mở Modal → ghi nhận can thiệp → thấy trong lịch sử can thiệp", async ({ page }) => {
  await page.locator(".risk-card").filter({ hasText: "Nguy cơ cao" }).click();
  const table = page.locator(".ant-card", { has: page.getByText("Bảng cảnh báo sinh viên", { exact: true }) });
  await expect(table.locator("tbody tr.ant-table-row").first()).toBeVisible();
  for (const text of await table.locator("tbody .risk-badge").allInnerTexts()) expect(text).toContain("Nguy cơ cao");

  await table.getByRole("button", { name: "Chi tiết" }).first().click();
  const modal = page.getByRole("dialog").filter({ hasText: "So sánh với trung bình lớp" });
  await expect(modal.getByText(/Lý do:/)).toBeVisible();
  await expect(modal.locator("canvas")).toHaveCount(3);

  const note = `[e2e] Đã nhắc nhở trên lớp ${Date.now()}`;
  await modal.getByRole("button", { name: /Ghi chú/ }).click();
  const dialog = page.getByRole("dialog").filter({ hasText: "Nội dung" });
  await dialog.getByPlaceholder(/Đã nhắc nhở/).fill(note);
  await dialog.getByRole("button", { name: "Ghi nhận" }).click();
  await expect(page.getByText("Đã ghi nhận: Ghi chú")).toBeVisible();
  await expect(modal.getByText(note)).toBeVisible();
});

test("tiến độ lớp: progress bar, tiến độ theo chương và chuyển tuần/ngày", async ({ page }) => {
  await page.getByRole("link", { name: "Tiến độ lớp" }).click();
  await waitForCharts(page, 2);
  await expect(page.getByText("Hoàn thành hoạt động bắt buộc")).toBeVisible();
  await expect(page.getByText("Tuần 1", { exact: true })).toBeVisible();
  await page.getByText("Theo ngày", { exact: true }).first().click();
  await expect(page.getByText("Số SV có truy cập trong mỗi ngày")).toBeVisible();
});

test("đổi môn trên thanh tiêu đề", async ({ page }) => {
  const select = page.locator(".app-header .ant-select");
  const before = page.url();
  await select.click();
  const options = page.locator(".ant-select-item-option");
  await expect(options).toHaveCount(2);
  const second = await options.nth(1).innerText();
  await options.nth(1).click();
  await expect(select).toContainText(second.split(" – ")[0]);
  await expect(page).not.toHaveURL(before);
  await expect(page).toHaveURL(/\/teacher\/courses\/\d+\/risk$/);
  await expect(page.getByText("Bảng cảnh báo sinh viên", { exact: true })).toBeVisible();
});
