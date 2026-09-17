# KẾT QUẢ KIỂM THỬ VÀ ĐO HIỆU NĂNG

> Đối chiếu với Phần 6 của [kế hoạch](../SPEC/KE_HOACH_TRIEN_KHAI.md) · Đo ngày 17/09/2026
> Máy đo: Intel Core i5-12450H (12 luồng), 16 GB RAM, Windows 11, PostgreSQL 18 cài trực tiếp trên máy.
> Dữ liệu thô của từng phép đo: thư mục [perf/results/](../perf/results/)

---

## 1. TỔNG KẾT

| Nhóm | Số lượng | Kết quả |
|---|---|---|
| pytest – CSDL, ETL, mock data, tích hợp, API, bảo mật | 248 | Tất cả đạt |
| vitest – hàm định dạng và gộp dữ liệu biểu đồ | 8 | Tất cả đạt |
| Playwright – luồng Admin/Giảng viên, phân quyền, responsive, WCAG | 27 | Tất cả đạt (chạy trên bản Docker) |
| Kiểm tra nhanh giao diện bằng trình duyệt (`npm run smoke`) | 11 bước | Không lỗi JavaScript, console hay API |

| Mục tiêu hiệu năng (kế hoạch 6.2) | Kết quả đo | Đạt |
|---|---|---|
| Mỗi truy vấn SQL ≤ 100 ms, không Seq Scan trên bảng lớn (x1 và x10) | chậm nhất 1,71 ms (x1) và 8,55 ms (x10) | ✔ |
| API: p95 < 500 ms, p99 < 1 s, lỗi < 0,1% (50 người dùng đồng thời) | x1: p95 16 ms, p99 230 ms · x10: p95 22 ms, p99 37 ms · 0 lỗi | ✔ |
| Tải trang: biểu đồ đầu < 1 s, LCP < 2,5 s, TTI < 3 s (cache lạnh) | 335–409 ms · 360–428 ms · 389–461 ms | ✔ |
| ETL: traffic < 30 s, risk < 5 phút, nightly < 20 phút | 0,10 s · 60 s · 60 s | ✔ |
| Xuất file: Excel 10.000 dòng và PDF 500 dòng < 5 s | Excel 23.830 dòng 4,48 s · PDF 408 dòng 0,53 s | ✔ |

---

## 2. KIỂM THỬ TÍNH ĐÚNG ĐẮN DỮ LIỆU (6.1)

### 2.1 Unit test luật rủi ro

`tests/etl/test_risk_rules.py` – 12 hàm test, chạy thành nhiều ca bằng tham số hóa. Các ca biên được kiểm tra:

- Vắng đúng 15% và đúng 30% (ranh giới giữa các mức); thiếu đúng 20% và đúng 60%.
- Môn chưa có buổi điểm danh (0 buổi) → tiêu chí C1 = 0 và `attendance_status = NO_DATA`.
- `days_since_last_access = None` (chưa từng truy cập) → C2 = 2.
- Trung vị lớp bằng 0 (đầu học kỳ chưa ai truy cập).
- Dữ liệu vào không hợp lệ (số buổi vắng lớn hơn số buổi, số âm) → báo lỗi rõ ràng.
- Luật xếp mức gốc của kế hoạch vẫn cấu hình lại được.

So sánh tỷ lệ với ngưỡng bằng phân số chính xác (`Fraction`), nên "vắng đúng 3/10 buổi = 30%" luôn cho kết quả đúng, không phụ thuộc sai số dấu phẩy động.

### 2.2 Đối soát với Moodle

`tests/integration/test_etl_pipeline.py`. Với **5 môn lấy ngẫu nhiên**, test viết lại truy vấn theo đúng Phần 1 của kế hoạch (không dùng lại SQL của ETL) rồi so với bảng fact:

| Chỉ số đối soát | Sai lệch |
|---|---|
| Số sinh viên ghi danh và số sinh viên có tương tác của môn | 0 |
| Số buổi điểm danh và số buổi vắng của từng sinh viên | 0 |
| Số bài đã tới hạn và số bài thiếu của từng sinh viên | 0 |
| Số request và số người dùng theo từng giờ (3 ngày gần nhất) | 0 |

### 2.3 Đối chiếu với "đáp án" (ground truth)

So mức rủi ro hệ thống tính với hồ sơ hành vi đã gieo khi sinh dữ liệu, trên 2.383 cặp sinh viên–môn tại ngày 06/11/2026:

| Đáp án \ Hệ thống | XANH | VÀNG | ĐỎ |
|---|---|---|---|
| GREEN | 1.279 | 247 | 0 |
| YELLOW | 29 | 412 | 60 |
| RED | 0 | 8 | **348** |

- **Recall (ĐỎ) = 97,8%** (mục tiêu ≥ 90%)
- **Precision (ĐỎ) = 85,3%** (mục tiêu ≥ 80%)

Không có sinh viên nhóm RED nào bị xếp nhầm xuống XANH; 8 em còn lại vẫn được cảnh báo ở mức VÀNG.

### 2.4 Chạy lại không đổi kết quả (idempotency)

Chạy lại lần lượt 3 job trên cùng dữ liệu: `rows_loaded = 0` và checksum `md5(string_agg(row_to_json(t)))` của cả 3 bảng fact không đổi.

### 2.5 Cập nhật tăng dần đúng

Chèn thêm 1.000 dòng nhật ký vào một giờ cụ thể rồi chạy job `traffic`: **chỉ đúng giờ đó thay đổi**, watermark tăng đúng bằng `MAX(id)` mới. Sau khi xóa dữ liệu chèn thêm và chạy lại, số liệu trở về đúng như trước.

### 2.6 Ràng buộc dữ liệu

`tests/database/test_analytics_schema.py` – 30 ca thử ghi dữ liệu sai vào từng ràng buộc và bắt buộc CSDL phải từ chối: mức rủi ro lạ, học kỳ 4, năm học sai dạng, tỷ lệ 120%, số bài thiếu không khớp, trễ hạn nhiều hơn đã nộp, `attendance_status` không khớp điểm C1, `absence_rate` khác NULL khi chưa có buổi điểm danh, `access_count_7d > access_count_14d`, điểm tiêu chí ngoài 0–2, mảng `teacher_ids` chứa NULL, JSONB không phải mảng…

### 2.7 Kiểm thử thủ công với giảng viên (UAT)

**Chưa thực hiện** – phần này cần giảng viên thật đánh giá danh sách ĐỎ của lớp mình (mục tiêu: đồng ý ≥ 80% trường hợp).

---

## 3. HIỆU NĂNG (6.2)

### 3.1 Bộ dữ liệu dùng để đo

| Bộ | Cách tạo | Quy mô |
|---|---|---|
| **x1** | Dữ liệu demo hiện có (`lms_analytics`) | 145.846 dòng cảnh báo · 915 dòng tiến độ · 15 môn · 322 MB |
| **x10** | `python -m perf.build_x10` nhân 10 lần bảng fact sang CSDL riêng `lms_analytics_x10` | 1.458.460 dòng cảnh báo · 9.150 dòng tiến độ · 150 môn · 10 khoa · 2.588 MB |
| **ETL** | `python -m perf.etl_bench prepare` sinh Moodle riêng `moodle_src_x4` | 2.000 sinh viên · 9.677 lượt ghi danh còn hiệu lực · 4.974.543 dòng nhật ký · 2.001 MB |

### 3.2 Truy vấn SQL – `EXPLAIN (ANALYZE, BUFFERS)`

Script `perf/explain_queries.py` gọi lần lượt 14 endpoint chính, **ghi lại đúng câu SQL mà API gửi xuống CSDL** (kèm tham số), rồi chạy lại mỗi câu 5 lần với `EXPLAIN (ANALYZE, BUFFERS)`.

| Bộ | Số câu truy vấn | Chậm nhất (trung vị) | Chậm nhất (lần tệ nhất) | Seq Scan trên bảng > 100.000 dòng |
|---|---|---|---|---|
| x1 | 40 | 1,71 ms | 1,79 ms | không |
| x10 | 40 | 8,55 ms | 11,28 ms | không |

Năm truy vấn chậm nhất ở bộ x10:

| Truy vấn (endpoint) | Trung vị | Index sử dụng |
|---|---|---|
| `GET /admin/enrollment/by-faculty` | 8,55 ms | `pk_fact_course_progress_daily` |
| `GET /admin/overview/kpis` | 8,13 ms | `pk_fact_course_progress_daily` |
| `GET /admin/reports/preview` (risk, ĐỎ) | 8,05 ms | `ix_risk_course_date_level`, `ix_risk_red_partial` |
| `GET /teacher/courses/{id}/students` | 3,19 ms | `ix_risk_course_date_level`, `ix_risk_teacher_gin` |
| `GET /teacher/courses/{id}/students/{uid}/compare` | 3,07 ms | `ix_cpd_teacher_gin`, `ix_risk_teacher_gin` |

Ghi chú: PostgreSQL chọn Seq Scan trên `fact_course_progress_daily` (9.150 dòng ở bộ x10) là **hợp lý**, vì bảng này nhỏ. Tiêu chí "không Seq Scan" chỉ áp dụng cho bảng trên 100.000 dòng, tức `fact_student_risk_summary`.

### 3.3 API dưới tải – Locust

50 người dùng đồng thời (40 giảng viên, 10 quản trị), think-time 2–5 giây, API chạy 2 worker. Locust và API chạy **trên cùng một máy** nên số đo là cận trên.

| Bộ | Thời lượng | Số request | Lỗi | Trung vị | **p95** | **p99** | Chậm nhất | Throughput |
|---|---|---|---|---|---|---|---|---|
| x1 | 5 phút | 4.001 | **0** | 9 ms | **16 ms** | 230 ms | 439 ms | 13,4 req/s |
| x10 | 10 phút | 16.301 | **0** | 10 ms | **22 ms** | 37 ms | 415 ms | 27,2 req/s |

Trong toàn bộ 297 + 595 khoảng đo 1 giây, **không khoảng nào có p95 vượt 500 ms**.

Giá trị p99 của bộ x1 (230 ms) đến từ 50 lần gọi `POST /auth/login`: bcrypt cố ý tốn khoảng 230 ms mỗi lần để chống dò mật khẩu. Các endpoint đọc dữ liệu đều có p99 dưới 40 ms.

#### Một lỗi hiệu năng đã phát hiện và sửa: tranh chấp keep-alive

Lần đo đầu tiên có vài request lẻ mất **30–69 giây** dù p95 vẫn rất thấp. Quá trình truy tìm:

1. Bật `log_min_duration_statement = 1s` của PostgreSQL rồi chạy lại tải → **không có truy vấn nào vượt 1 giây**, và log không có checkpoint hay autovacuum chậm. Vậy nguyên nhân không nằm ở CSDL.
2. Đặc điểm số liệu (30–69 giây, đúng bậc thang hết giờ của TCP) dẫn tới giả thuyết: uvicorn mặc định đóng kết nối nhàn rỗi sau **5 giây**, trong khi người dùng Dashboard có khoảng nghỉ 2–5 giây; thỉnh thoảng client gửi request đúng lúc server đóng kết nối và phải chờ TCP hết giờ.
3. Chạy lại với `--timeout-keep-alive 65`: request chậm nhất giảm từ **69.006 ms xuống 552 ms**.

Đã áp dụng `--timeout-keep-alive 65` cho lệnh chạy API trong `docker-compose.yml` và ghi vào tài liệu Backend.

### 3.4 Tải trang – bản build production

Đo bằng Playwright trên `vite preview`, mỗi trang 5 lần, **mỗi lần một hồ sơ trình duyệt mới (cache lạnh)**, phiên đăng nhập đặt sẵn để chỉ đo trang Dashboard.

| Trang | Hồ sơ máy | Biểu đồ đầu tiên | LCP | TTI (xấp xỉ) | TBT | Tải về |
|---|---|---|---|---|---|---|
| Tổng quan (Admin) | bình thường | **335 ms** | **360 ms** | **389 ms** | 27 ms | 527 KB |
| Cảnh báo (Giảng viên) | bình thường | **409 ms** | **428 ms** | **461 ms** | 63 ms | 500 KB |
| Tổng quan (Admin) | CPU chậm 4× | 1.414 ms | 1.456 ms | 2.154 ms | 1.120 ms | 527 KB |
| Cảnh báo (Giảng viên) | CPU chậm 4× | 2.075 ms | 2.140 ms | 2.187 ms | 1.359 ms | 500 KB |

Trên máy bình thường đạt cả ba mục tiêu. Hồ sơ "CPU chậm 4×" là kịch bản khắc nghiệt tự thêm (giả lập máy yếu): LCP và TTI vẫn đạt, riêng "biểu đồ đầu tiên" vượt 1 giây do phải phân tích gói JavaScript 924 KB của Ant Design. Hướng cải thiện: tách nhỏ gói hoặc thay bằng bộ thành phần nhẹ hơn.

### 3.5 Xuất file

| Trường hợp | Số dòng | Trung vị 3 lần | Dung lượng | Mục tiêu |
|---|---|---|---|---|
| Excel – cảnh báo toàn bộ, bộ x10 | 23.830 | **4,48 s** | 1.573 KB | Excel 10.000 dòng < 5 s ✔ |
| PDF – cảnh báo mức ĐỎ, bộ x1 | 408 | **0,53 s** | 166 KB | PDF 500 dòng < 5 s ✔ |
| PDF – cảnh báo toàn bộ, bộ x1 | 2.383 | 2,86 s | 514 KB | (ngoài mục tiêu, để tham khảo) |

### 3.6 ETL

`python -m perf.etl_bench measure` – mỗi job chạy 3 lần trên CSDL riêng, thời gian lấy từ `etl_run_log` (không tính thời gian khởi động Python).

| Job | Trung vị | Mục tiêu | Đạt |
|---|---|---|---|
| `traffic` (tăng dần mỗi 5 phút) | **0,10 s** | < 30 s | ✔ |
| `student_risk` (9.677 lượt ghi danh) | **60,05 s** | < 5 phút | ✔ |
| `course_progress` | 62,76 s | – | – |
| `nightly` (chốt số liệu cả ngày) | **60,12 s** | < 20 phút | ✔ |

Tham chiếu thêm: nạp lịch sử 61 ngày (`backfill`) mất 340 giây trên dữ liệu demo khi chạy trực tiếp trên Windows, và **111 giây** khi chạy trong container Linux.

---

## 4. GIAO DIỆN, PHÂN QUYỀN, KHẢ DỤNG (6.3)

### 4.1 E2E – Playwright, chạy trên bản Docker

27 test, tất cả đạt:

| Nhóm | Nội dung |
|---|---|
| Admin | Lọc HK1 → nhấn cột khoa trên biểu đồ cột chồng → bảng drill-down hiện 15 môn → tải Excel về máy (kiểm tra đúng tên file). Drill-down tới danh sách sinh viên, lọc "Không tương tác". Trang Lưu lượng có đủ biểu đồ, heatmap, bảng Top 10. Báo cáo: chọn loại "Cảnh báo sinh viên", lọc mức ĐỎ, xem trước rồi tải PDF |
| Giảng viên | Lọc mức Nguy cơ cao → mở Modal chi tiết (kiểm tra có đủ 3 biểu đồ) → ghi nhận can thiệp "Ghi chú" → can thiệp hiện ngay trong lịch sử. Trang Tiến độ lớp, chuyển tuần/ngày. Đổi môn trên thanh tiêu đề |
| Phân quyền | GV gọi API môn của GV khác → 403 (4 endpoint); môn không tồn tại → 404; GV gọi `/admin/*` → 403; Admin gọi `/teacher/*` → 403; không token → 401; token bị sửa → 401; token hết hạn → 401 kèm thông báo "Phiên đăng nhập đã hết hạn"; phiên hỏng trong trình duyệt → tự quay về trang đăng nhập; GV mở `/admin` → bị chuyển về trang GV |
| Responsive | 1920, 1366, 768, 390 px × 3 trang: trang không cuộn ngang, biểu đồ co giãn trong khung, thanh điều hướng luôn nhìn thấy; kèm ảnh chụp từng kích thước |
| Khả năng tiếp cận | axe-core với bộ quy tắc WCAG 2.1 A/AA trên 4 màn hình (đăng nhập, tổng quan, cảnh báo, Modal) |

### 4.2 Các lỗi khả năng tiếp cận đã phát hiện và sửa

| Lỗi axe phát hiện | Sửa |
|---|---|
| `color-contrast` – chữ trắng trên nút xanh `#2a78d6` chỉ đạt 4,47:1 | Đổi màu nút/link chính sang `#256abf` (5,5:1); màu `#2a78d6` vẫn dùng cho đường/cột biểu đồ |
| `color-contrast` – chữ phụ, chú thích, breadcrumb dùng xám mặc định của Ant Design | Đặt lại token `colorTextDescription`, `colorTextPlaceholder`, và biến CSS `--muted` thành `#6b6a65` |
| `color-contrast` – thẻ trạng thái bài tập dùng màu preset (chữ xanh lá/cam/đỏ trên nền nhạt) | Đổi sang nền nhạt + chữ đậm cùng tông, giống huy hiệu mức rủi ro |
| `aria-progressbar-name` – thanh tiến độ không có tên cho trình đọc màn hình | Thêm `aria-label` mô tả đủ nghĩa cho mọi thanh tiến độ |

Sau khi sửa: **không còn vi phạm mức serious hoặc critical** trên cả 4 màn hình.

Ngoài ra, bộ kiểm tra nhanh bằng trình duyệt đã phát hiện và sửa: tiêu đề bảng cảnh báo bị ẩn trên màn hình điện thoại, hai cảnh báo deprecation của Ant Design, và các ô lọc bị cắt chữ.

### 4.3 Bảo mật cơ bản

`tests/backend/test_security_api.py` và `test_auth_api.py`:

| Kiểm tra | Kết quả |
|---|---|
| CORS chỉ cho origin đã cấu hình; origin lạ không nhận header cho phép | Đạt |
| Header `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` trên response API | Đạt |
| Chuỗi tấn công SQL trong ô tìm kiếm (`' OR 1=1 --`, `%' UNION SELECT`, `\`) được coi là văn bản, trả 0 kết quả | Đạt |
| Tham số có cấu trúc sai (`sort`, `order`, `risk_level`, `page_size`, id không phải số) → 422 | Đạt |
| Mọi mật khẩu trong CSDL là hash bcrypt (60 ký tự, tiền tố `$2`) | Đạt |
| Thông báo lỗi không lộ câu SQL hay vết stack | Đạt |
| Đăng nhập sai 5 lần trong 5 phút → 429 kèm `Retry-After` | Đạt |
| Vai trò đọc lại từ CSDL mỗi request (token ghi `role=ADMIN` cho tài khoản GV vẫn bị chặn) | Đạt |

---

## 5. TRIỂN KHAI (6.4)

`docker compose --env-file docker/.env up --build -d` dựng đủ 5 dịch vụ và chạy được ngay:

| Dịch vụ | Trạng thái sau khi dựng |
|---|---|
| `db` (PostgreSQL 18) | healthy |
| `init` (migrate → mock data → backfill → tài khoản) | chạy xong, mã thoát 0; backfill 61 ngày mất **111 giây** |
| `backend` (FastAPI, 2 worker) | healthy |
| `etl` (APScheduler) | running |
| `web` (Nginx phục vụ bản build React, proxy `/api`) | running |

Kiểm chứng: **toàn bộ 27 test E2E chạy trên chính hệ thống Docker này đều đạt**, và bộ ảnh chụp màn hình trong [docs/images/](images/) cũng lấy từ bản Docker.

Chạy lại `up` lần hai: dịch vụ `init` tự phát hiện CSDL đã có dữ liệu và bỏ qua bước sinh mock data.

---

## 6. NHỮNG GÌ CHƯA LÀM

| Hạng mục | Lý do |
|---|---|
| UAT với 2–3 giảng viên thật | Cần người dùng thật tham gia |
| Lighthouse chính thức | Đang đo bằng Playwright (LCP, TBT, TTI xấp xỉ) vì trang cần đăng nhập |
| Giảm dung lượng gói JavaScript | Gói chính 924 KB (gzip 299 KB), chủ yếu là Ant Design; ảnh hưởng rõ khi CPU chậm |
| Đo trên máy chủ riêng | Hiện Locust và API chạy cùng một máy nên số đo là cận trên |
