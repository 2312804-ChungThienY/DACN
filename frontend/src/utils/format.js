/** Định dạng số, ngày theo vi-VN. Giá trị null của tỷ lệ = "chưa có dữ liệu", khác với 0%. */
import dayjs from "dayjs";

export const NO_DATA = "Chưa có dữ liệu";
export const DOW_LABELS = ["", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"];

const intFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
const compactFormat = new Intl.NumberFormat("vi-VN", { notation: "compact", maximumFractionDigits: 1 });

export function fmtInt(value) {
  return value == null || Number.isNaN(Number(value)) ? "–" : intFormat.format(Number(value));
}

export function fmtDecimal(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return "–";
  return new Intl.NumberFormat("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
}

export function fmtPercent(value, digits = 1, empty = NO_DATA) {
  return value == null ? empty : `${fmtDecimal(value, digits)}%`;
}

export function fmtCompact(value) {
  return value == null ? "–" : compactFormat.format(Number(value));
}

export function fmtDate(value) {
  return value ? dayjs(value).format("DD/MM/YYYY") : "–";
}

export function fmtShortDate(value) {
  return value ? dayjs(value).format("DD/MM") : "–";
}

export function fmtDateTime(value) {
  return value ? dayjs(value).format("DD/MM/YYYY HH:mm") : "–";
}

export function fmtHour(value) {
  return value ? dayjs(value).format("HH:mm") : "–";
}

export function fmtDaysSince(days) {
  if (days == null) return "Chưa truy cập";
  if (days === 0) return "Hôm nay";
  return `${fmtInt(days)} ngày trước`;
}

/** Tỷ lệ % (0–100) hoặc null khi mẫu số bằng 0. */
export function share(part, total) {
  return total ? (100 * part) / total : null;
}

/** Tên file từ header Content-Disposition (ưu tiên filename* UTF-8). */
export function filenameFromDisposition(header, fallback = "bao_cao") {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      /* rơi xuống filename thường */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : fallback;
}

/** Gộp các snapshot rủi ro liên tiếp cùng mức -> các điểm đổi mức (dòng "Lịch sử cảnh báo" trong Modal). */
export function riskTransitions(history) {
  const points = [];
  for (const item of history ?? []) {
    if (!points.length || points[points.length - 1].risk_level !== item.risk_level) points.push(item);
  }
  return points;
}

/** Các khoảng giờ liên tiếp có is_peak_hour = true -> [{from, to}] theo chỉ số điểm. */
export function peakRanges(items) {
  const ranges = [];
  let start = null;
  (items ?? []).forEach((item, index) => {
    if (item.is_peak_hour && start === null) start = index;
    if (!item.is_peak_hour && start !== null) {
      ranges.push({ from: start, to: index - 1 });
      start = null;
    }
  });
  if (start !== null) ranges.push({ from: start, to: items.length - 1 });
  return ranges;
}
