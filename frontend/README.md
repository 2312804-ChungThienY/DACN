# Frontend – React + Vite + Chart.js + Ant Design

Tài liệu thiết kế: [SPEC/KE_HOACH_TRIEN_KHAI.md](../SPEC/KE_HOACH_TRIEN_KHAI.md), Phần 5.2–5.5. API: [backend/README.md](../backend/README.md).

## Chạy

```powershell
# 1. API (cửa sổ 1, thư mục gốc dự án)
python -m uvicorn backend.app.main:app --port 8000

# 2. Frontend (cửa sổ 2)
cd frontend
npm install
npm run dev            # http://localhost:5173 – /api được proxy tới http://127.0.0.1:8000
```

Tài khoản: `admin` (Quản trị) và các giảng viên `gv.*`, tạo bằng `python -m backend.app.cli sync-users`.

Kiểm tra:

```powershell
npm test               # vitest: hàm định dạng, gộp dữ liệu biểu đồ
npm run build          # build production vào dist/
$env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
npm run smoke          # trình duyệt thật: đi qua các luồng chính, chụp màn hình vào e2e/screenshots,
                       # thất bại nếu có lỗi JavaScript / console / API >= 400
```

## Cấu trúc

```
src/
├── main.jsx, App.jsx          Provider (React Query, Ant Design tiếng Việt), định tuyến theo vai trò
├── api/client.js              axios + JWT; 401 -> đăng xuất; tải file Excel/PDF
├── api/hooks.js               React Query hook cho từng endpoint (realtime tự làm mới 60 giây)
├── auth/AuthContext.jsx       đăng nhập / đăng xuất, tự hết phiên theo hạn token
├── routes/ProtectedRoute.jsx  chặn trang theo vai trò
├── theme/tokens.js            màu đèn giao thông, màu chuỗi dữ liệu, màu khung
├── utils/format.js            định dạng vi-VN; tỷ lệ null = "Chưa có dữ liệu"
├── charts/                    setup Chart.js, TrafficDualAxisChart, EnrollmentStackedBar, TrafficHeatmap,
│                              RiskDoughnut, StudentCharts (so sánh SV–lớp, hoạt động theo tuần)
├── components/                AppHeader, TermFilterBar, HierarchyTable, StudentDetailModal, common (RiskBadge, KpiCard, ChartCard)
├── layouts/                   AdminLayout, TeacherLayout (chọn môn trên header)
└── pages/                     LoginPage; admin/ AdminOverview, AdminTraffic, AdminReports; teacher/ TeacherRisk, TeacherProgress
```

## Đối chiếu với kế hoạch

| Kế hoạch | Màn hình |
|---|---|
| 5.2 Admin – KPI Cards, Dual-axis Line (24h / 7 ngày, tô nền giờ cao điểm), Stacked Bar theo khoa (nhấn để drill-down), Bảng phân cấp Khoa ▸ Môn ▸ SV có breadcrumb, Heatmap giờ × thứ | `/admin` |
| 5.2 Tab Lưu lượng | `/admin/traffic` |
| 5.2 Trang Báo cáo: loại báo cáo + bộ lọc → Data Preview → Xuất Excel / PDF | `/admin/reports` |
| 5.3 GV – 3 thẻ đèn giao thông (nhấn để lọc), Doughnut (nhấn lát cắt để lọc) + đếm theo tiêu chí, bảng cảnh báo (tìm, lọc mức/tiêu chí, sắp xếp, Excel), Modal chi tiết (bar so sánh, line hoạt động có ●/○ điểm danh, bài tập ✔/✘, lịch sử cảnh báo, can thiệp trước, 4 nút hành động) | `/teacher/courses/:id/risk` |
| 5.3 Tiến độ lớp: progress bar hoàn thành / nộp bài / chuyên cần, tiến độ theo chương, line SV hoạt động theo tuần | `/teacher/courses/:id/progress` |

## Quy ước hiển thị

- Mức rủi ro luôn có **biểu tượng + chữ**: `● Nguy cơ cao` (#D64545), `▲ Cần lưu ý` (#E0A100), `✔ An toàn` (#2E9D5B), không bao giờ chỉ dùng màu. Người mù màu đỏ–lục không phân biệt được #D64545 với #2E9D5B (ΔE 3,5), nên biểu tượng và chữ là kênh nhận diện chính.
- Mọi biểu đồ có nút **"Biểu đồ | Bảng"** để xem cùng số liệu dạng bảng, và có tooltip. Biểu đồ đường có đường dóng dọc theo vị trí chuột.
- Tỷ lệ `null` từ API hiển thị **"Chưa có dữ liệu"** (hoặc "–" trong bảng), không hiển thị 0%.
- "Hôm nay" và các mốc ngày chọn nhanh lấy theo `as_of` của API (`LMS_AS_OF`), không theo đồng hồ máy người dùng.
- Biểu đồ lưu lượng dùng **2 trục** vì đề tài yêu cầu. Để tránh đọc nhầm thang: đường requests nét liền, đường online nét đứt, tiêu đề trục ghi rõ đại lượng, tooltip hiện đủ cả hai giá trị.
