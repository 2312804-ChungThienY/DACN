/**
 * Đăng ký Chart.js một lần + mặc định giao diện theo skill dataviz:
 * lưới/trục mảnh và lùi về sau, chữ màu mực (không tô màu dữ liệu), đường 2px, điểm >= 8px, tooltip nền trắng.
 */
import {
  ArcElement, BarElement, CategoryScale, Chart, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from "chart.js";
import { MatrixController, MatrixElement } from "chartjs-chart-matrix";
import annotationPlugin from "chartjs-plugin-annotation";
import { CHROME, FONT_FAMILY } from "../theme/tokens.js";

Chart.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Tooltip, Legend, Filler,
  MatrixController, MatrixElement, annotationPlugin);

Chart.defaults.font.family = FONT_FAMILY;
Chart.defaults.font.size = 12;
Chart.defaults.color = CHROME.secondary;
Chart.defaults.borderColor = CHROME.grid;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation.duration = 250;
Chart.defaults.elements.line.borderWidth = 2;
Chart.defaults.elements.line.borderCapStyle = "round";
Chart.defaults.elements.line.borderJoinStyle = "round";
Chart.defaults.elements.point.radius = 0;
Chart.defaults.elements.point.hoverRadius = 5;
Chart.defaults.elements.point.hitRadius = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.boxHeight = 8;
Chart.defaults.plugins.legend.labels.color = CHROME.ink;
Chart.defaults.plugins.tooltip.backgroundColor = "#ffffff";
Chart.defaults.plugins.tooltip.titleColor = CHROME.secondary;
Chart.defaults.plugins.tooltip.bodyColor = CHROME.ink;
Chart.defaults.plugins.tooltip.borderColor = CHROME.grid;
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.boxPadding = 4;
Chart.defaults.plugins.tooltip.usePointStyle = true;

/** Trục số/danh mục chuẩn: lưới mảnh 1px, trục màu nhạt, nhãn màu muted. */
export function axis(overrides = {}) {
  return {
    grid: { color: CHROME.grid, drawTicks: false, ...(overrides.grid ?? {}) },
    border: { color: CHROME.axis, ...(overrides.border ?? {}) },
    ticks: { color: CHROME.muted, padding: 6, ...(overrides.ticks ?? {}) },
    ...Object.fromEntries(Object.entries(overrides).filter(([k]) => !["grid", "border", "ticks"].includes(k))),
  };
}

export const vnNumber = (value) => new Intl.NumberFormat("vi-VN").format(value);

/** Đường dọc mảnh tại vị trí tooltip (biểu đồ đường): người đọc nhắm vào mốc thời gian, không phải nét 2px. */
export const crosshair = {
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const active = chart.tooltip?.getActiveElements?.() ?? [];
    if (!active.length) return;
    const { x } = active[0].element;
    const { top, bottom } = chart.chartArea;
    const { ctx } = chart;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.lineWidth = 1;
    ctx.strokeStyle = CHROME.axis;
    ctx.stroke();
    ctx.restore();
  },
};
