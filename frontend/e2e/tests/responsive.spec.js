/** Responsive (SPEC 6.3): 1920, 1366, 768, 390 px – biểu đồ co giãn trong khung, trang không cuộn ngang, bảng cuộn trong khung. */
import { expect, test } from "@playwright/test";
import { ADMIN, TEACHER, horizontalOverflow, login, requirePassword, waitForCharts } from "./helpers.js";

const WIDTHS = [1920, 1366, 768, 390];
const PAGES = [
  { name: "admin-tong-quan", user: ADMIN, path: "/admin", charts: 3, ready: "Tổng môn học" },
  { name: "gv-canh-bao", user: TEACHER, path: "/teacher", charts: 1, ready: "Bảng cảnh báo sinh viên" },
  { name: "gv-tien-do", user: TEACHER, path: null, charts: 2, ready: "Tiến độ theo chương / tuần" },
];

for (const width of WIDTHS) {
  for (const target of PAGES) {
    test(`${target.name} @ ${width}px`, async ({ page }, testInfo) => {
      requirePassword(test);
      await page.setViewportSize({ width, height: width < 500 ? 844 : 900 });
      await login(page, target.user);
      if (target.path) await page.goto(target.path);
      else await page.getByRole("link", { name: "Tiến độ lớp" }).click();
      await expect(page.getByText(target.ready, { exact: true }).first()).toBeVisible();
      await waitForCharts(page, target.charts);

      expect(await horizontalOverflow(page), "trang không được cuộn ngang").toBeLessThanOrEqual(1);
      const canvases = await page.locator("canvas").evaluateAll((els) => els.map((c) => c.getBoundingClientRect().width));
      for (const w of canvases) {
        expect(w).toBeGreaterThan(0);
        expect(w).toBeLessThanOrEqual(width);
      }
      await expect(page.locator(".app-nav a").first()).toBeInViewport();
      await testInfo.attach(`${target.name}-${width}`, { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
    });
  }
}
