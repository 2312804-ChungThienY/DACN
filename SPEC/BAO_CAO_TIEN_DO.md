# BÁO CÁO TIẾN ĐỘ & ĐỐI CHIẾU VỚI KẾ HOẠCH

> Đề tài: Trực quan hóa dữ liệu hệ thống LMS Moodle phục vụ công tác quản lý và hỗ trợ giảng dạy
> Kế hoạch gốc: [KE_HOACH_TRIEN_KHAI.md](KE_HOACH_TRIEN_KHAI.md) (v1.0 – 14/09/2026)
> Cập nhật: 15/09/2026
> Trạng thái: **Đã hoàn thành Bước 1 (CSDL phân tích), Bước 2 (Mock data + ETL), Bước 3 (Backend API), Bước 4 (Frontend) và Phần 6 (kiểm thử, hiệu năng, E2E, triển khai Docker).** Còn lại phần cần người thật tham gia: khảo sát ý kiến giảng viên (UAT), viết báo cáo, slide và video demo.

---

## 1. TÓM TẮT

| Hạng mục | Kế hoạch | Thực tế | Trạng thái |
|---|---|---|---|
| CSDL nguồn Moodle | Moodle 3.9 chạy Docker + plugin `mod_attendance` | CSDL `moodle_src` rút gọn (25 bảng `mdl_*`, đúng tên và kiểu cột của Moodle 3.9) trên PostgreSQL 18 local | ✅ Xong (có thay đổi) |
| CSDL phân tích | 1 file `sql/analytics_schema.sql`, PostgreSQL 15 | 6 migration có quản lý phiên bản, PostgreSQL 18 local | ✅ Xong (có mở rộng) |
| Mock data | 5 khoa / 40 môn / 2.000 SV / 2–3 triệu log | 1 khoa / 15 môn / 500 SV / 1,2 triệu log | ✅ Xong (thu hẹp quy mô) |
| ETL 3 job + scheduler | Theo Phần 4 | Đủ 3 job, thêm `nightly`, `maintenance`, `backfill` và APScheduler | ✅ Xong |
| Luật rủi ro | Theo Phần 2.3 | Giữ ngưỡng và công thức điểm, **hiệu chỉnh luật xếp mức RED** | ✅ Xong (có hiệu chỉnh) |
| Kiểm thử dữ liệu (6.1) | Unit, đối soát, ground truth, idempotency, incremental | 174 test, pass 100% | ✅ Xong |
| **Backend API (5.1)** | FastAPI, JWT, RBAC, export Excel/PDF | Đủ 21 endpoint theo 5.1 + `/health`; CLI tạo tài khoản; 56 test API | ✅ Xong (có thay đổi thư viện) |
| Tỷ lệ "chưa có dữ liệu" | – (DDL kế hoạch: `NOT NULL DEFAULT 0`) | Migration V007: lưu `NULL`, hiển thị "Chưa có dữ liệu" | ✅ Xong (theo quyết định 16/09/2026) |
| **Frontend (5.2–5.5)** | React 18 + Vite, Chart.js 4, Ant Design 5 | Đủ trang Admin (Tổng quan, Lưu lượng, Báo cáo) và Giảng viên (Cảnh báo, Modal chi tiết, Tiến độ lớp) | ✅ Xong |
| **Hiệu năng tải lớn (6.2)** | EXPLAIN x1/x10, Locust 50 người dùng, Lighthouse, đo ETL và export | Đã đo đủ; dữ liệu x10 dựng riêng (1,46 triệu dòng) và Moodle 2.000 SV cho ETL | ✅ Xong |
| **E2E, phân quyền, responsive, WCAG (6.3)** | Playwright, kiểm tra 403/401, 4 kích thước màn hình | 27 test chạy trên bản Docker, kèm axe-core cho WCAG 2.1 AA | ✅ Xong |
| **Triển khai (6.4)** | Docker Compose, Nginx, script, README chạy demo | 5 dịch vụ, một lệnh `docker compose up`, README hướng dẫn | ✅ Xong |
| UAT với giảng viên, báo cáo, slide, video (6.1, 6.5) | – | Cần người thật tham gia | ⏳ Chưa làm |

**Kiểm thử hiện tại, tất cả đều pass:**
- 248 test Python (CSDL, ETL, mock, tích hợp, API, bảo mật)
- 8 test Frontend (vitest)
- 27 test E2E Playwright chạy trên bản Docker (luồng nghiệp vụ, phân quyền, responsive, WCAG)
- Kiểm tra nhanh giao diện bằng trình duyệt thật: 11 bước

Số liệu hiệu năng đầy đủ: [docs/KET_QUA_KIEM_THU.md](../docs/KET_QUA_KIEM_THU.md). Tài liệu tổng hợp toàn hệ thống (kiến trúc, CSDL, cách dùng web, minh chứng trực quan hóa): [docs/TAI_LIEU_HE_THONG.md](../docs/TAI_LIEU_HE_THONG.md).

Các quyết định thay đổi so với kế hoạch đều đã được thống nhất trước khi làm, hoặc được giao tự chọn với nguyên tắc: **không thay đổi các yếu tố trực quan hóa của đề tài** (loại biểu đồ, chỉ số hiển thị, cột dữ liệu phục vụ Dashboard).

---

## 2. NHỮNG GÌ ĐÃ LÀM ĐƯỢC

### 2.1 Cấu trúc dự án hiện tại

```
Do_an_chuyen_nganh/
├── .env / .env.example      kết nối 2 CSDL, múi giờ, LMS_AS_OF, cấu hình BACKEND_*
├── requirements.txt         psycopg 3, pandas, SQLAlchemy 2, APScheduler, FastAPI, PyJWT, bcrypt, openpyxl, ReportLab...
├── common/settings.py       múi giờ + thời điểm tham chiếu AS_OF dùng chung
├── database/                runner migration + migration cho 2 CSDL
├── mockdata/                sinh dữ liệu giả lập vào moodle_src
├── etl/                     extract (SQL tĩnh) → transform (pandas) → load (COPY + UPSERT), jobs, scheduler
├── backend/app/             FastAPI: core/, repositories/, schemas/, services/, routers/, main.py, cli.py
└── tests/{database,etl,mockdata,integration,backend}/
```

### 2.2 Bước 1 – Database Layer

**Runner migration** (`database/migrate.py`):
- Áp dụng các file `V<3 số>__<tên>.sql` theo thứ tự cho từng target (`analytics`, `moodle`). Tự tạo database nếu chưa có.
- Mỗi file chạy trong một transaction; lỗi thì rollback cả file.
- Lưu lịch sử vào `public.schema_migrations` kèm checksum SHA-256. File đã áp dụng mà bị sửa, bị xóa hoặc bị bỏ qua thứ tự thì runner dừng lại.
- Chặn `BEGIN/COMMIT` trong file migration. Dùng advisory lock để hai tiến trình không chạy chồng.

**CSDL phân tích `lms_analytics`** (schema `analytics`):

| Migration | Nội dung |
|---|---|
| V001 | Schema, 4 domain dùng chung (`academic_year_t`, `semester_t`, `percent_t`, `risk_level_t`), trigger `set_updated_at`, bảng `etl_run_log`, `etl_watermark`, `app_user` |
| V002 | `fact_student_risk_summary`: đủ cột theo kế hoạch, 5 index (gồm GIN `teacher_ids` và partial index RED) |
| V003 | `fact_course_progress_daily`: đủ cột, index B-tree, BRIN và GIN |
| V004 | `fact_server_traffic_hourly`: đủ cột, index ngày-giờ và BRIN |
| V005 | `intervention_log`, view `v_student_risk_latest` |
| V006 | Bảng `etl_online_snapshot` và ràng buộc `attendance_status` khớp `score_attendance` |

**CSDL nguồn `moodle_src`** (4 migration, 25 bảng): giữ đúng tên bảng, tên cột, kiểu, giá trị mặc định và tên index của Moodle 3.9 trên PostgreSQL, để SQL trích xuất chạy nguyên vẹn trên Moodle thật.
- V001: `course_categories`, `course`, `user`, `role`, `context`, `role_assignments`, `enrol`, `user_enrolments`, `groups`, `groups_members`
- V002: `logstore_standard_log`, `sessions`, `user_lastaccess`
- V003: `modules`, `course_sections`, `course_modules`, `course_modules_completion`, `assign`, `assign_submission`, `page`, `forum`
- V004 (plugin): `attendance`, `attendance_sessions`, `attendance_statuses`, `attendance_log`

### 2.3 Bước 2 – Mock data

`seed_structure.py` dựng cấu trúc: 8 vai trò mặc định của Moodle, Khoa CNTT gồm 4 bộ môn, 15 môn HK1 2026-2027 (bắt đầu 07/09/2026, 15 tuần), 8 giảng viên (có trợ giảng), 500 sinh viên tên tiếng Việt, ghi danh, chương/tuần, trang bài giảng, diễn đàn, 5–8 bài tập/môn, 1–2 buổi điểm danh/tuần.

`generate_activity.py` sinh hành vi **đến thời điểm AS_OF**: log (đăng nhập, xem môn/bài giảng/bài tập/diễn đàn, đăng bài, nộp bài, đăng nhập lỗi, truy cập từ app `origin='ws'`), bài nộp cá nhân và nhóm, điểm danh, hoàn thành hoạt động, `mdl_user_lastaccess`, `mdl_sessions` tại AS_OF, và file ground truth. Hồ sơ hành vi GREEN/YELLOW/RED (65/20/15%), trọng số giờ/thứ, hệ số giữa kỳ và 48 giờ trước hạn nộp giữ đúng Phần 3.2.

**Ca biên sinh chủ động:** SV bị khóa (4) và bị xóa (2); ghi danh tạm dừng (2%) và hết hạn ở tuần 3 (1%); phương thức ghi danh bị tắt; bài nộp nhóm (IT008, IT009); buổi điểm danh theo nhóm (IT013); môn chưa có buổi điểm danh (IT015); SV chưa từng truy cập; SV "bỏ dần" từ tuần 7.

**Dữ liệu hiện có** (AS_OF = 06/11/2026 10:30, tuần 9):

| Bảng Moodle | Số dòng | | Bảng analytics | Số dòng |
|---|---|---|---|---|
| `mdl_logstore_standard_log` | 1.215.153 | | `fact_student_risk_summary` | 145.846 (61 ngày snapshot) |
| `mdl_user_enrolments` | 2.496 | | `fact_course_progress_daily` | 915 (15 môn × 61 ngày) |
| `mdl_attendance_log` | 36.933 | | `fact_server_traffic_hourly` | 1.451 |
| `mdl_course_modules_completion` | 26.120 | | `etl_online_snapshot` | 17.406 |
| `mdl_assign_submission` | 7.272 | | `app_user` | 9 (1 admin + 8 giảng viên) |

Snapshot ngày 06/11/2026: 2.383 cặp SV–môn, gồm **408 RED (17,1%)**, 667 YELLOW, 1.308 GREEN.

### 2.4 Bước 2 – ETL

**Luồng mỗi job** (`jobs/runner.py`), đúng Phần 4.1: `pg_try_advisory_lock` → ghi `etl_run_log` RUNNING → Extract / Transform / Load → ghi SUCCESS hoặc FAILED kèm lỗi. Mã thoát CLI: `0` thành công, `3` bị bỏ qua do khóa, `1` lỗi.

- **Extract:** SQL tĩnh trong `etl/extract/sql/`, tham số bind. Toàn bộ dữ liệu của một lần tính đọc trong **một transaction REPEATABLE READ**. Engine Moodle đặt chế độ chỉ đọc và `statement_timeout=60s`.
- **Transform:** `risk_rules.py` (so sánh ngưỡng bằng `Fraction`, làm tròn half-up bằng `Decimal`), `student_risk.py`, `course_progress.py`, `traffic.py`, `semester.py`.
- **Load:** bảng tạm `LIKE` bảng đích → `COPY` → `INSERT … ON CONFLICT DO UPDATE … WHERE (cũ) IS DISTINCT FROM (mới)`. Watermark cập nhật trong cùng transaction.

| Job | Lịch | Việc |
|---|---|---|
| `traffic` | mỗi 5 phút | Log mới theo watermark; tính lại các giờ bị ảnh hưởng, giờ hiện tại và giờ trước; chụp `mdl_sessions` |
| `course_progress` | phút 05 mỗi giờ | Tiến độ trong ngày của các môn đang diễn ra |
| `student_risk` | 07:15–21:15, 2 giờ/lần | Snapshot rủi ro hôm nay (ghi đè, xóa SV đã hủy ghi danh) |
| `nightly` | 01:00 | Chốt risk + progress hôm qua lúc 23:59:59, tính lại 24 giờ lưu lượng, đánh dấu P90 giờ cao điểm |
| `maintenance` | Chủ nhật 03:00 | Snapshot cũ hơn 180 ngày chỉ giữ bản cuối tuần; `VACUUM ANALYZE` |
| `backfill` | thủ công | Nạp lịch sử từ `--from` tới AS_OF (07/09 → 06/11: **356 giây**) |

### 2.5 Kiểm thử Bước 1–2 – 174 test

| Nhóm | Nội dung | Tương ứng kế hoạch 6.1 |
|---|---|---|
| `tests/database` | Runner migration; schema chấp nhận dữ liệu đúng, từ chối dữ liệu sai theo từng CHECK; generated column; trigger; FK | Ràng buộc dữ liệu |
| `tests/etl` | Luật rủi ro (vắng đúng 15%/30%, thiếu đúng 20%/60%, 0 buổi, `days=None`, trung vị lớp = 0, dữ liệu không hợp lệ, luật gốc vẫn cấu hình được); học kỳ; transform | Unit test luật rủi ro |
| `tests/mockdata` | Quy mô, không có bản ghi mồ côi, không có sự kiện sau AS_OF, ca biên tồn tại | – |
| `tests/integration` | Đối soát 5 môn ngẫu nhiên với SQL viết độc lập: **sai lệch = 0**. Chạy lại job: **checksum không đổi**. Chèn 1.000 log: **chỉ đúng 1 giờ bị cập nhật** | Đối soát, idempotency, incremental |
| Ground truth | **Recall(RED) = 97,8%** (≥ 90%), **Precision(RED) = 85,3%** (≥ 80%) | Đối chiếu ground truth |

Ma trận nhầm lẫn tại 06/11/2026 (2.383 cặp SV–môn):

| Ground truth \ ETL | GREEN | YELLOW | RED |
|---|---|---|---|
| GREEN | 1.279 | 247 | 0 |
| YELLOW | 29 | 412 | 60 |
| RED | 0 | 8 | 348 |

### 2.6 Bước 3 – Backend API (FastAPI)

**Kiến trúc** (`backend/app/`), theo đúng bố cục 5.1:

| Thành phần | Nội dung |
|---|---|
| `core/config.py` | Biến `BACKEND_*` trong `.env`. **"Hôm nay" của API tính theo `LMS_AS_OF`**, khớp với mock data và ETL |
| `core/db.py` | SQLAlchemy Core + psycopg 3, pool 10 kết nối, `statement_timeout=15s` |
| `core/security.py` | Mật khẩu bcrypt; JWT HS256 (hết hạn 8 giờ); `require_role`; giới hạn đăng nhập sai (5 lần/5 phút theo IP + username → 429) |
| `core/cache.py` | Cache TTL 60 giây (cachetools) cho KPI, số liệu theo khoa/môn, heatmap, bộ lọc |
| `repositories/` | SQL thuần bằng `text()` với tham số bind. Sắp xếp và lọc động chỉ ghép đoạn SQL từ danh sách cho phép |
| `schemas/` | Pydantic cho mọi response → Swagger tự sinh tại `/api/docs` |
| `services/` | Xuất Excel (openpyxl write-only: giữ kiểu số/ngày, cố định dòng tiêu đề, bộ lọc cột, sheet "Thông tin") và PDF (ReportLab: A4 ngang, font có dấu tiếng Việt, lặp tiêu đề mỗi trang, tô màu mức rủi ro, số trang) |
| `routers/` | `auth`, `common`, `admin`, `reports`, `teacher` dưới tiền tố `/api/v1` |
| `cli.py` | `sync-users` tạo/cập nhật tài khoản từ Moodle (`user_id = mdl_user.id`), `set-password`, `list-users` |

**Endpoint đã có** (đủ các dòng trong bảng 5.1):

| Nhóm | Endpoint |
|---|---|
| Xác thực & dùng chung | `POST /auth/login`, `GET /auth/me`, `GET /filters`, `GET /etl/status`, `GET /health` |
| Admin 1.1 | `GET /admin/overview/kpis`, `/admin/enrollment/by-faculty`, `/admin/enrollment/faculties/{id}/courses`, `/admin/enrollment/courses/{id}/students` |
| Admin 1.2 | `GET /admin/traffic/hourly`, `/admin/traffic/realtime`, `/admin/traffic/heatmap` |
| Admin 1.3 | `GET /admin/reports/preview`, `/admin/reports/export` (3 loại báo cáo `enrollment`, `risk`, `traffic`; định dạng `xlsx`, `pdf`) |
| Giảng viên 2.1 | `GET /teacher/courses`, `/teacher/courses/{id}/risk-summary`, `/students`, `/students/{uid}`, `POST /students/{uid}/interventions`, `GET /export` |
| Giảng viên 2.2 | `GET /teacher/courses/{id}/progress?granularity=day\|week`, `/students/{uid}/compare` |

Quy ước chung đúng 5.1: lỗi trả `{"detail": "..."}`; danh sách phân trang trả `items, total, page, page_size`; mọi response có `data_updated_at`.

**Phân quyền:**
- Chưa đăng nhập, token sai hoặc hết hạn, tài khoản bị khóa → 401.
- Sai vai trò → 403, theo cả hai chiều: GV gọi `/admin/*` và Admin gọi `/teacher/*`.
- GV gọi môn của GV khác → 403; môn không tồn tại → 404.
- Vai trò đọc lại từ `app_user` ở mỗi request, không tin trường `role` trong token.
- Mọi truy vấn trên bảng fact của giảng viên đều kèm điều kiện `teacher_ids`.

**Tài khoản demo** (đã tạo bằng `sync-users`): `admin` (ADMIN) và 8 giảng viên `gv.*`, mật khẩu tạm `Lms@2026demo`. Đổi bằng `python -m backend.app.cli set-password --username <tên>`.

**Kiểm thử – 56 test** (`tests/backend`), mọi số liệu API đều **đối chiếu với truy vấn trực tiếp CSDL**:
- **Bảo mật:** bcrypt, JWT hết hạn/giả mạo/`alg=none`, khóa JWT quá ngắn, bộ đếm đăng nhập sai (cửa sổ trượt), chống SQL injection qua tham số `sort`, thoát ký tự đại diện khi tìm kiếm.
- **Phân quyền:** 401/403/404 như trên; token ghi `role=ADMIN` cho tài khoản GV vẫn bị chặn.
- **Admin:**
  - Tổng KPI khớp tổng bảng tiến độ.
  - Số "SV có tương tác" ở cấp SV khớp `total_active_students` của **cả 15 môn**.
  - Phân trang và tìm kiếm đúng; chuỗi 24 giờ và heatmap 168 ô đầy đủ.
- **Giảng viên:**
  - Chỉ thấy đúng môn mình dạy; tổng đèn = số SV ghi danh.
  - Thứ tự mặc định: ĐỎ → VÀNG → XANH, điểm cao trước; các bộ lọc mức/tiêu chí/tìm kiếm đúng.
  - Lịch sử cảnh báo đủ 61 ngày; can thiệp ghi đúng mức rủi ro tại thời điểm tạo.
  - Chuỗi tiến độ theo tuần khớp chuỗi theo ngày; số liệu so sánh lớp khớp trang tiến độ.
- **Báo cáo:**
  - Preview và file Excel đúng số dòng; Excel giữ kiểu số.
  - PDF hợp lệ; vượt giới hạn dòng trả 422.

**Đo nhanh** (máy local, dữ liệu x1, 20 lần/endpoint, xóa cache mỗi lần):

| Endpoint | Median | Max |
|---|---|---|
| `GET /admin/overview/kpis` | 6,7 ms | 8,2 ms |
| `GET /admin/enrollment/courses/{id}/students` | 7,3 ms | 42,7 ms |
| `GET /admin/reports/preview?report_type=risk` | 12,9 ms | 14,8 ms |
| `GET /teacher/courses/{id}/students` | 10,4 ms | 11,6 ms |
| `GET /teacher/courses/{id}/students/{uid}` | 6,9 ms | 9,8 ms |
| `GET /teacher/courses/{id}/progress?granularity=week` | 5,8 ms | 7,1 ms |
| Các endpoint còn lại | 4–12 ms | < 16 ms |
| Xuất PDF toàn bộ cảnh báo (2.383 dòng, 114 trang, 513 KB) – 3 lần đo | 3,9–5,8 s | – |
| Xuất Excel toàn bộ cảnh báo (2.383 dòng, 155 KB) – 3 lần đo | 1,0–1,1 s | – |

Mọi endpoint đều dưới mục tiêu 100 ms/truy vấn của 6.2.

Mục tiêu xuất file của 6.2 là PDF 500 dòng và Excel 10.000 dòng, mỗi loại dưới 5 giây. Bản PDF 2.383 dòng (gấp khoảng 5 lần mục tiêu) dao động quanh ngưỡng 5 giây; bản 39 dòng mất 0,06 giây. Excel còn dư nhiều. Bố cục PDF đã được kiểm tra bằng cách render trang thành ảnh:
- tiếng Việt hiển thị đúng
- không từ nào bị ngắt giữa chừng
- màu mức rủi ro đúng

Chưa phải benchmark chính thức: chưa đo tải đồng thời (Locust) và dữ liệu x10.

### 2.7 Sửa "tỷ lệ chưa có dữ liệu lưu là 0" (migration V007)

Trước đây, khi mẫu số bằng 0, ETL ghi tỷ lệ = 0. Ví dụ môn IT015 chưa có buổi điểm danh nào nhưng hiện "Chuyên cần 0%", dễ bị hiểu là không sinh viên nào đi học. Đã sửa theo quyết định ngày 16/09/2026.

| Tầng | Thay đổi |
|---|---|
| CSDL | V007 cho phép `NULL` ở `absence_rate`, `completion_rate` (`fact_student_risk_summary`) và `assignment_submission_rate`, `attendance_rate`, `avg_completion_rate` (`fact_course_progress_daily`). Thêm ràng buộc `absence_rate IS NULL ⇔ total_sessions = 0` |
| ETL | Hàm `percent()` trả `None` khi mẫu số = 0. Đã chạy lại backfill 07/09 → 06/11 |
| API | Các trường tỷ lệ trong schema cho phép `null`; file PDF hiển thị "–" |
| Frontend | Hiển thị "Chưa có dữ liệu" thay cho thanh tiến độ; đường biểu đồ để khoảng trống |

Kết quả sau khi nạp lại:
- Chuyên cần của IT015 = `NULL`.
- Tỷ lệ nộp bài = `NULL` ở mọi môn trong 07–22/09, trước khi có bài tới hạn đầu tiên.
- 9.730 dòng cảnh báo có `absence_rate = NULL`, tương ứng với các ngày/môn chưa có buổi điểm danh.

Đã thêm test cho tầng CSDL, ETL và định dạng file xuất.

### 2.8 Bước 4 – Frontend (React + Vite + Chart.js + Ant Design)

Mã nguồn trong `frontend/` ([frontend/README.md](../frontend/README.md)). Thư viện đúng như kế hoạch: React 18, Vite 5, Chart.js 4 (react-chartjs-2, chartjs-chart-matrix, chartjs-plugin-annotation), Ant Design 5, React Query, axios.

| Kế hoạch | Màn hình đã làm |
|---|---|
| 5.2 Admin – Tổng quan | Bộ lọc Năm học / Học kỳ / Khoa, nút Làm mới, menu Export. 6 thẻ KPI: tổng môn, SV đăng ký, SV tương tác, online hiện tại, peak hôm nay, SV nguy cơ đỏ. Biểu đồ đường 2 trục (24 giờ / 7 ngày, tô nền giờ cao điểm). Stacked bar theo khoa, nhấn vào cột để drill-down. Bảng phân cấp Khoa ▸ Môn ▸ Sinh viên có breadcrumb, sắp xếp, lọc SV có/không tương tác, tìm kiếm, phân trang. Heatmap giờ × thứ 4 tuần |
| 5.2 Admin – Lưu lượng | Chọn khoảng ngày có mốc nhanh (hôm nay, 7/30/90 ngày). Thẻ thời gian thực tự làm mới 60 giây. Biểu đồ 2 trục theo khoảng đã chọn. Top 10 giờ đông nhất. Heatmap chọn 1–12 tuần |
| 5.2 Admin – Báo cáo | Chọn loại báo cáo và bộ lọc (khoa, môn, mức rủi ro, ngày số liệu hoặc khoảng ngày) → bảng xem trước có phân trang → Xuất Excel / Xuất PDF |
| 5.3 GV – Cảnh báo | Chọn môn trên thanh tiêu đề. 3 thẻ đèn giao thông, nhấn để lọc. Doughnut: nhấn lát cắt để lọc, kèm số SV theo từng tiêu chí (nhấn để lọc). Bảng cảnh báo: tìm kiếm, lọc mức/tiêu chí, sắp xếp phía server, xuất Excel/PDF |
| 5.3 GV – Modal chi tiết | Lý do và chỉ số chính. Bar so sánh SV với trung bình lớp. Line hoạt động theo tuần, ● có mặt đủ / ○ có vắng. Bài tập ✔ đúng hạn / ✔ trễ / ✘ thiếu / … chưa tới hạn. Lịch sử cảnh báo, can thiệp trước đây, 4 nút hành động (tin nhắn, email, ghi chú, hẹn gặp) ghi vào `intervention_log` |
| 5.3 GV – Tiến độ lớp | Thanh tiến độ hoàn thành / nộp bài / chuyên cần. Tiến độ theo chương/tuần. Line SV hoạt động (theo tuần/ngày). Line tỷ lệ tiến độ theo thời gian |
| 5.5 Routes & phân quyền | Đăng nhập JWT, tự đăng xuất khi token hết hạn hoặc API trả 401; `ProtectedRoute` chặn theo vai trò (GV mở `/admin` bị chuyển về trang GV) |

**Quy tắc hiển thị áp dụng** (theo kế hoạch 5.4 và skill trực quan hóa dữ liệu):
- Mức rủi ro luôn có biểu tượng + chữ.
- Mọi biểu đồ có tooltip và nút "Biểu đồ | Bảng" để xem số liệu dạng bảng.
- Biểu đồ đường có đường dóng dọc theo vị trí chuột.
- Lưới và trục mảnh; chữ dùng màu mực, không tô bằng màu dữ liệu.
- Số và ngày định dạng vi-VN.
- "Hôm nay" lấy theo `as_of` của API.

**Kiểm tra màu bằng script của skill:**
- 3 màu chuỗi dữ liệu (xanh dương / cam / xanh ngọc) đạt mọi tiêu chí mù màu.
- Màu đèn giao thông của đề tài **không đạt** với người mù màu đỏ–lục (xem #48).

**Kiểm chứng:**
- `npm test`: 8 test (định dạng, gộp dữ liệu biểu đồ).
- `npm run build` thành công. Gói chính 924 KB (gzip 299 KB), gói biểu đồ 233 KB (gzip 80 KB).
- `npm run smoke`: dùng playwright-core với Chrome có sẵn trên máy, đi qua 11 bước trên API và dữ liệu thật:
  - Admin: đăng nhập sai, tổng quan, drill-down tới danh sách SV, lưu lượng, xem trước báo cáo, tải Excel.
  - Giảng viên: cảnh báo, lọc qua doughnut, Modal chi tiết, tiến độ lớp, bị chặn khi vào `/admin`.
  - Màn hình điện thoại 390px.
  - Kết quả cuối: không có lỗi JavaScript, console hay API. Các lần chạy đầu phát hiện và đã sửa: tiêu đề bảng cảnh báo bị ẩn trên điện thoại, 2 cảnh báo deprecation của Ant Design.
- Đã xem lại từng ảnh chụp để kiểm tra bố cục, nhãn chồng chéo và chữ bị cắt.

---

## 3. NHỮNG THAY ĐỔI SO VỚI KẾ HOẠCH VÀ LÝ DO

### 3.1 Môi trường & công nghệ

| # | Kế hoạch | Thực tế | Lý do |
|---|---|---|---|
| 1 | Moodle 3.9 chạy Docker (`bitnami/moodle`) + cài plugin `mod_attendance` | CSDL `moodle_src` rút gọn: chỉ 25 bảng ETL cần, giữ đúng cấu trúc Moodle 3.9 | Đã thống nhất 14/09/2026. Dựng Moodle thật và cài plugin tốn công nhưng không thêm giá trị cho phần phân tích vì ETL chỉ đọc CSDL. Giữ đúng tên bảng/cột/kiểu nên SQL trích xuất vẫn chạy được trên Moodle thật |
| 2 | PostgreSQL 13 (Moodle) + 15 (analytics) trong container | PostgreSQL 18 cài local, 2 database `moodle_src` và `lms_analytics` | Tận dụng môi trường sẵn có; hai CSDL vẫn tách riêng như thiết kế |
| 3 | `psycopg2` | `psycopg` 3 | Hỗ trợ `COPY` theo từng dòng gọn hơn, tương thích SQLAlchemy 2 |
| 4 | Faker `vi_VN` sinh tên | `mockdata/names.py` tự sinh | Kiểm soát được họ/đệm/tên thật của Việt Nam, tái lập theo seed |
| 5 | Một file `sql/analytics_schema.sql` | 6 migration có phiên bản + runner kiểm tra checksum | Schema đã thay đổi trong quá trình làm (thêm V006); migration giúp nâng cấp mà không xóa dữ liệu |
| 6 | SQL trích xuất ở `sql/extract/` | `etl/extract/sql/` và `etl/load/sql/`, có cơ chế `{{include}}` | Đặt gần mã dùng nó; CTE `student_enrol` viết một lần, include vào mọi truy vấn |

### 3.2 Phạm vi dữ liệu giả lập

| # | Kế hoạch | Thực tế | Lý do |
|---|---|---|---|
| 7 | 5 khoa, 40 môn, 2.000 SV, 40 GV, 2–3 triệu log | 1 Khoa CNTT (4 bộ môn), 15 môn, 500 SV, 8 GV, 1,2 triệu log | Đã thống nhất 14/09/2026: đề tài thuộc Khoa CNTT, quy mô này đủ thể hiện mọi biểu đồ và ca biên |
| 8 | Dùng `now()` làm thời điểm hiện tại | Tham số **`LMS_AS_OF`** (mặc định 06/11/2026 10:30). Để trống = thời gian thực | Đã thống nhất 14/09/2026. Học kỳ giả lập mới bắt đầu 1 tuần nên `now()` không có dữ liệu rủi ro; AS_OF còn cho backfill dựng lại đúng lịch sử |
| 9 | Script `live_sessions.py` cập nhật `mdl_sessions` mỗi 5 phút | Sinh sẵn `mdl_sessions` tại AS_OF; ETL bổ sung mẫu online suy ra từ log | Khi đồng hồ "đóng băng" ở AS_OF, script chạy liên tục không có ý nghĩa |
| 10 | Mẫu RED "nộp tối đa 40% bài" cho mọi bài | Chỉ áp dụng cho bài **đã tới hạn** tại AS_OF | Nếu tính cả bài tương lai, giữa kỳ SV RED có thể chưa thiếu bài nào |
| 11 | Chỉ sinh log xem môn + nộp bài | Thêm xem bài giảng/bài tập/diễn đàn, đăng bài, đăng nhập lỗi, truy cập `ws`, bài nộp nhóm | Để `login_count`, `failed_login_count`, `ws_requests`, `active_actions` có dữ liệu thật |

### 3.3 Thiết kế CSDL phân tích

Mọi cột mà Dashboard cần giữ nguyên tên, kiểu và ý nghĩa.

| # | Thay đổi | Lý do |
|---|---|---|
| 12 | Thêm 4 **domain** và nhiều **CHECK** | Đưa tiêu chí "Ràng buộc dữ liệu: 0 vi phạm" (6.1) vào ngay CSDL |
| 13 | `stat_date`, `hour_of_day`, `day_of_week` của bảng traffic là **generated column** | Không bao giờ lệch với `stat_hour` |
| 14 | Trigger `set_updated_at` thay cho `updated_at=now()` trong câu UPSERT | Luôn đúng với mọi đường ghi |
| 15 | `IDENTITY` thay `BIGSERIAL`; FK `etl_run_id … ON DELETE SET NULL` | Chuẩn PostgreSQL mới; dọn được `etl_run_log` mà không mất fact |
| 16 | `attendance_status` mặc định `NO_DATA` (kế hoạch: `OK`) + ràng buộc khớp điểm C1 | Kế hoạch chưa định nghĩa WARN/CRITICAL. Đã thống nhất 14/09/2026 |
| 17 | Bảng mới **`etl_online_snapshot`**; peak/avg online theo giờ được **tính lại** từ các mẫu | Công thức cộng dồn trung bình bị đếm trùng khi job chạy lại hoặc retry, vi phạm idempotency |
| 18 | Chưa chuyển `v_student_risk_latest` thành materialized view | API không dùng view này (xem #35). Sẽ quyết định sau khi đo tải lớn |

### 3.4 Luật rủi ro

| # | Kế hoạch (2.3) | Thực tế | Lý do |
|---|---|---|---|
| 19 | **RED** khi có ít nhất một tiêu chí = 2 **hoặc** tổng ≥ 3 | **RED** khi **C2 = 2** **hoặc ≥ 2 tiêu chí = 2** **hoặc tổng ≥ 4** | Luật gốc cho Precision(RED) = **62,9%**, không đạt mục tiêu 80%: tuần 9 mỗi môn mới có 3–4 bài tới hạn, thiếu 2 bài đã thành C3 = 2. Luật mới: Precision **85,3%**, Recall **97,8%**. Kế hoạch 6.7 đã dự trù hiệu chỉnh; người dùng giao tự chọn ngày 15/09/2026 |

Giữ nguyên ngưỡng từng tiêu chí, công thức `risk_score`, các cột và cách hiển thị. Đổi `red_min_red_criteria=1, red_min_total=3` trong `etl/config.py` là quay về luật gốc.

### 3.5 Logic trích xuất & ETL

| # | Kế hoạch | Thực tế | Lý do |
|---|---|---|---|
| 20 | `last_access` lấy từ `mdl_user_lastaccess` | `MAX(timecreated)` từ logstore tại AS_OF | `mdl_user_lastaccess` chỉ lưu giá trị hiện tại, không dựng lại được các ngày trước |
| 21 | CTE `student_enrol` dạng JOIN nhiều bảng | Dạng semi-join `EXISTS`, thêm `timestart ≤ AS_OF` | Dạng JOIN làm planner chọn Nested Loop và bị **timeout**. Kết quả tương đương, đã đối soát |
| 22 | Truy vấn log JOIN thẳng với danh sách ghi danh | Gom log theo (môn, SV) trước rồi mới nối | Tận dụng index, tránh timeout |
| 23 | Tỷ lệ hoàn thành tính mọi hoạt động có `completion > 0` | Chỉ tính hoạt động đã tới hạn dự kiến | Tính cả các tuần chưa học thì tỷ lệ giữa kỳ bị kéo xuống, gây hiểu sai |
| 24 | Đọc log theo lô 200k dòng | Tổng hợp trong SQL theo lô **1 ngày** | Chỉ trả về vài chục dòng mỗi giờ, không kéo log thô về Python |
| 25 | UPSERT luôn ghi đè | Chỉ UPDATE khi giá trị đổi (`IS DISTINCT FROM`) | Kiểm chứng idempotency bằng checksum được |
| 26 | Snapshot risk trong ngày chỉ UPSERT | UPSERT + xóa SV không còn trong lần tính mới | SV hủy ghi danh giữa ngày không nằm lại trong bảng cảnh báo |
| 27 | Trường JSONB như mẫu | `weekly_activity` thêm `sessions`, `present`; `assignment_detail` thêm `assign_id`, `submitted_at`, trạng thái `missing`/`not_due` | Đủ dữ liệu cho Modal chi tiết mà không truy vấn ngược Moodle; không đổi thiết kế Modal |
| 28 | `nightly` có `REFRESH MATERIALIZED VIEW` | Không có | Chưa dùng materialized view (#18) |
| 29 | Retry mọi job | `traffic` không retry | Lượt 5 phút kế tiếp tự bù nhờ watermark |
| 30 | `backfill` thủ công | Đã làm, kèm `--as-of` cho mọi job | Nạp lịch sử lần đầu và khi đổi AS_OF |

### 3.6 Backend API

Mọi endpoint, tham số và dạng response của 5.1 đều có. Các thay đổi chỉ nằm ở thư viện và cách tính bên trong, **không bớt dữ liệu nào mà các biểu đồ ở 5.2–5.5 cần**.

| # | Kế hoạch | Thực tế | Lý do |
|---|---|---|---|
| 31 | JWT bằng `python-jose` | `PyJWT` | `python-jose` ít được bảo trì và có lỗ hổng đã công bố (CVE-2024-33663, CVE-2024-33664); PyJWT là thư viện phổ biến, được FastAPI khuyến nghị |
| 32 | PDF bằng Jinja2 + WeasyPrint | **ReportLab** | WeasyPrint cần cài GTK/Pango riêng trên Windows, khó chạy trên máy dev. ReportLab thuần Python, dùng font Arial (Windows) hoặc DejaVu Sans (Linux) cho tiếng Việt |
| 33 | Pool `asyncpg`/SQLAlchemy async | SQLAlchemy Core đồng bộ + psycopg 3; endpoint `def` chạy trong threadpool của FastAPI | Dùng lại driver và cấu hình kết nối của ETL. Truy vấn chỉ mất 4–13 ms nên async không cải thiện rõ, mà tăng độ phức tạp |
| 34 | Bảng cảnh báo GV lọc `:uid = ANY(teacher_ids)` | `teacher_ids @> ARRAY[:uid]` | Cùng ý nghĩa, nhưng chỉ toán tử `@>` dùng được GIN index `ix_risk_teacher_gin` mà kế hoạch đã tạo |
| 35 | Bảng cảnh báo đọc từ view `v_student_risk_latest` | Đọc **snapshot mới nhất của từng môn** | View lấy bản mới nhất theo từng SV nên vẫn giữ SV đã hết hạn/hủy ghi danh (snapshot cũ ngày 27/09). Tổng số SV trên bảng sẽ lệch với số đèn đỏ/vàng/xanh và số SV đăng ký. Không đổi cột nào |
| 36 | Số liệu học kỳ lấy `stat_date = MAX(stat_date)` chung (mẫu 2.4) | Lấy dòng mới nhất **của từng môn** trong học kỳ | Môn kết thúc trước ngày mới nhất sẽ bị rơi khỏi stacked bar và KPI nếu dùng một ngày chung |
| 37 | Drill-down SV: `status=active\|inactive` (chưa định nghĩa) | "Có tương tác" = có log từ ngày bắt đầu môn | Khớp chính xác `total_active_students` ở cấp môn (đã kiểm chứng cả 15 môn). `total_access_count > 0` lệch ở môn IT011 (182 so với 180) vì có log trước ngày bắt đầu môn |
| 38 | `academic_year`, `semester` bắt buộc ở API Admin | Tùy chọn, bỏ trống thì dùng học kỳ của dữ liệu mới nhất; truyền thiếu một trong hai → 422 | Frontend mở trang lần đầu không cần biết trước học kỳ; `/filters` trả thêm `current` |
| 39 | Can thiệp: `action_type` = `MESSAGE\|EMAIL\|NOTE`, MESSAGE có thể gọi Moodle Web Service | Chấp nhận thêm `MEETING`; **chỉ ghi nhật ký**, không gửi tin nhắn Moodle | `MEETING` có trong CHECK của bảng và nút "Hẹn gặp" ở layout 5.3. Kế hoạch ghi gửi tin nhắn là tùy chọn, và `moodle_src` rút gọn không có Web Service |
| 40 | Phân quyền: "GV gọi `/admin/*` nhận 403" | Áp dụng cả chiều ngược lại: Admin gọi `/teacher/*` cũng nhận 403 | API giảng viên lọc theo `teacher_ids` của người gọi, Admin không có trong đó nên luôn trả rỗng. Trả 403 rõ ràng hơn |
| 41 | Không nói cách tạo `app_user` | CLI `sync-users` lấy từ Moodle: vai trò editingteacher/teacher → TEACHER, `admin` → ADMIN; tài khoản bị khóa → vô hiệu | `user_id` phải bằng `mdl_user.id` để khớp `teacher_ids`. Tạo tay dễ sai |
| 42 | Heatmap `weeks=4` | Trung bình 4 tuần **trọn ngày**, không tính hôm nay | Hôm nay đang dở dang sẽ kéo thấp các giờ chưa tới |
| 43 | `progress` theo tuần (chưa định nghĩa cách gộp) | Tỷ lệ, đèn và "SV hoạt động 7 ngày" lấy tại ngày cuối tuần; lượt xem/thao tác/bài nộp cộng dồn | Snapshot Chủ nhật 23:59:59 bao trọn Thứ 2–Chủ nhật; cộng dồn tỷ lệ theo ngày là sai |
| 44 | Response mẫu tối thiểu | Bổ sung trường: `risk-summary` thêm số SV có tiêu chí ở mức 2 và số SV chưa có buổi điểm danh; `compare` thêm chỉ số "tổng lượt truy cập"; KPI thêm `yellow/green_students`, `current_online_at`; export GV thêm PDF; `GET /health` | Dữ liệu sẵn có, giúp Frontend hiển thị chú thích và trạng thái rõ hơn. Không thay biểu đồ nào |
| 45 | Chưa nói giới hạn | Đăng nhập sai 5 lần/5 phút → 429; PDF tối đa 5.000 dòng, Excel 200.000 dòng → 422 | Mục 6.3 yêu cầu rate-limit login; giới hạn xuất file tránh request treo server |

### 3.7 CSDL – bổ sung sau Bước 3

| # | Kế hoạch | Thực tế | Lý do |
|---|---|---|---|
| 46 | Các cột tỷ lệ `NOT NULL DEFAULT 0` (DDL 2.2) | `NULL` = chưa có dữ liệu để tính (migration V007) | Giá trị 0 không phân biệt được "không ai đi học/nộp bài" với "chưa có buổi/bài nào". Người dùng quyết định sửa ngày 16/09/2026. Tên cột và cách hiển thị không đổi |

### 3.8 Frontend

Đủ các trang, biểu đồ và tương tác của 5.2–5.5. Các điểm dưới đây là cách hiện thực hoặc bổ sung, **không bỏ hay thay loại biểu đồ nào**.

| # | Kế hoạch | Thực tế | Lý do |
|---|---|---|---|
| 47 | Biểu đồ đường 2 trục cho lưu lượng | **Giữ nguyên 2 trục**, thêm: đường requests nét liền, đường online nét đứt; tiêu đề trục ghi rõ đại lượng; legend ghi "(trục trái/phải)"; tooltip hiện cả hai giá trị | Đề tài yêu cầu 2 trục nên giữ. Skill trực quan hóa khuyến cáo tránh 2 trục vì dễ đọc nhầm thang, nên bổ sung các cách phân biệt trên |
| 48 | Màu đèn giao thông #D64545 / #E0A100 / #2E9D5B, luôn kèm biểu tượng + chữ | Giữ nguyên màu; mọi nơi hiển thị mức rủi ro đều có ● ▲ ✔ và chữ; doughnut có chú thích từng dòng | Script kiểm tra màu cho thấy người mù màu đỏ–lục gần như không phân biệt được đỏ và xanh (ΔE 3,5, cần ≥ 8). Vì vậy biểu tượng + chữ là kênh nhận diện chính, đúng yêu cầu 5.4 |
| 49 | Prototype 5.5: huy hiệu nền màu đậm, chữ trắng | Nền màu nhạt cùng tông, biểu tượng màu đậm, chữ màu đậm | Chữ trắng trên nền vàng #E0A100 chỉ đạt tương phản khoảng 2,2:1, khó đọc |
| 50 | Layout 5.2: "vùng tô nền 08–10h, 14–16h (giờ cao điểm)" | Tô nền các giờ có `is_peak_hour = true` (requests vượt P90 của 28 ngày) | Cột `is_peak_hour` do kế hoạch định nghĩa chính cho mục đích này. Tô theo dữ liệu vẫn đúng khi giờ cao điểm thay đổi; với mock data các vùng tô rơi đúng khung sáng và chiều |
| 51 | Modal: một bar so sánh gồm "Truy cập 14d" và "Nộp bài %" | Tách 2 biểu đồ nhỏ: nhóm tỷ lệ % (nộp bài, chuyên cần, hoàn thành) và nhóm số lượt (truy cập 14 ngày, tổng truy cập) | Đặt "3 lượt" và "78%" chung một trục làm thanh dài ngắn không so được với nhau |
| 52 | Modal: "Line hoạt động 15 tuần" | Hiện từ tuần 1 tới tuần hiện tại (tuần 9 tại AS_OF) | Các tuần chưa diễn ra không có dữ liệu; vẽ thêm sẽ trông như SV bỏ học |
| 53 | Nút "Gửi tin nhắn Moodle" (có thể gọi Moodle Web Service) | Ghi nhận vào `intervention_log` kèm thông báo chưa kết nối Moodle; nút Email mở ứng dụng thư tới email SV | `moodle_src` rút gọn không có Web Service (xem #39) |
| 54 | Không nêu | Bổ sung: nút "Biểu đồ \| Bảng" cho mọi biểu đồ; trang Lưu lượng có thẻ thời gian thực và Top 10 giờ; trang Tiến độ có biểu đồ tỷ lệ theo thời gian; thẻ Online hiện tại ghi thời điểm lấy mẫu | Mọi số liệu trên biểu đồ đều đọc được không cần di chuột; dữ liệu đã có sẵn từ API |
| 55 | `hooks/useApi.js`, `components/RiskTable.jsx`, `pages/Reports.jsx`… | `api/hooks.js` (một hook cho mỗi endpoint), bảng cảnh báo nằm trong `pages/teacher/TeacherRisk.jsx`, trang Admin tách 3 file | Tổ chức theo trang cho gọn; chức năng giống kế hoạch |
| 56 | E2E bằng Playwright (6.3) | Bước này mới có script kiểm tra nhanh `npm run smoke` (playwright-core + Chrome có sẵn, không tải trình duyệt) | Dùng để kiểm chứng giao diện ngay trong bước làm Frontend. Bộ E2E đầy đủ để lại cho giai đoạn kiểm thử (6.3) |
| 57 | Nginx phục vụ bản build, proxy `/api` (6.4) | Hiện chạy bằng Vite dev server có proxy `/api` | Triển khai Docker/Nginx thuộc giai đoạn 6.4 |

### 2.9 Phần 6 – Kiểm thử, hiệu năng và triển khai

Số liệu đầy đủ trong [docs/KET_QUA_KIEM_THU.md](../docs/KET_QUA_KIEM_THU.md). Tóm tắt:

| Mục tiêu của kế hoạch | Kết quả đo | Đạt |
|---|---|---|
| Truy vấn SQL ≤ 100 ms, không Seq Scan trên bảng lớn (x1 và x10) | chậm nhất 1,71 ms (x1) · 8,55 ms (x10, 1,46 triệu dòng) | ✔ |
| API 50 người dùng đồng thời: p95 < 500 ms, p99 < 1 s, lỗi < 0,1% | x1: p95 16 ms, p99 230 ms · x10: p95 22 ms, p99 37 ms · 0 lỗi trên 20.302 request | ✔ |
| Tải trang: biểu đồ đầu < 1 s, LCP < 2,5 s, TTI < 3 s | 335–409 ms · 360–428 ms · 389–461 ms | ✔ |
| ETL: traffic < 30 s, risk < 5 phút, nightly < 20 phút | 0,10 s · 60,05 s · 60,12 s (trên 9.677 lượt ghi danh) | ✔ |
| Export: Excel 10.000 dòng và PDF 500 dòng < 5 s | Excel 23.830 dòng 4,48 s · PDF 408 dòng 0,53 s | ✔ |
| E2E, phân quyền, responsive, WCAG AA | 27 test Playwright chạy trên bản Docker, không còn vi phạm serious/critical | ✔ |
| Triển khai một lệnh | `docker compose up` dựng 5 dịch vụ; `init` sinh dữ liệu và backfill trong 111 giây | ✔ |

**Hai lỗi thật được phát hiện nhờ Phần 6 và đã sửa:**

1. **Tranh chấp keep-alive.** Vài request lẻ mất 30–69 giây dù p95 rất thấp. Bật ghi truy vấn chậm của PostgreSQL cho thấy không có truy vấn nào quá 1 giây, nên nguyên nhân không ở CSDL: uvicorn đóng kết nối nhàn rỗi sau 5 giây, trùng khoảng nghỉ 2–5 giây của người dùng. Đặt `--timeout-keep-alive 65` thì request chậm nhất còn 0,55 giây.
2. **Bốn lỗi tương phản và nhãn trợ năng** (nút chính, chữ phụ, thẻ trạng thái bài tập, thanh tiến độ không có tên) do axe-core phát hiện – đã sửa bằng cách đổi token màu và thêm `aria-label`.

---

## 4. VIỆC CÒN LẠI

| Hạng mục | Tham chiếu kế hoạch | Ghi chú |
|---|---|---|
| Khảo sát ý kiến giảng viên (UAT), báo cáo, slide, video demo | 6.1, 6.5 | Cần người thật tham gia |
| Lighthouse chính thức | 6.2 | Trang cần đăng nhập nên đang đo bằng Playwright (LCP, TBT, TTI xấp xỉ) |
| Giảm dung lượng gói Frontend | 6.2 | Gói chính 924 KB (gzip 299 KB), chủ yếu là Ant Design. Trên máy CPU chậm 4× thì biểu đồ đầu tiên mất 1,4–2,1 giây (máy bình thường: 0,34–0,41 giây) |
| Đo hiệu năng trên máy chủ riêng | 6.2 | Hiện Locust và API chạy cùng một máy nên số đo là cận trên |
| Demo online thời gian thực (`live_sessions.py`) | 3.3 ghi chú 4 | Xem #9 |
| Dọn CSDL dùng cho đo hiệu năng | – | `lms_analytics_x10` (2,6 GB), `moodle_src_x4` (2,0 GB), `lms_analytics_etlbench` – xóa được bằng `DROP DATABASE` khi không cần đo lại |
| Bộ đếm đăng nhập sai dùng chung khi chạy nhiều worker | – | Hiện nằm trong bộ nhớ của một tiến trình; khi triển khai nhiều worker cần Redis hoặc bảng CSDL |
| Đổi mật khẩu tài khoản demo | – | Mật khẩu tạm `Lms@2026demo` chỉ dùng cho môi trường local |

---

## 5. CÁCH CHẠY LẠI TOÀN BỘ

```powershell
Copy-Item .env.example .env                              # điền mật khẩu PostgreSQL, BACKEND_JWT_SECRET; giữ LMS_AS_OF
python -m pip install -r requirements.txt
python -m database.migrate up --target analytics
python -m database.migrate up --target moodle
python -m mockdata.seed_structure --reset
python -m mockdata.generate_activity --reset              # ~1 phút
python -m etl.jobs.backfill --from 2026-09-07             # ~6 phút
$env:BACKEND_SEED_PASSWORD = "<mật khẩu ban đầu>"
python -m backend.app.cli sync-users                      # tài khoản admin + giảng viên
python -m pytest -q                                       # 235 test
python -m uvicorn backend.app.main:app --port 8000        # API: http://localhost:8000/api/docs
python -m etl.scheduler                                   # chạy ETL tự động (tùy chọn, cửa sổ khác)

# Frontend (cửa sổ khác)
cd frontend
npm install
npm run dev                                               # http://localhost:5173
npm test; npm run build
$env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"; npm run smoke # kiểm tra bằng trình duyệt thật
```

> Nếu CSDL phân tích đã có từ trước V007: chạy `python -m database.migrate up --target analytics` rồi `python -m etl.jobs.backfill --from 2026-09-07`.

> Đổi `LMS_AS_OF` thì phải chạy lại `generate_activity --reset` và `backfill`.
