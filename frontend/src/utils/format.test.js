import { describe, expect, it } from "vitest";
import {
  NO_DATA, filenameFromDisposition, fmtDaysSince, fmtInt, fmtPercent, peakRanges, riskTransitions, share,
} from "./format.js";

describe("định dạng số vi-VN", () => {
  it("số nguyên có dấu chấm ngăn cách hàng nghìn", () => {
    expect(fmtInt(1234567)).toBe("1.234.567");
    expect(fmtInt(null)).toBe("–");
  });
  it("null là chưa có dữ liệu, 0 là 0%", () => {
    expect(fmtPercent(null)).toBe(NO_DATA);
    expect(fmtPercent(0)).toBe("0,0%");
    expect(fmtPercent(41.666, 2)).toBe("41,67%");
  });
  it("tỷ lệ với mẫu số 0", () => {
    expect(share(3, 0)).toBeNull();
    expect(share(1, 4)).toBe(25);
  });
  it("số ngày chưa truy cập", () => {
    expect(fmtDaysSince(null)).toBe("Chưa truy cập");
    expect(fmtDaysSince(0)).toBe("Hôm nay");
    expect(fmtDaysSince(16)).toBe("16 ngày trước");
  });
});

describe("tên file tải về", () => {
  it("ưu tiên filename* UTF-8", () => {
    const header = "attachment; filename=\"canh_bao_IT001.xlsx\"; filename*=UTF-8''canh_bao_IT001.xlsx";
    expect(filenameFromDisposition(header)).toBe("canh_bao_IT001.xlsx");
  });
  it("không có header -> tên mặc định", () => {
    expect(filenameFromDisposition(undefined, "x.pdf")).toBe("x.pdf");
  });
});

describe("gộp dữ liệu cho biểu đồ", () => {
  it("chỉ giữ các điểm đổi mức rủi ro", () => {
    const history = ["GREEN", "GREEN", "YELLOW", "YELLOW", "RED", "RED", "YELLOW"].map((risk_level, i) => ({ date: `d${i}`, risk_level }));
    expect(riskTransitions(history).map((p) => `${p.date}:${p.risk_level}`)).toEqual(["d0:GREEN", "d2:YELLOW", "d4:RED", "d6:YELLOW"]);
  });
  it("khoảng giờ cao điểm liên tiếp", () => {
    const flags = [false, true, true, false, true].map((is_peak_hour) => ({ is_peak_hour }));
    expect(peakRanges(flags)).toEqual([{ from: 1, to: 2 }, { from: 4, to: 4 }]);
  });
});
