/** E2E Admin (SPEC 6.3): lọc HK1 → nhấn cột khoa → bảng drill-down hiện môn → Export Excel; lưu lượng; báo cáo PDF. */
import { expect, test } from "@playwright/test";
import { ADMIN, chooseOption, login, requirePassword, waitForCharts } from "./helpers.js";

test.beforeEach(async ({ page }) => {
  requirePassword(test);
  await login(page, ADMIN);
  await expect(page).toHaveURL(/\/admin$/);
});

test("lọc HK1 → nhấn cột khoa trên stacked bar → drill-down môn → xuất Excel", async ({ page }) => {
  await waitForCharts(page, 3);
  await chooseOption(page, "Học kỳ", "HK1");
  await expect(page.getByText("2026-2027 · HK1")).toBeVisible();

  const barCard = page.locator(".ant-card", { has: page.getByText("SV đăng ký và tương tác theo khoa", { exact: true }) });
  const canvas = barCard.locator("canvas");
  const box = await canvas.boundingBox();
  await canvas.click({ position: { x: box.width * 0.6, y: box.height * 0.52 } });

  const hierarchy = page.locator(".ant-card", { has: page.getByText("Thống kê phân cấp: Khoa ▸ Môn ▸ Sinh viên") });
  await expect(hierarchy.locator(".ant-breadcrumb")).toContainText("Khoa Công nghệ Thông tin");
  await expect(hierarchy.getByRole("button", { name: "Xem SV" })).toHaveCount(15);

  await page.getByRole("button", { name: /Export/ }).click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByText("Báo cáo quy mô & tương tác – Excel").click(),
  ]);
  expect(download.suggestedFilename()).toBe("bao_cao_enrollment_HK1_2026-2027.xlsx");
  const file = await download.path();
  expect(file).toBeTruthy();
});

test("drill-down tới sinh viên và lọc SV không tương tác", async ({ page }) => {
  const hierarchy = page.locator(".ant-card", { has: page.getByText("Thống kê phân cấp: Khoa ▸ Môn ▸ Sinh viên") });
  await hierarchy.getByRole("row", { name: /Khoa Công nghệ Thông tin/ }).click();
  await hierarchy.getByRole("button", { name: "Xem SV" }).first().click();
  await expect(hierarchy.getByText(/SV đăng ký · .* có tương tác/)).toBeVisible();
  await hierarchy.getByText("Không tương tác", { exact: true }).click();
  await expect(hierarchy.locator("tbody tr.ant-table-row").first()).toBeVisible();
  const tags = await hierarchy.locator("tbody tr.ant-table-row").allInnerTexts();
  expect(tags.length).toBeGreaterThan(0);
  for (const row of tags) expect(row).toContain("Chưa");
});

test("trang lưu lượng: biểu đồ 2 trục, heatmap và thẻ thời gian thực", async ({ page }) => {
  await page.getByRole("link", { name: "Lưu lượng" }).click();
  await waitForCharts(page, 2);
  await expect(page.getByText("Online hiện tại")).toBeVisible();
  await expect(page.getByText("Top 10 giờ đông nhất")).toBeVisible();
  await expect(page.locator("tbody tr.ant-table-row")).toHaveCount(10);
});

test("báo cáo cảnh báo: lọc mức Nguy cơ cao → xem trước → xuất PDF", async ({ page }) => {
  await page.getByRole("link", { name: "Báo cáo" }).click();
  await chooseOption(page, "Loại báo cáo", "Cảnh báo sinh viên nguy cơ");
  await chooseOption(page, "Mức rủi ro", "● Nguy cơ cao");
  await page.getByRole("button", { name: "Xem trước" }).click();
  await expect(page.getByText("Báo cáo cảnh báo sinh viên nguy cơ")).toBeVisible();
  const badges = page.locator("tbody .risk-badge");
  await expect(badges.first()).toBeVisible();
  for (const text of await badges.allInnerTexts()) expect(text).toContain("Nguy cơ cao");

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Xuất PDF/ }).click()]);
  expect(download.suggestedFilename()).toMatch(/^bao_cao_risk_HK1_2026-2027\.pdf$/);
});
