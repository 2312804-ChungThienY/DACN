/**
 * Màu & nhãn dùng chung.
 *
 * - Đèn giao thông: đúng màu của kế hoạch (SPEC 5.4) và LUÔN đi kèm biểu tượng + chữ,
 *   không bao giờ để màu đứng một mình.
 * - Chuỗi dữ liệu: 3 màu đầu của bảng màu phân loại đã kiểm định mù màu (skill dataviz),
 *   dùng theo thứ tự cố định, không xoay vòng.
 * - Chữ luôn dùng màu mực (ink/secondary/muted), không tô bằng màu dữ liệu.
 */
export const RISK = {
  RED: { color: "#D64545", tint: "#FBEAEA", ink: "#9B2C2C", icon: "●", label: "Nguy cơ cao" },
  YELLOW: { color: "#E0A100", tint: "#FDF3D8", ink: "#7A5800", icon: "▲", label: "Cần lưu ý" },
  GREEN: { color: "#2E9D5B", tint: "#E3F3EA", ink: "#1E6B3E", icon: "✔", label: "An toàn" },
};
export const RISK_LEVELS = ["RED", "YELLOW", "GREEN"];

export const CRITERIA = {
  attendance: "Vắng học",
  inactivity: "Không tương tác",
  assignment: "Thiếu bài tập",
};

/** Thứ tự cố định: 1 xanh dương, 2 cam, 3 xanh ngọc. */
export const SERIES = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
};

export const CHROME = {
  page: "#f5f7fb",
  surface: "#ffffff",
  ink: "#1f2937",
  secondary: "#52514e",
  muted: "#6b6a65",        // >= 4.5:1 trên nền trắng
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  neutral: "#c9c8c0",      // phần "không tương tác", "TB lớp" – đại lượng tham chiếu, lùi về sau
  peakWash: "rgba(214, 69, 69, 0.08)",
};

/** Thang tuần tự một màu (xanh dương, nhạt -> đậm) cho heatmap. */
export const SEQUENTIAL_BLUE = [
  "#eef5fd", "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
  "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
];

export const ACTIONS = {
  MESSAGE: { icon: "✉", label: "Gửi tin nhắn Moodle" },
  EMAIL: { icon: "📧", label: "Email" },
  NOTE: { icon: "📝", label: "Ghi chú" },
  MEETING: { icon: "📅", label: "Hẹn gặp" },
};

/** Màu nút/link chính: bậc 500 của thang xanh, chữ trắng đạt 5,5:1 (màu chuỗi #2a78d6 chỉ 4,47:1). */
export const UI_PRIMARY = "#256abf";

export const FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
