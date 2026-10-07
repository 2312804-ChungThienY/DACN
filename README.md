# LMS Analytics — Trực quan hóa dữ liệu hệ thống LMS Moodle

> Đồ án chuyên ngành: *Trực quan hóa dữ liệu hệ thống LMS Moodle phục vụ công tác quản lý và hỗ trợ giảng dạy*
> Khoa Công nghệ Thông tin — Trường Đại học Đà Lạt

Hệ thống đọc dữ liệu thô từ Moodle, chạy tiến trình ETL để tính toán sẵn các chỉ số, rồi hiển thị lên dashboard cho hai nhóm người dùng:

- **Quản trị viên** — theo dõi quy mô đào tạo, lưu lượng truy cập máy chủ, xuất báo cáo Excel/PDF.
- **Giảng viên** — nhận cảnh báo "đèn giao thông" về sinh viên có nguy cơ bỏ học, theo dõi tiến độ lớp.

```
Moodle (moodle_src)  ──ETL Python──▶  PostgreSQL lms_analytics  ──FastAPI──▶  React + Chart.js
   26 bảng mdl_*         5 phút /          3 bảng fact              JWT, RBAC      Admin · Giảng viên
   1,2 triệu dòng log    giờ / đêm         145.702 dòng             Excel/PDF
```

---

## Mục lục

| # | Phần | Dành cho ai |
|---|---|---|
| [1](#1-công-nghệ-sử-dụng) | Công nghệ sử dụng | Người đọc muốn biết dự án dùng gì |
| [2](#2-yêu-cầu-hệ-thống) | Yêu cầu hệ thống | Người sắp cài |
| [3](#3-hướng-dẫn-cài-đặt-và-chạy) | **Hướng dẫn cài đặt và chạy** | Lập trình viên |
| [4](#4-hướng-dẫn-sử-dụng-web) | **Hướng dẫn sử dụng web** | Người dùng cuối |
| [5](#5-tài-khoản-đăng-nhập) | Tài khoản đăng nhập | Ai cũng cần |
| [6](#6-những-gì-không-đi-theo-gói) | Những gì KHÔNG đi theo gói | Người vừa clone về |
| [7](#7-cách-web-hoạt-động) | Cách web hoạt động | Người muốn hiểu kiến trúc |
| [8](#8-cách-xem-cơ-sở-dữ-liệu) | Cách xem cơ sở dữ liệu | Người kiểm tra dữ liệu |
| [9](#9-cấu-trúc-dự-án--tác-dụng-từng-file) | Cấu trúc dự án — tác dụng từng file | Người sắp sửa code |
| [10](#10-kiểm-thử) | Kiểm thử | Người muốn kiểm chứng |
| [11](#11-xử-lý-sự-cố) | Xử lý sự cố | Khi gặp lỗi |

---

## 1. Công nghệ sử dụng

### Tầng cơ sở dữ liệu

| Công nghệ | Phiên bản | Vai trò trong dự án |
|---|---|---|
| **PostgreSQL** | 18 | Hai CSDL: `moodle_src` (nguồn, mô phỏng Moodle) và `lms_analytics` (kho phân tích) |
| **psycopg** | 3.2 | Driver PostgreSQL cho Python, dùng `COPY` để nạp hàng loạt |
| **SQLAlchemy Core** | 2.0 | Quản lý connection pool, viết SQL có tham số bind |

Migration tự viết (`database/migrate.py`), không dùng Alembic — file SQL đặt tên `V001__*.sql` và áp dụng tăng dần, ghi lại checksum vào bảng `schema_migrations`.

### Tầng ETL

| Công nghệ | Phiên bản | Vai trò |
|---|---|---|
| **Python** | 3.11+ | Ngôn ngữ chính |
| **pandas** | 2.2 | Gộp, tính toán chỉ số trên bảng dữ liệu |
| **NumPy** | 1.26 | Sinh dữ liệu giả lập, tính vector hóa |
| **APScheduler** | 3.10 | Lập lịch chạy job tự động (5 phút / giờ / đêm / tuần) |

### Tầng API

| Công nghệ | Phiên bản | Vai trò |
|---|---|---|
| **FastAPI** | 0.115 | Framework REST API, tự sinh tài liệu Swagger |
| **Uvicorn** | 0.30+ | ASGI server chạy FastAPI |
| **Pydantic** | v2 (theo FastAPI) | Kiểm tra kiểu dữ liệu request/response |
| **PyJWT** | 2.9 | Ký và xác thực token JWT (HS256) |
| **bcrypt** | 4.2 | Băm mật khẩu một chiều |
| **cachetools** | 5.5 | Cache TTL 60 giây cho endpoint KPI |
| **openpyxl** | 3.1 | Xuất báo cáo Excel (chế độ write-only) |
| **ReportLab** | 4.2 | Xuất báo cáo PDF khổ A4 ngang |

### Tầng giao diện

| Công nghệ | Phiên bản | Vai trò |
|---|---|---|
| **React** | 18.3 | Thư viện giao diện |
| **Vite** | 5.4 | Công cụ build và dev server (hot-reload) |
| **Ant Design** | 5.21 | Bộ thành phần giao diện (bảng, modal, bộ lọc) — tiếng Việt |
| **Chart.js** | 4.4 | Vẽ biểu đồ |
| **react-chartjs-2** | 5.2 | Cầu nối Chart.js với React |
| **chartjs-chart-matrix** | 2.0 | Vẽ heatmap giờ × thứ |
| **chartjs-plugin-annotation** | 3.1 | Tô vùng giờ cao điểm trên biểu đồ |
| **TanStack React Query** | 5.59 | Quản lý dữ liệu từ API, cache, tự làm mới 60 giây |
| **React Router** | 6.27 | Định tuyến theo vai trò |
| **axios** | 1.7 | Gọi HTTP, gắn JWT, tải file Excel/PDF |
| **dayjs** | 1.11 | Xử lý ngày giờ |

### Kiểm thử và đo đạc

| Công nghệ | Vai trò |
|---|---|
| **pytest** | Kiểm thử Python: đơn vị, tích hợp, API |
| **httpx** | HTTP client cho TestClient của FastAPI |
| **Vitest** | Kiểm thử đơn vị JavaScript |
| **Playwright** | Kiểm thử đầu-cuối trên trình duyệt thật |
| **axe-core** | Kiểm tra khả năng tiếp cận WCAG 2.1 A/AA |
| **Locust** | Kiểm thử tải API (50 người dùng đồng thời) |

### Đóng gói

| Công nghệ | Vai trò |
|---|---|
| **Docker + Docker Compose** | Demo trọn gói 5 dịch vụ bằng một lệnh |
| **Nginx** | Phục vụ bản build React, proxy `/api` sang backend |

---

## 2. Yêu cầu hệ thống

### Cách 1 — Chạy trực tiếp (khuyến nghị khi phát triển)

| Phần mềm | Phiên bản tối thiểu | Ghi chú khi cài |
|---|---|---|
| PostgreSQL | 18 | Nhớ kỹ mật khẩu user `postgres` đặt lúc cài |
| Python | 3.11 | Tick **"Add Python to PATH"** |
| Node.js | 18 (bản LTS) | Đã kèm npm |
| Git | bất kỳ | Để clone dự án |

Dung lượng đĩa cần: khoảng **1,5 GB** (mã nguồn 7 MB + thư viện 160 MB + hai CSDL 830 MB).

### Cách 2 — Chạy bằng Docker

Chỉ cần **Docker Desktop**. Không cần cài PostgreSQL, Python hay Node.js.

---

## 3. Hướng dẫn cài đặt và chạy

> Phần này dành cho người sẽ chạy hoặc sửa mã nguồn.
> Nếu chỉ muốn biết cách **dùng** dashboard, xem [Phần 4](#4-hướng-dẫn-sử-dụng-web).

### 3.1 Tải mã nguồn

```powershell
git clone https://github.com/ThangThieng/Do_an_chuyen_nganh.git
cd Do_an_chuyen_nganh
```

### 3.2 Tạo file cấu hình `.env`

File `.env` chứa mật khẩu nên **không** được đưa lên Git. Bạn tự tạo từ file mẫu:

```powershell
Copy-Item .env.example .env
notepad .env
```

Điền 4 giá trị:

```ini
ANALYTICS_DB_PASSWORD=<mật khẩu postgres trên MÁY BẠN>
MOODLE_DB_PASSWORD=<mật khẩu postgres trên MÁY BẠN>
BACKEND_JWT_SECRET=<sinh bằng lệnh bên dưới>
LMS_AS_OF=2026-11-06T10:30:00+07:00
```

Sinh khóa JWT ngẫu nhiên:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> ⚠️ **`LMS_AS_OF` phải đúng y hệt dòng trên.** Đây là "thời điểm tham chiếu" đóng băng đồng hồ của toàn hệ thống. Dữ liệu giả lập mô phỏng học kỳ 1 năm học 2026–2027 (bắt đầu 07/09/2026), và mốc `2026-11-06` là tuần 9. Đặt sai giá trị này, dữ liệu sinh ra sẽ khác và không đối chiếu được với tài liệu.

### 3.3 Cài đặt và dựng dữ liệu

Chạy lần lượt, đợi từng lệnh xong hẳn. Tổng thời gian khoảng **10–15 phút**.

```powershell
# 1. Cài thư viện Python + npm, tạo bảng trong 2 CSDL          (~3 phút)
.\scripts\lms.ps1 setup

# 2. Sinh cấu trúc Moodle: 15 môn, 500 SV, 8 giảng viên        (~1 phút)
.\scripts\lms.ps1 seed

# 3. Sinh hành vi học tập: 1,2 triệu dòng log truy cập         (~4 phút)
.\scripts\lms.ps1 mock

# 4. Chạy ETL nạp 3 bảng fact                                  (~6 phút)
.\scripts\lms.ps1 etl-backfill

# 5. Tạo 9 tài khoản đăng nhập
$env:BACKEND_SEED_PASSWORD = "Lms@2026demo"
.\scripts\lms.ps1 users
```

Trên Linux/macOS dùng `make setup`, `make seed`, … (xem [Makefile](Makefile)).

### 3.4 Chạy hệ thống

Mở **hai cửa sổ PowerShell**, cùng ở thư mục dự án:

```powershell
# ───── Cửa sổ 1: Backend API ─────
.\scripts\lms.ps1 api
```
→ API chạy ở `http://localhost:8000`, tài liệu Swagger ở `http://localhost:8000/api/docs`

```powershell
# ───── Cửa sổ 2: Frontend ─────
.\scripts\lms.ps1 web
```
→ Mở trình duyệt vào **`http://localhost:5173`**

Frontend tự chuyển tiếp mọi request `/api` sang `http://127.0.0.1:8000` nhờ cấu hình proxy trong [frontend/vite.config.js](frontend/vite.config.js) — không cần sửa CORS.

### 3.5 Bảng tra cứu toàn bộ lệnh

| Lệnh tắt | Lệnh đầy đủ tương đương | Tác dụng |
|---|---|---|
| `lms.ps1 setup` | `pip install -r requirements.txt` + `npm install` + `python -m database.migrate up` | Cài thư viện, tạo bảng |
| `lms.ps1 seed` | `python -m mockdata.seed_structure --reset` | Sinh cấu trúc Moodle |
| `lms.ps1 mock` | `python -m mockdata.generate_activity --reset` | Sinh hành vi học tập |
| `lms.ps1 etl-backfill` | `python -m etl.jobs.backfill --from 2026-09-07` | Nạp lịch sử 3 bảng fact |
| `lms.ps1 users` | `python -m backend.app.cli sync-users` | Tạo/cập nhật tài khoản |
| `lms.ps1 api` | `python -m uvicorn backend.app.main:app --port 8000` | Chạy Backend |
| `lms.ps1 web` | `cd frontend; npm run dev` | Chạy Frontend |
| `lms.ps1 test` | `python -m pytest -q` + `npm test` | Kiểm thử |
| `lms.ps1 e2e` | `npx playwright test` | Kiểm thử giao diện thật |
| `lms.ps1 bench` | `python -m perf.build_x10` + `explain_queries` | Đo hiệu năng |
| `lms.ps1 docker` | `docker compose up --build -d` | Demo bằng Docker |
| — | `python -m etl.scheduler` | Chạy ETL tự động nền (tùy chọn) |

### 3.6 Chạy bằng Docker (không cần cài PostgreSQL/Python/Node)

```powershell
Copy-Item docker/.env.example docker/.env
notepad docker/.env
```

Điền hai giá trị:
```ini
BACKEND_JWT_SECRET=<chuỗi ngẫu nhiên >= 32 ký tự>
BACKEND_SEED_PASSWORD=Lms@2026demo
```

Rồi chạy:
```powershell
docker compose --env-file docker/.env up --build -d
     # chờ dòng "[init] Hoàn tất." (~5–8 phút)
```

Mở **`http://localhost:8080`**.

Compose gồm 5 dịch vụ:

| Dịch vụ | Vai trò |
|---|---|
| `db` | PostgreSQL 18, cổng **không** mở ra máy |
| `init` | Chạy một lần: migrate → seed → mock → ETL backfill → tạo tài khoản |
| `etl` | APScheduler chạy nền |
| `backend` | FastAPI, 2 worker |
| `web` | Nginx phục vụ bản build React và proxy `/api` |

Dữ liệu nằm trong volume `pgdata`. Lệnh `docker compose down -v` xóa sạch để làm lại từ đầu.

> ⚠️ **Hai cách chạy dùng hai CSDL hoàn toàn tách biệt.** Đổi mật khẩu ở bản local không ảnh hưởng bản Docker và ngược lại. Bản local chạy ở cổng **5173**, bản Docker ở cổng **8080**.

---

## 4. Hướng dẫn sử dụng web

> Phần này dành cho người dùng cuối — quản trị viên và giảng viên.
> Không cần biết lập trình.

### 4.1 Đăng nhập

![Trang đăng nhập](docs/images/00_login_error.png)

Nhập tên đăng nhập và mật khẩu (xem [Phần 5](#5-tài-khoản-đăng-nhập)). Hệ thống tự đưa bạn tới trang phù hợp với vai trò:

- Tài khoản **quản trị** → trang Tổng quan
- Tài khoản **giảng viên** → trang Cảnh báo của môn đầu tiên

Khi nhập sai, hệ thống chỉ báo *"Sai tên đăng nhập hoặc mật khẩu"* mà không nói rõ sai ở đâu — đây là chủ ý, để không tiết lộ tài khoản nào có tồn tại. Nhập sai nhiều lần liên tiếp sẽ bị tạm khóa vài phút.

---

### PHẦN DÀNH CHO QUẢN TRỊ VIÊN

### 4.2 Trang Tổng quan

![Trang tổng quan](docs/images/01_admin_overview.png)

Màn hình chia làm 6 khu vực, từ trên xuống:

**① Hàng bộ lọc** — Năm học · Học kỳ · Khoa.
Mọi biểu đồ và bảng bên dưới đổi theo bộ lọc này. Nút **Export** xuất ngay báo cáo theo đúng bộ lọc đang chọn.

**② Sáu thẻ KPI** — các con số tổng quan:

| Thẻ | Ý nghĩa |
|---|---|
| Tổng môn học | Số môn đang diễn ra trong học kỳ đã chọn |
| Sinh viên đăng ký | Tổng lượt ghi danh còn hiệu lực |
| Sinh viên có tương tác | Số em thực sự vào học, kèm tỷ lệ % |
| Người đang online | Đếm theo thời gian thực, tự làm mới mỗi 60 giây |
| Giờ cao điểm hôm nay | Khung giờ có nhiều truy cập nhất |
| Sinh viên nguy cơ cao | Số em bị đánh dấu ĐỎ |

**③ Biểu đồ đường 2 trục** — chọn xem 24 giờ hoặc 7 ngày.
Trục trái là số request mỗi giờ (**nét liền**), trục phải là số người online (**nét đứt**). Hai kiểu nét khác nhau để không đọc nhầm thang đo. Vùng nền tô đậm là giờ cao điểm.

**④ Biểu đồ cột chồng theo khoa** — mỗi cột chia hai phần: sinh viên có tương tác và không tương tác.
**Nhấn vào một cột** để xem danh sách môn của khoa đó.

**⑤ Bảng phân cấp** Khoa ▸ Môn ▸ Sinh viên, có thanh breadcrumb để quay lại cấp trên.

**⑥ Heatmap giờ × thứ** của 4 tuần gần nhất. Ô càng đậm thì giờ đó càng đông.

> 💡 Mọi biểu đồ đều có nút **"Biểu đồ | Bảng"** để xem cùng số liệu ở dạng bảng — tiện khi cần chép số vào báo cáo.

### 4.3 Xem chi tiết tới từng sinh viên

![Drill-down danh sách sinh viên](docs/images/02_admin_drilldown_students.png)

Đường đi ba cấp:

```
Nhấn dòng khoa
      ↓
Danh sách 15 môn học  (sắp xếp được theo tỷ lệ tương tác, số SV, số nguy cơ đỏ)
      ↓  nhấn nút "Xem SV"
Danh sách sinh viên của môn
```

Ở cấp sinh viên có thể:
- Lọc **Có tương tác / Không tương tác**
- Tìm theo MSSV, họ tên hoặc email
- Xem lần truy cập cuối cùng và mức rủi ro của từng em

### 4.4 Trang Lưu lượng

![Trang lưu lượng](docs/images/03_admin_traffic.png)

| Thành phần | Cách dùng |
|---|---|
| Chọn khoảng ngày | Có sẵn mốc nhanh: hôm nay, 7 ngày, 30 ngày, 90 ngày |
| Thẻ **Online hiện tại** | Tự làm mới mỗi 60 giây |
| Biểu đồ 2 trục | Requests/giờ và người online |
| **Top 10 giờ đông nhất** | Cho biết chính xác giờ nào tải cao nhất |
| Heatmap | Chọn được 1–12 tuần |

### 4.5 Trang Báo cáo

![Trang báo cáo](docs/images/04_admin_reports_preview.png)

Quy trình 4 bước:

1. **Chọn loại báo cáo** — quy mô đào tạo / cảnh báo sinh viên / lưu lượng truy cập
2. **Đặt bộ lọc** — năm học, học kỳ, khoa, môn, mức rủi ro…
3. **Nhấn "Xem trước"** — bảng dữ liệu hiện ra có phân trang, kiểm tra trước khi xuất
4. **Nhấn "Xuất Excel" hoặc "Xuất PDF"**

| Định dạng | Đặc điểm |
|---|---|
| **Excel** | Giữ nguyên kiểu số và kiểu ngày, mở ra lọc và tính toán được ngay |
| **PDF** | Khổ A4 ngang, lặp tiêu đề mỗi trang, tô màu theo mức rủi ro |

---

### PHẦN DÀNH CHO GIẢNG VIÊN

### 4.6 Trang Cảnh báo

![Trang cảnh báo](docs/images/05_teacher_risk.png)

**Bước 1 — Chọn môn** ở thanh tiêu đề. Danh sách chỉ hiện các môn bạn dạy.

**Bước 2 — Ba thẻ đèn giao thông.** Nhấn vào một thẻ để lọc bảng bên dưới theo mức đó.

| Mức | Hiển thị | Ý nghĩa |
|---|---|---|
| 🔴 | `● Nguy cơ cao` | Cần liên hệ ngay |
| 🟡 | `▲ Cần lưu ý` | Theo dõi thêm |
| 🟢 | `✔ An toàn` | Bình thường |

> ♿ Mức rủi ro **luôn có biểu tượng và chữ đi kèm**, không bao giờ chỉ dùng màu. Lý do: người mù màu đỏ–lục không phân biệt được hai màu này (độ khác biệt ΔE chỉ 3,5).

**Bước 3 — Biểu đồ tròn.** Nhấn một lát cắt hoặc một dòng chú thích để lọc. Bên dưới là số sinh viên theo từng tiêu chí (vắng học / không tương tác / thiếu bài tập) — cũng nhấn để lọc được.

**Bước 4 — Bảng cảnh báo.** Mặc định sắp xếp ĐỎ → VÀNG → XANH, trong cùng mức thì điểm cao lên trước. Bảng có:
- Ô tìm kiếm theo MSSV / họ tên
- Bộ lọc theo mức và theo tiêu chí
- Sắp xếp theo từng cột
- Nút xuất danh sách ra Excel / PDF

**Bước 5 — Nhấn "Chi tiết"** ở mỗi dòng để mở cửa sổ chi tiết.

### 4.7 Cửa sổ chi tiết sinh viên

![Cửa sổ chi tiết sinh viên](docs/images/06_teacher_student_modal.png)

Cửa sổ này trả lời câu hỏi **"vì sao em này bị đánh dấu đỏ?"**

| Thành phần | Nội dung |
|---|---|
| **Dòng Lý do** | Viết bằng câu chữ rõ ràng: *"Vắng 9/18 buổi (50%) · Chưa từng truy cập môn học · Thiếu 3/3 bài tập"* |
| **Biểu đồ so sánh** | Đối chiếu sinh viên này với trung bình lớp |
| **Biểu đồ hoạt động theo tuần** | Chấm tròn **đặc** = tuần đi học đủ, chấm **rỗng** = tuần có buổi vắng |
| **Danh sách bài tập** | Trạng thái đúng hạn / trễ hạn / thiếu / chưa tới hạn |
| **Lịch sử cảnh báo** | Mức rủi ro thay đổi qua các tuần |
| **Can thiệp trước đây** | Những lần giảng viên đã liên hệ |

**Bốn nút hành động** ở cuối cửa sổ: Gửi tin nhắn Moodle · Email · Ghi chú · Hẹn gặp.

Mỗi hành động được ghi vào nhật ký can thiệp kèm mức rủi ro tại thời điểm đó, để sau này biết đã làm gì và kết quả ra sao.

### 4.8 Trang Tiến độ lớp

![Trang tiến độ lớp](docs/images/07_teacher_progress.png)

| Thành phần | Cho biết điều gì |
|---|---|
| Ba thanh tiến độ | Hoàn thành hoạt động · Nộp bài · Chuyên cần |
| Tiến độ từng chương/tuần | Lớp đang học tới đâu, chương nào bị bỏ lại |
| Biểu đồ sinh viên hoạt động | Theo tuần hoặc theo ngày |
| Biểu đồ tỷ lệ tiến độ | Xu hướng theo thời gian |

### 4.9 Dùng trên điện thoại

![Giao diện trên điện thoại](docs/images/08_mobile_teacher_risk.png)

Giao diện dùng được từ màn hình rộng 390 px trở lên: các thẻ xếp dọc, bảng cuộn ngang trong khung riêng, trang không bao giờ bị cuộn ngang.

### 4.10 Quy ước hiển thị cần biết

| Quy ước | Giải thích |
|---|---|
| **"Chưa có dữ liệu"** | Khác hẳn "0%". Ví dụ môn chưa có buổi điểm danh nào thì tỷ lệ chuyên cần là "chưa có dữ liệu", không phải "vắng 0%" |
| **"Cập nhật lúc…"** trên header | Thời điểm ETL chạy lần cuối, không phải giờ hiện tại của máy bạn |
| **Nút "Biểu đồ \| Bảng"** | Mọi biểu đồ đều xem được ở dạng bảng số liệu |
| **Màu luôn kèm ký hiệu** | `●` `▲` `✔` — bảo đảm người mù màu vẫn đọc được |

---

## 5. Tài khoản đăng nhập

Mật khẩu mặc định của **tất cả** tài khoản: `Lms@2026demo`
(chính là giá trị `BACKEND_SEED_PASSWORD` bạn đặt ở bước 3.3)

### Quản trị viên

| Tên hiển thị | Username | Vai trò | Xem được gì |
|---|---|---|---|
| Quản trị Hệ thống | `admin` | ADMIN | Tổng quan · Lưu lượng · Báo cáo |

### Giảng viên

| Tên hiển thị | Username | Môn phụ trách | Số SV |
|---|---|---|---:|
| Trần Minh Hùng | `gv.tranminhhung` | IT001 Nhập môn lập trình · IT002 Toán rời rạc | 287 |
| Nguyễn Thị Lan | `gv.nguyenthilan` | IT003 Cấu trúc dữ liệu và giải thuật · IT010 Trí tuệ nhân tạo | 270 |
| Lê Quốc Bảo | `gv.lequocbao` | IT004 Cơ sở dữ liệu · IT005 Hệ quản trị cơ sở dữ liệu | 304 |
| Phạm Thu Hà | `gv.phamthuha` | IT006 Phân tích thiết kế HTTT · IT011 Kho dữ liệu và khai phá dữ liệu | 326 |
| Võ Thanh Tâm | `gv.vothanhtam` | IT007 Lập trình hướng đối tượng · IT008 Công nghệ phần mềm | 250 |
| Đặng Ngọc Ánh | `gv.dangngocanh` | IT009 Lập trình Web · IT012 Kiểm thử phần mềm | 253 |
| **Bùi Đức Thắng** ⭐ | `gv.buiducthang` | IT004 Cơ sở dữ liệu · IT013 Mạng máy tính · IT014 Hệ điều hành | **315** |
| **Hồ Hải Yến** ⭐ | `gv.hohaiyen` | IT001 Nhập môn lập trình · IT009 Lập trình Web · IT015 An toàn thông tin | **350** |

⭐ = dạy 3 môn, nhiều dữ liệu nhất — nên dùng để demo.

Tất cả đều thuộc **Khoa Công nghệ Thông tin**. Dữ liệu giả lập chỉ mô phỏng 1 khoa với 4 bộ môn và 15 môn học.

### Đổi mật khẩu

```powershell
# Một tài khoản
python -m backend.app.cli set-password --username admin

# Tất cả tài khoản
$env:BACKEND_SEED_PASSWORD = "<mật khẩu mới>"
python -m backend.app.cli sync-users --reset-password
```

> 🔐 Mật khẩu **không bao giờ** được lưu dạng plaintext. CSDL chỉ chứa `password_hash` — chuỗi bcrypt 60 ký tự bắt đầu bằng `$2b$12$`. Bcrypt là hàm một chiều nên không thể khôi phục mật khẩu đã quên, chỉ có thể đặt lại.

---

## 6. Những gì KHÔNG đi theo gói

Sau khi `git clone`, hệ thống **chưa chạy được ngay**. Sáu thứ dưới đây cố ý không có trong repo và bạn phải tự tạo:

| Thứ thiếu | Dung lượng | Vì sao không có | Cách tạo lại |
|---|---:|---|---|
| **`.env`** | vài KB | Chứa mật khẩu và khóa JWT — đưa lên Git là lộ bí mật | `Copy-Item .env.example .env` rồi điền (mục 3.2) |
| **`docker/.env`** | vài KB | Như trên | `Copy-Item docker/.env.example docker/.env` |
| **`frontend/node_modules`** | **160 MB** | Thư viện tải về, `package-lock.json` đã ghi đủ phiên bản | `cd frontend && npm install` |
| **CSDL `moodle_src`** | **507 MB** | Nằm trong PostgreSQL, không nằm trong thư mục dự án | `lms.ps1 seed` + `lms.ps1 mock` |
| **CSDL `lms_analytics`** | **322 MB** | Như trên | `lms.ps1 setup` + `lms.ps1 etl-backfill` |
| **`frontend/dist`** | 1,5 MB | Bản build, sinh ra từ mã nguồn | `npm run build` |

Nhờ vậy repo chỉ nặng khoảng **7 MB** thay vì gần 1 GB.

### Vì sao không cần gửi kèm cơ sở dữ liệu?

File [mockdata/config.py](mockdata/config.py) đặt `RANDOM_SEED = 2026` **cố định**. Mọi máy chạy `seed` + `mock` với cùng `LMS_AS_OF` sẽ sinh ra dữ liệu **giống hệt nhau, từng dòng một**.

Kiểm chứng bằng lệnh sau — kết quả phải khớp với bảng bên dưới:

```powershell
python -c "import sys; sys.path.insert(0,'.'); import psycopg; from database.config import load_db_config; conn=psycopg.connect(**load_db_config('ANALYTICS_DB').conninfo()); print(conn.execute(\"SELECT risk_level, count(*) FROM analytics.fact_student_risk_summary WHERE snapshot_date='2026-11-06' GROUP BY 1 ORDER BY 1\").fetchall())"
```

| Mức rủi ro | Số lượng phải ra |
|---|---:|
| 🟢 GREEN | 1.308 |
| 🔴 RED | 408 |
| 🟡 YELLOW | 667 |

Ra số khác nghĩa là `LMS_AS_OF` trong `.env` chưa đúng.

---

## 7. Cách web hoạt động

### 7.1 Kiến trúc 5 tầng

```
┌────────────────────────────────────────────────────────────────┐
│ ① NGUỒN — moodle_src (507 MB, 26 bảng mdl_*)                   │
│   mdl_logstore_standard_log ....... 1.215.209 dòng             │
│   mdl_attendance_log .............. 36.933 dòng                │
│   mdl_assign_submission ........... 7.272 dòng                 │
│   ❌ Dữ liệu thô, muốn biết ai nguy cơ phải JOIN 12 bảng       │
└───────────────────────────┬────────────────────────────────────┘
                            │ CHỈ ĐỌC (read-only + timeout)
                 ┌──────────▼───────────┐
                 │ ② ETL — Python       │
                 │   Extract  (SQL)     │
                 │   Transform (pandas) │  ← chấm điểm đèn giao thông
                 │   Load  (COPY+UPSERT)│
                 └──────────┬───────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ ③ KHO PHÂN TÍCH — lms_analytics (322 MB)                       │
│   fact_student_risk_summary ... 145.702 dòng  ✅ đã chấm điểm  │
│   fact_course_progress_daily ..     915 dòng  ✅ đã gộp        │
│   fact_server_traffic_hourly ..   1.451 dòng  ✅ đã đếm        │
└───────────────────────────┬────────────────────────────────────┘
                            │
                 ┌──────────▼───────────┐
                 │ ④ API — FastAPI      │
                 │   JWT · RBAC · Cache │
                 │   Excel · PDF        │
                 └──────────┬───────────┘
                            │ JSON qua HTTP
                 ┌──────────▼───────────┐
                 │ ⑤ WEB — React        │
                 │   Chart.js · AntD    │
                 └──────────────────────┘
```

### 7.2 Vì sao phải tách kho phân tích riêng?

| Vấn đề khi truy vấn thẳng Moodle | Giải pháp của dự án |
|---|---|
| Phải JOIN 12 bảng, quét 1,2 triệu dòng log → mất **vài phút** | Tính trước, lưu sẵn vào bảng fact → còn **dưới 40 ms** |
| Chạy truy vấn nặng làm chậm Moodle mà sinh viên đang dùng thật | ETL kết nối **read-only** có timeout, chạy lúc rảnh |
| Moodle không có khái niệm "học kỳ", "mức rủi ro" | ETL tự suy ra và lưu vào bảng fact |

### 7.3 Vòng đời một request

Ví dụ: giảng viên Bùi Đức Thắng mở trang Cảnh báo môn IT004.

```
① TRÌNH DUYỆT gửi
   GET /api/v1/teacher/courses/6/risk-students?level=RED
   Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
        │
        ▼
② BACKEND kiểm tra vé vào cửa
   ├─ security.py giải mã JWT → user_id=9, role=TEACHER
   │  └─ token hết hạn?  → trả 401
   └─ teacher.py: teacher_ids của môn 6 = {5, 9}, có chứa 9 không?
      └─ không có       → trả 403
        │
        ▼
③ REPOSITORY chạy SQL trên bảng fact
   SELECT student_code, student_name, risk_score, risk_level, ...
   FROM analytics.fact_student_risk_summary
   WHERE course_id = 6
     AND snapshot_date = '2026-11-06'
     AND risk_level = 'RED'
     AND teacher_ids @> ARRAY[9]     ← phân quyền lần 2, ngay trong SQL
   ORDER BY risk_score DESC;
        │
        ▼
④ BACKEND đóng gói JSON  { "total": 30, "items": [...] }
        │
        ▼
⑤ REACT QUERY nhận, cache lại, tự làm mới sau 60 giây
        │
        ▼
⑥ CHART.JS vẽ doughnut + bảng cảnh báo lên màn hình
```

### 7.4 Ba lớp bảo vệ độc lập

| Lớp | Ở đâu | Làm gì |
|---|---|---|
| **1. Giao diện** | [ProtectedRoute.jsx](frontend/src/routes/ProtectedRoute.jsx) | Ẩn/chặn trang không đúng vai trò |
| **2. API** | [security.py](backend/app/core/security.py) `require_role()` | Trả 401 nếu token sai/hết hạn, 403 nếu sai vai trò |
| **3. Dữ liệu** | [repositories/teacher.py](backend/app/repositories/teacher.py) | Mọi câu SQL kèm `teacher_ids @> ARRAY[:teacher_id]` |

Ba lớp độc lập nhau. Người dùng có sửa JavaScript trong trình duyệt để vượt lớp 1 thì lớp 2 và 3 vẫn chặn.

### 7.5 Luật chấm điểm "đèn giao thông"

Đây là nghiệp vụ cốt lõi, cài đặt ở [etl/transform/risk_rules.py](etl/transform/risk_rules.py):

| Tiêu chí | 🟢 0 điểm | 🟡 1 điểm | 🔴 2 điểm |
|---|---|---|---|
| **C1** Vắng học | < 15% | 15% – < 30% | ≥ 30% |
| **C2** Không tương tác | vào gần đây | khá lâu | rất lâu |
| **C3** Thiếu bài tập | 0 bài | ít bài | nhiều bài |

Tổng điểm 3 tiêu chí quyết định `risk_level` = RED / YELLOW / GREEN.
Luật này được kiểm thử với **≥ 20 ca biên**, yêu cầu 100% pass ([tests/etl/test_risk_rules.py](tests/etl/test_risk_rules.py)).

### 7.6 Lịch chạy ETL tự động

| Job | Lịch | Việc |
|---|---|---|
| `traffic` | mỗi **5 phút** | Cập nhật lưu lượng, chụp mẫu người online |
| `course_progress` | mỗi **1 giờ** | Cập nhật tiến độ môn trong ngày |
| `student_risk` | mỗi **2 giờ** (07h–21h) | Chấm lại điểm rủi ro, ghi đè snapshot hôm nay |
| `nightly` | **01:00** hằng đêm | Chốt số liệu ngày hôm qua tại 23:59:59 |
| `maintenance` | **CN 03:00** | Tỉa snapshot cũ hơn 180 ngày, `VACUUM ANALYZE` |

Mỗi job dùng `pg_try_advisory_lock` để không chạy chồng lên nhau, và ghi lại kết quả vào bảng `etl_run_log`.

---

## 8. Cách xem cơ sở dữ liệu

### 8.1 Hai cơ sở dữ liệu cần phân biệt

| | `moodle_src` | `lms_analytics` |
|---|---|---|
| Vai trò | **Nguồn** — mô phỏng Moodle thật | **Đích** — kho phân tích |
| Schema | `public` | `analytics` |
| Số bảng | 26 (`mdl_*`) | 8 |
| Dung lượng | 507 MB | 322 MB |
| Ai ghi vào | `mockdata/` | `etl/` |
| Ai đọc | `etl/` (chỉ đọc) | `backend/` |

### 8.2 Xem bằng psql (dòng lệnh)

`psql.exe` thường **chưa có trong PATH** sau khi cài PostgreSQL trên Windows:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d lms_analytics
```

Hoặc thêm vào PATH một lần cho tiện:

```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\PostgreSQL\18\bin", "User")
```

Lệnh cơ bản trong psql:

| Lệnh | Tác dụng |
|---|---|
| `\l` | Liệt kê tất cả CSDL |
| `\dt analytics.*` | Liệt kê bảng trong schema `analytics` |
| `\d analytics.fact_student_risk_summary` | Xem cấu trúc, khóa, index của bảng |
| `\x` | Bật hiển thị dọc (dễ đọc khi bảng nhiều cột) |
| `\q` | Thoát |

### 8.3 Xem bằng pgAdmin 4 (giao diện đồ họa)

pgAdmin đi kèm bộ cài PostgreSQL. Mở **Start → PostgreSQL 18 → pgAdmin 4**.

```
Servers
└── PostgreSQL 18                    ← nhập mật khẩu user postgres
    └── Databases
        ├── lms_analytics
        │   └── Schemas
        │       └── analytics        ← chú ý: KHÔNG phải "public"
        │           └── Tables (8)
        └── moodle_src
            └── Schemas
                └── public
                    └── Tables (26)
```

- Xem dữ liệu: chuột phải bảng → **View/Edit Data** → **First 100 Rows**
- Gõ SQL: menu **Tools** → **Query Tool**

> ⚠️ Nếu báo `password authentication failed`: kiểm tra xem có vô tình gõ cả dấu nháy `'` không. Trong file `.env`, dấu nháy chỉ là cú pháp bao chuỗi, **không thuộc mật khẩu**.

### 8.4 Xem sơ đồ quan hệ (ERD)

**Với `lms_analytics`** — pgAdmin vẽ được ngay:
chuột phải database → **ERD For Database** → **Auto-layout** → **Download image**.

Schema này có 5 khóa ngoại thật:

```
  etl_run_log (run_id)
       ▲  ▲  ▲  ▲
       │  │  │  └──── etl_online_snapshot.etl_run_id
       │  │  └─────── fact_server_traffic_hourly.etl_run_id
       │  └────────── fact_course_progress_daily.etl_run_id
       └───────────── fact_student_risk_summary.etl_run_id

  app_user (user_id) ◀── intervention_log.teacher_id
```

**Với `moodle_src`** — cần thêm một bước. CSDL này có **0 khóa ngoại**, vì Moodle thật cũng không dùng khóa ngoại ở tầng CSDL (nó kiểm soát quan hệ ở tầng code PHP để chạy được trên nhiều hệ CSDL). Công cụ ERD vì thế sẽ vẽ ra 26 hộp rời rạc.

Cách khắc phục: dùng **DBeaver** (tải ở dbeaver.io) và khai báo *virtual foreign key* — chỉ lưu trong metadata của DBeaver, không đụng gì tới CSDL:

1. Mở bảng → tab **Foreign Keys** → chuột phải → **Create New Virtual Foreign Key**
2. Khai các quan hệ chính:

| Bảng | Cột | → Bảng đích |
|---|---|---|
| `mdl_course` | `category` | `mdl_course_categories.id` |
| `mdl_enrol` | `courseid` | `mdl_course.id` |
| `mdl_user_enrolments` | `enrolid` / `userid` | `mdl_enrol.id` / `mdl_user.id` |
| `mdl_assign` | `course` | `mdl_course.id` |
| `mdl_assign_submission` | `assignment` / `userid` | `mdl_assign.id` / `mdl_user.id` |
| `mdl_attendance` | `course` | `mdl_course.id` |
| `mdl_attendance_sessions` | `attendanceid` | `mdl_attendance.id` |
| `mdl_attendance_log` | `sessionid` / `studentid` | `mdl_attendance_sessions.id` / `mdl_user.id` |
| `mdl_course_modules` | `course` / `module` / `section` | `mdl_course.id` / `mdl_modules.id` / `mdl_course_sections.id` |
| `mdl_logstore_standard_log` | `userid` / `courseid` | `mdl_user.id` / `mdl_course.id` |

3. Click đôi **Tables** → tab **ER Diagram** → sơ đồ hiện đầy đủ

> ℹ️ **Không công cụ nào vẽ được quan hệ giữa bảng Moodle và 3 bảng fact**, vì chúng nằm ở hai database khác nhau — PostgreSQL không cho tạo khóa ngoại xuyên database. Cầu nối duy nhất là mã ETL trong [etl/extract/sql/](etl/extract/sql/).

### 8.5 Vài câu SQL hữu ích

```sql
-- Dung lượng và số dòng từng bảng
SELECT relname AS bang, n_live_tup AS so_dong,
       pg_size_pretty(pg_total_relation_size(relid)) AS dung_luong
FROM pg_stat_user_tables WHERE schemaname = 'analytics'
ORDER BY n_live_tup DESC;

-- Phân bố đèn giao thông ngày mới nhất
SELECT risk_level, COUNT(*) FROM analytics.fact_student_risk_summary
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM analytics.fact_student_risk_summary)
GROUP BY risk_level;

-- Top 10 sinh viên nguy cơ cao nhất của một môn
SELECT student_code, student_name, risk_score, absence_rate,
       missing_assignments_count, risk_reasons
FROM analytics.fact_student_risk_summary
WHERE course_id = 6 AND snapshot_date = '2026-11-06' AND risk_level = 'RED'
ORDER BY risk_score DESC LIMIT 10;

-- Lịch sử chạy ETL gần đây
SELECT run_id, job_name, status, started_at, finished_at
FROM analytics.etl_run_log ORDER BY run_id DESC LIMIT 10;
```

### 8.6 Kiểm tra trạng thái migration

Không cần mở CSDL vẫn xem được cấu trúc đã dựng tới đâu:

```powershell
python -m database.migrate status --target analytics
python -m database.migrate status --target moodle
```

### 8.7 Grain của 3 bảng fact

| Bảng | PRIMARY KEY | Một dòng là gì |
|---|---|---|
| `fact_student_risk_summary` | `(course_id, user_id, snapshot_date)` | 1 sinh viên, trong 1 môn, tại 1 ngày chụp |
| `fact_course_progress_daily` | `(course_id, stat_date)` | 1 môn học, trong 1 ngày |
| `fact_server_traffic_hourly` | `(stat_hour)` | 1 giờ đồng hồ |

---

## 9. Cấu trúc dự án — tác dụng từng file

```
Do_an_chuyen_nganh/
├── common/       Tiện ích dùng chung mọi tầng
├── database/   ① Migration CSDL
├── mockdata/   ② Sinh dữ liệu giả lập
├── etl/        ③ Extract → Transform → Load
├── backend/    ④ REST API
├── frontend/   ⑤ Giao diện web
├── tests/        Kiểm thử pytest
├── perf/         Đo hiệu năng
├── scripts/      Lệnh tắt Windows
├── docker/       Dockerfile, nginx, bootstrap
├── docs/         Tài liệu nộp kèm
└── SPEC/         Kế hoạch và báo cáo tiến độ
```

### 9.1 Thư mục gốc

| File | Tác dụng |
|---|---|
| `.env.example` | Mẫu cấu hình có chú thích, sao chép thành `.env` rồi điền |
| `.gitignore` | Loại `.env`, `node_modules`, `dist`, `__pycache__` khỏi Git |
| `.dockerignore` | Loại các thư mục không cần khỏi build context Docker |
| `README.md` | Chính là file bạn đang đọc |
| `requirements.txt` | Thư viện Python, chia nhóm theo từng bước của dự án |
| `docker-compose.yml` | Định nghĩa 5 dịch vụ Docker |
| `Makefile` | Lệnh tắt cho Linux/macOS |
| `pytest.ini` | Cấu hình pytest |

### 9.2 `common/` — Tiện ích dùng chung

| File | Tác dụng |
|---|---|
| `settings.py` | **Quản lý thời gian toàn hệ thống.** Định nghĩa `AS_OF` thay cho `now()`, nhờ đó mock data, ETL, API và giao diện đều nhìn cùng một mốc thời gian |

### 9.3 `database/` — ① Tầng cơ sở dữ liệu

| File | Tác dụng |
|---|---|
| `config.py` | Đọc `.env`, trả về cấu hình kết nối. Thiếu biến nào báo lỗi rõ tên biến đó. Dùng chung bởi ETL và Backend |
| `migrate.py` | Trình chạy migration tự viết: quét `V***__*.sql`, áp dụng tăng dần, ghi checksum vào `schema_migrations` |

**`migrations/analytics/` — dựng kho phân tích**

| File | Tác dụng |
|---|---|
| `V001__schema_domains_support_tables.sql` | Tạo schema `analytics`, bảng `app_user`, `etl_run_log`, `etl_watermark` |
| `V002__fact_student_risk_summary.sql` | **BẢNG FACT 1** — cảnh báo sinh viên, 38 cột |
| `V003__fact_course_progress_daily.sql` | **BẢNG FACT 2** — tiến độ môn theo ngày |
| `V004__fact_server_traffic_hourly.sql` | **BẢNG FACT 3** — lưu lượng theo giờ |
| `V005__intervention_log_and_views.sql` | Bảng nhật ký can thiệp + view `v_student_risk_latest` |
| `V006__online_snapshot_attendance_status_rule.sql` | Bảng mẫu người online 5 phút + ràng buộc trạng thái điểm danh |
| `V007__nullable_rates_without_data.sql` | Sửa lỗi nghiệp vụ: mẫu số bằng 0 thì lưu `NULL` ("chưa có dữ liệu") thay vì `0` |

**`migrations/moodle/` — dựng CSDL nguồn**

| File | Tác dụng |
|---|---|
| `V001__core_course_user_enrol.sql` | Bảng lõi: danh mục, khóa học, người dùng, ghi danh, vai trò, nhóm |
| `V002__logstore_sessions_lastaccess.sql` | Nhật ký sự kiện, phiên đăng nhập, lần truy cập gần nhất |
| `V003__course_modules_assign_completion.sql` | Cấu trúc nội dung môn, bài tập, theo dõi hoàn thành |
| `V004__mod_attendance.sql` | Plugin điểm danh `mod_attendance` |

> Cấu trúc các bảng này sao chép nguyên văn từ **Moodle 3.9 thật**. Khi có Moodle thật, chỉ cần đổi thông tin kết nối trong `.env` là ETL chạy được, không phải sửa mã.

### 9.4 `mockdata/` — ② Sinh dữ liệu giả lập

| File | Tác dụng |
|---|---|
| `config.py` | Tham số sinh dữ liệu: `RANDOM_SEED = 2026`, 15 môn, 500 SV, các hồ sơ hành vi (chăm / trung bình / lười), trọng số theo giờ và thứ |
| `db.py` | Kết nối `moodle_src`, dùng `COPY` ghi hàng loạt |
| `names.py` | Sinh họ tên tiếng Việt có tính tái lập |
| `seed_structure.py` | Dựng bộ khung: vai trò, cây Khoa→Bộ môn→Môn, 8 giảng viên, 500 SV, ghi danh, bài tập, buổi điểm danh |
| `generate_activity.py` | Sinh hành vi học tập: 1,2 triệu dòng log, 7.272 bài nộp, 36.933 lượt điểm danh |
| `cleanup.py` | Xóa dữ liệu giả lập (`--activity` hoặc `--all`) |

### 9.5 `etl/` — ③ Tầng ETL

**File gốc**

| File | Tác dụng |
|---|---|
| `config.py` | Mọi ngưỡng nghiệp vụ tập trung ở đây: timezone, quy tắc học kỳ, ngưỡng rủi ro, lịch job |
| `db.py` | Hai engine SQLAlchemy. Engine Moodle **chỉ đọc** — read-only + `statement_timeout`, nên ETL không thể làm hỏng Moodle |
| `sqlfile.py` | Nạp file SQL tĩnh; cú pháp `{{ten}}` chèn đoạn SQL dùng chung từ `_ten.sql` |
| `scheduler.py` | Lập lịch bằng APScheduler, chạy như tiến trình nền |

**`extract/` — Bước E**

| File | Tác dụng |
|---|---|
| `course_data.py` | Trích bộ dữ liệu các môn đang diễn ra, chạy trong một transaction REPEATABLE READ |
| `sql/_student_enrol.sql` | CTE dùng chung: SV ghi danh hợp lệ. Viết dạng semi-join `EXISTS` để tránh timeout |
| `sql/courses.sql` | Môn đang diễn ra + tên khoa, bộ môn, danh sách giảng viên |
| `sql/enrolments.sql` | SV ghi danh + MSSV, họ tên, email |
| `sql/attendance.sql` | **Tiêu chí 1 — Điểm danh.** Không có bản ghi = coi như vắng |
| `sql/interaction.sql` | **Tiêu chí 2 — Tương tác.** Lần truy cập cuối lấy từ logstore để đúng theo `AS_OF` |
| `sql/assignments.sql` | **Tiêu chí 3 — Bài tập.** Xử lý cả bài nộp nhóm |
| `sql/completion.sql` | Hoàn thành hoạt động theo chương, chỉ tính hoạt động bắt buộc đã đến hạn |
| `sql/weekly_activity.sql` | Hoạt động theo tuần học, cho biểu đồ đường 15 tuần |
| `sql/submissions_day.sql` | Số bài nộp trong ngày theo môn |
| `sql/traffic_hourly.sql` | Lưu lượng theo giờ, tính lại toàn bộ để `COUNT(DISTINCT)` luôn đúng |
| `sql/online_sessions.sql` | Người online tại `AS_OF` từ `mdl_sessions` |
| `sql/online_logstore.sql` | Suy ra người online từ log theo khung 5 phút |
| `sql/max_log_id.sql` | `id` lớn nhất của logstore, dùng khóa chính nên rất nhanh |
| `sql/new_log_range.sql` | Khoảng thời gian của log mới trong khoảng watermark |

**`transform/` — Bước T** (thuần Python/pandas, không truy cập CSDL nên dễ test)

| File | Tác dụng |
|---|---|
| `risk_rules.py` | ⭐ **Luật chấm điểm đèn giao thông** — nghiệp vụ cốt lõi của đề tài |
| `student_risk.py` | Gộp chỉ số từng cặp (môn, SV), gọi `risk_rules` → dòng fact |
| `course_progress.py` | Gộp số liệu cả lớp → dòng fact |
| `traffic.py` | Gộp lưu lượng theo giờ, bổ sung 0 cho giờ không có sự kiện |
| `semester.py` | Suy ra năm học / học kỳ từ `startdate` của môn |

**`load/` — Bước L**

| File | Tác dụng |
|---|---|
| `upsert.py` | Nạp hàng loạt: `CREATE TEMP TABLE` → `COPY` → `INSERT ... ON CONFLICT DO UPDATE` |
| `sql/delete_stale_risk.sql` | Xóa SV không còn trong lần tính mới |
| `sql/mark_peak_hours.sql` | Đánh dấu giờ cao điểm khi requests > P90 của 28 ngày |
| `sql/merge_online_snapshot.sql` | Gộp mẫu online; mẫu chụp thật luôn ghi đè mẫu suy ra |
| `sql/aggregate_online.sql` | Tính lại peak/avg người online |
| `sql/risk_level_counts.sql` | Đếm phân bố đèn giao thông mỗi môn |
| `sql/prune_risk_snapshots.sql` | Snapshot cũ hơn 180 ngày chỉ giữ bản cuối mỗi tuần |

**`jobs/` — Các job định kỳ**

| File | Tác dụng |
|---|---|
| `runner.py` | Khung chạy chung: khóa chống chạy trùng → ghi log RUNNING → E/T/L → ghi SUCCESS/FAILED |
| `job_traffic.py` | Job mỗi 5 phút |
| `job_course_progress.py` | Job mỗi giờ |
| `job_student_risk.py` | Job mỗi 2 giờ (07h–21h) |
| `nightly.py` | Job 01:00 — chốt số liệu ngày hôm qua |
| `maintenance.py` | Job Chủ nhật 03:00 — dọn dẹp, tối ưu |
| `backfill.py` | Chạy thủ công — nạp lịch sử lần đầu |

### 9.6 `backend/` — ④ Tầng API

**Gốc và hạ tầng**

| File | Tác dụng |
|---|---|
| `app/main.py` | Điểm khởi động: tạo FastAPI app, gắn CORS, security header, đăng ký 5 router với tiền tố `/api/v1` |
| `app/cli.py` | Quản lý tài khoản: `sync-users`, `set-password`, `list-users` |
| `app/core/config.py` | Đọc biến `BACKEND_*` từ `.env` + `AS_OF` |
| `app/core/db.py` | Connection pool (`pool_size=10`), dependency `get_conn` |
| `app/core/security.py` | ⭐ Băm bcrypt, ký/kiểm JWT HS256 (hạn 8 giờ), `require_role`, giới hạn đăng nhập sai |
| `app/core/cache.py` | Cache TTL 60 giây cho endpoint KPI |

**`routers/` — Nhận HTTP request**

| File | Tác dụng |
|---|---|
| `auth.py` | `POST /auth/login`, `GET /auth/me` |
| `common.py` | `/filters`, `/etl/status`, `/health` |
| `admin.py` | Tổng quan, drill-down Khoa→Môn→SV, lưu lượng. **Chỉ vai trò ADMIN** |
| `reports.py` | Data Preview + xuất Excel/PDF |
| `teacher.py` | Cảnh báo, modal, can thiệp, tiến độ. Kiểm tra GV thuộc `teacher_ids` của môn |
| `deps.py` | Dependency dùng chung: vai trò, học kỳ, thời điểm tham chiếu |
| `_export.py` | Tạo HTTP response tải file |

**`repositories/` — Truy vấn CSDL (SQL thuần)**

| File | Tác dụng |
|---|---|
| `admin.py` | Cây Khoa→Môn→SV và thẻ KPI |
| `teacher.py` | Cảnh báo và tiến độ, luôn kèm điều kiện phân quyền |
| `traffic.py` | Lưu lượng và người online |
| `reports.py` | Định nghĩa các loại báo cáo |
| `common.py` | Thời điểm cập nhật, bộ lọc, trạng thái ETL |
| `users.py` | Đọc/ghi bảng `app_user` |
| `_sql.py` | ⭐ Chống SQL injection: chỉ ghép đoạn SQL **tĩnh** từ danh sách cho phép; mọi giá trị người dùng đi qua tham số bind |

**`schemas/` — Kiểu dữ liệu Pydantic** (tự sinh tài liệu Swagger)

| File | Tác dụng |
|---|---|
| `auth.py` | `LoginIn`, `TokenOut`, `UserOut` |
| `admin.py` / `teacher.py` / `reports.py` | Schema các endpoint tương ứng |
| `common.py` | Phân trang, dấu thời gian, bộ lọc |

**`services/` — Nghiệp vụ không đụng CSDL**

| File | Tác dụng |
|---|---|
| `export_excel.py` | Xuất Excel bằng openpyxl chế độ write-only, ít bộ nhớ |
| `export_pdf.py` | Xuất PDF bằng ReportLab, A4 ngang, lặp tiêu đề mỗi trang |
| `formatting.py` | Định dạng số/ngày kiểu vi-VN |

### 9.7 `frontend/` — ⑤ Tầng giao diện

**Gốc**

| File | Tác dụng |
|---|---|
| `package.json` | Khai báo thư viện và script `dev` / `build` / `test` / `e2e` |
| `vite.config.js` | Cấu hình Vite + **proxy `/api` → `http://127.0.0.1:8000`** |
| `index.html` | HTML gốc, chứa `<div id="root">` |
| `playwright.config.js` | Cấu hình E2E chạy trên Chrome đã cài sẵn |

**`src/` — Mã nguồn**

| File | Tác dụng |
|---|---|
| `main.jsx` | Điểm khởi động React, gắn theme đạt tương phản WCAG AA |
| `App.jsx` | Bọc Provider (React Query, Ant Design tiếng Việt), định tuyến theo vai trò |
| `styles.css` | CSS toàn cục |
| `api/client.js` | axios + gắn JWT. **401 ở bất kỳ request nào → tự đăng xuất** |
| `api/hooks.js` | React Query hook cho từng endpoint, tự làm mới 60 giây |
| `auth/AuthContext.jsx` | Đăng nhập/đăng xuất, tự hết phiên theo hạn token |
| `routes/ProtectedRoute.jsx` | Chặn trang theo vai trò ở phía giao diện |
| `theme/tokens.js` | Màu đèn giao thông và màu chuỗi dữ liệu; màu **luôn đi kèm ký hiệu** |
| `utils/format.js` | Định dạng vi-VN; tỷ lệ `null` → "Chưa có dữ liệu", khác hẳn 0% |

**`src/charts/` — Biểu đồ**

| File | Tác dụng |
|---|---|
| `setup.js` | Đăng ký Chart.js một lần + thiết lập mặc định (lưới mảnh, chữ màu mực, đường 2px) |
| `TrafficDualAxisChart.jsx` | Biểu đồ 2 trục; hai đường **khác kiểu nét** để không đọc nhầm thang |
| `EnrollmentStackedBar.jsx` | Cột chồng theo khoa, nhấn để drill-down |
| `TrafficHeatmap.jsx` | Heatmap giờ × thứ, thang tuần tự một màu |
| `RiskDoughnut.jsx` | Biểu đồ vành khuyên, nhấn lát cắt để lọc |
| `StudentCharts.jsx` | Biểu đồ trong modal: so sánh SV vs lớp, hoạt động theo tuần |

**`src/components/`, `layouts/`, `pages/`**

| File | Tác dụng |
|---|---|
| `components/AppHeader.jsx` | Thanh tiêu đề chung |
| `components/TermFilterBar.jsx` | Bộ lọc Năm học / Học kỳ / Khoa |
| `components/HierarchyTable.jsx` | Bảng phân cấp drill-down có breadcrumb |
| `components/StudentDetailModal.jsx` | Cửa sổ chi tiết SV + 4 nút can thiệp |
| `components/common.jsx` | `RiskBadge`, `KpiCard`, `ChartCard` (có nút "Biểu đồ \| Bảng") |
| `layouts/AdminLayout.jsx` | Khung trang Admin |
| `layouts/TeacherLayout.jsx` | Khung trang Giảng viên, có ô chọn môn |
| `pages/LoginPage.jsx` | Trang đăng nhập |
| `pages/admin/AdminOverview.jsx` | Trang Tổng quan |
| `pages/admin/AdminTraffic.jsx` | Trang Lưu lượng |
| `pages/admin/AdminReports.jsx` | Trang Báo cáo |
| `pages/teacher/TeacherHome.jsx` | Tự mở môn đầu tiên |
| `pages/teacher/TeacherRisk.jsx` | Trang Cảnh báo |
| `pages/teacher/TeacherProgress.jsx` | Trang Tiến độ lớp |

**`e2e/` — Kiểm thử giao diện thật**

| File | Tác dụng |
|---|---|
| `tests/helpers.js` | Đăng nhập qua API để lấy token nhanh |
| `tests/admin.spec.js` | Luồng Admin: lọc → drill-down → Export Excel |
| `tests/teacher.spec.js` | Luồng GV: lọc ĐỎ → mở modal → gửi can thiệp |
| `tests/authz.spec.js` | Phân quyền: 403 khi xem môn người khác, 401 khi token hết hạn |
| `tests/a11y.spec.js` | Khả năng tiếp cận WCAG 2.1 A/AA bằng axe-core |
| `tests/responsive.spec.js` | Kiểm 4 độ rộng 1920 / 1366 / 768 / 390 px |
| `global-teardown.js` | Xóa can thiệp do E2E tạo (nội dung bắt đầu bằng `[e2e]`) |

### 9.8 `tests/` — Kiểm thử pytest

| File | Tác dụng |
|---|---|
| `backend/conftest.py` | Fixture: tài khoản test, client HTTP, kết nối CSDL |
| `backend/test_auth_api.py` | Xác thực, 401/403, giới hạn đăng nhập sai |
| `backend/test_admin_api.py` | API Admin — đối chiếu với truy vấn trực tiếp bảng fact |
| `backend/test_teacher_api.py` | API Giảng viên — phân quyền theo môn, modal, can thiệp |
| `backend/test_reports_api.py` | Data Preview và xuất Excel/PDF |
| `backend/test_security_api.py` | CORS, chống SQL injection, bcrypt, security header |
| `backend/test_security_unit.py` | Unit test không cần CSDL |
| `etl/test_risk_rules.py` | ⭐ Luật rủi ro, ≥20 ca biên, yêu cầu 100% pass |
| `etl/test_semester.py` | Quy tắc suy ra năm học / học kỳ |
| `etl/test_transforms.py` | Transform trên bộ dữ liệu nhỏ dựng tay |
| `database/test_analytics_schema.py` | Schema thật; mỗi test chạy trong transaction rồi rollback |
| `database/test_migrate_runner.py` | Unit test cho `migrate.py` |
| `integration/test_etl_pipeline.py` | Đối soát với Moodle, tính nhất quán, idempotency |
| `mockdata/test_mock_integrity.py` | Tính toàn vẹn dữ liệu giả lập |

### 9.9 `perf/`, `scripts/`, `docker/`, `docs/`, `SPEC/`

| File | Tác dụng |
|---|---|
| `perf/build_x10.py` | Dựng CSDL `lms_analytics_x10` — nhân 10 lần dữ liệu để đo |
| `perf/explain_queries.py` | `EXPLAIN (ANALYZE, BUFFERS)` các truy vấn chính |
| `perf/locustfile.py` | Test tải: 50 người đồng thời (40 GV, 10 Admin) |
| `perf/etl_bench.py` | Đo thời gian ETL trên ~2.000 SV |
| `perf/export_bench.py` | Đo xuất Excel 10.000 dòng, PDF 500 dòng |
| `perf/results/` | Kết quả đã đo, dùng làm minh chứng trong báo cáo |
| `scripts/lms.ps1` | ⭐ Lệnh tắt Windows cho mọi thao tác |
| `scripts/e2e_cleanup.py` | Dọn dữ liệu rác do E2E tạo |
| `docker/python.Dockerfile` | Image Python dùng chung cho `init`, `etl`, `backend` |
| `docker/frontend.Dockerfile` | Image build React |
| `docker/bootstrap.sh` | Script chạy một lần trong container `init` |
| `docker/nginx.conf` | Nginx phục vụ bản build + proxy `/api` |
| `docs/TAI_LIEU_HE_THONG.md` | **Tài liệu tổng hợp nộp kèm đồ án** |
| `docs/KET_QUA_KIEM_THU.md` | Kết quả kiểm thử và đo hiệu năng |
| `docs/images/` | Ảnh màn hình dùng trong tài liệu |
| `SPEC/KE_HOACH_TRIEN_KHAI.md` | Bản kế hoạch gốc — mọi file mã nguồn đều trích dẫn số mục của nó |
| `SPEC/BAO_CAO_TIEN_DO.md` | Tiến độ và các thay đổi so với kế hoạch, kèm lý do |

---

## 10. Kiểm thử

| Loại | Lệnh | Tiền điều kiện |
|---|---|---|
| CSDL, ETL, mock, tích hợp, API | `python -m pytest -q` | Đã chạy `etl-backfill` |
| Frontend (đơn vị) | `cd frontend; npm test` | — |
| E2E, phân quyền, responsive, WCAG | `cd frontend; npx playwright test` | API + web đang chạy, đặt `LMS_DEMO_PASSWORD` |
| Hiệu năng | `.\scripts\lms.ps1 bench` | Xem thêm [perf/README.md](perf/README.md) |

Kết quả đã đo được ghi ở [docs/KET_QUA_KIEM_THU.md](docs/KET_QUA_KIEM_THU.md). Tóm tắt: **p99 của mọi endpoint đọc dữ liệu đều dưới 40 ms**.

---

## 11. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Thiếu biến môi trường: ANALYTICS_DB_...` | Chưa tạo `.env` | `Copy-Item .env.example .env` rồi điền (mục 3.2) |
| `password authentication failed` | Sai mật khẩu, hoặc gõ cả dấu nháy | Mật khẩu **không bao gồm** dấu nháy trong file `.env` |
| `psql: command not found` | psql chưa có trong PATH | Dùng đường dẫn đầy đủ (mục 8.2) |
| Đăng nhập báo sai mật khẩu | Chưa chạy `lms.ps1 users` | Chạy lại bước 5 của mục 3.3 |
| Trang trắng, không có dữ liệu | Chưa chạy `etl-backfill` | Chạy lại bước 4 của mục 3.3 |
| Số liệu khác tài liệu | `LMS_AS_OF` sai | Đặt đúng `2026-11-06T10:30:00+07:00` rồi chạy lại từ `seed` |
| Đổi mật khẩu xong vẫn không vào được | Đổi nhầm CSDL | Bản local (cổng 5173) và Docker (cổng 8080) dùng **hai CSDL riêng** |
| `npm run dev` báo thiếu module | Chưa `npm install` | `cd frontend; npm install` |
| Biểu đồ trống nhưng bảng có số | Trình duyệt chặn canvas | Thử trình duyệt khác, hoặc bấm nút "Bảng" |

---

## 12. Tài liệu chi tiết hơn

| Muốn biết | Đọc |
|---|---|
| Kiến trúc, thiết kế CSDL, minh chứng trực quan hóa | [docs/TAI_LIEU_HE_THONG.md](docs/TAI_LIEU_HE_THONG.md) |
| Kết quả kiểm thử và đo hiệu năng | [docs/KET_QUA_KIEM_THU.md](docs/KET_QUA_KIEM_THU.md) |
| Kế hoạch gốc của đồ án | [SPEC/KE_HOACH_TRIEN_KHAI.md](SPEC/KE_HOACH_TRIEN_KHAI.md) |
| Tiến độ và thay đổi so với kế hoạch | [SPEC/BAO_CAO_TIEN_DO.md](SPEC/BAO_CAO_TIEN_DO.md) |
| Chi tiết tầng ETL | [etl/README.md](etl/README.md) |
| Danh sách endpoint API | [backend/README.md](backend/README.md) hoặc chạy backend rồi mở `http://localhost:8000/api/docs` |
| Chi tiết tầng giao diện | [frontend/README.md](frontend/README.md) |
| Cách sinh dữ liệu giả lập | [mockdata/README.md](mockdata/README.md) |
| Cách đo hiệu năng | [perf/README.md](perf/README.md) |

---

## Giấy phép và ghi chú

Đồ án học tập, không dùng cho mục đích thương mại.

Dữ liệu trong hệ thống là **dữ liệu giả lập** sinh bằng `mockdata/`, không phải dữ liệu sinh viên thật. Họ tên, MSSV, email đều do chương trình sinh ngẫu nhiên với seed cố định.
