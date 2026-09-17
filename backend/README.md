# Backend API – FastAPI

Tài liệu thiết kế: [SPEC/KE_HOACH_TRIEN_KHAI.md](../SPEC/KE_HOACH_TRIEN_KHAI.md), Phần 5.1.

API chỉ đọc CSDL phân tích `lms_analytics` (3 bảng fact do ETL nạp), không truy vấn Moodle. Chỉ ghi vào 2 bảng: `intervention_log` (can thiệp của giảng viên) và `app_user` (tài khoản, qua CLI).

## Cấu trúc

```
backend/app/
├── main.py              create_app(): CORS, header X-Process-Time-Ms, gắn router vào /api/v1
├── cli.py               quản lý tài khoản: sync-users, set-password, list-users
├── core/
│   ├── config.py        biến BACKEND_* trong .env; "hôm nay" tính theo LMS_AS_OF
│   ├── db.py            engine SQLAlchemy (pool 10, statement_timeout 15s), get_conn
│   ├── security.py      bcrypt, JWT (PyJWT HS256), require_role, giới hạn đăng nhập sai
│   └── cache.py         cache TTL 60 giây (cachetools) cho endpoint KPI
├── repositories/        SQL thuần + tham số bind: common, users, admin, traffic, teacher, reports
├── schemas/             Pydantic cho request/response (Swagger)
├── services/            formatting, export_excel (openpyxl), export_pdf (ReportLab)
└── routers/             auth, common, admin, reports, teacher (+ deps, _export)
```

## Chạy

```powershell
python -m pip install -r requirements.txt
# .env: BACKEND_JWT_SECRET (>= 32 ký tự) – xem .env.example

# Tạo tài khoản: admin + mọi giảng viên có vai trò trong Moodle (user_id = mdl_user.id)
$env:BACKEND_SEED_PASSWORD = "<mật khẩu ban đầu>"
python -m backend.app.cli sync-users
python -m backend.app.cli set-password --username gv.tranminhhung      # đổi mật khẩu (hỏi từ bàn phím)

python -m uvicorn backend.app.main:app --reload --port 8000
# Swagger UI: http://localhost:8000/api/docs

# Chạy như khi triển khai (nhiều worker, giữ kết nối lâu hơn – xem ghi chú bên dưới)
python -m uvicorn backend.app.main:app --port 8000 --workers 2 --timeout-keep-alive 65
```

Kiểm thử (cần dữ liệu ETL tại `LMS_AS_OF`):

```powershell
python -m pytest tests/backend -q
```

## Endpoint (tiền tố `/api/v1`)

| Nhóm | Method & URL | Vai trò |
|---|---|---|
| Xác thực | `POST /auth/login`, `GET /auth/me` | – / mọi vai trò |
| Dùng chung | `GET /filters`, `GET /etl/status`, `GET /health` (không cần đăng nhập) | mọi vai trò |
| Admin 1.1 | `GET /admin/overview/kpis`, `/admin/enrollment/by-faculty`, `/admin/enrollment/faculties/{id}/courses`, `/admin/enrollment/courses/{id}/students` | ADMIN |
| Admin 1.2 | `GET /admin/traffic/hourly`, `/admin/traffic/realtime`, `/admin/traffic/heatmap` | ADMIN |
| Admin 1.3 | `GET /admin/reports/preview`, `/admin/reports/export?format=xlsx\|pdf` | ADMIN |
| GV 2.1 | `GET /teacher/courses`, `/teacher/courses/{id}/risk-summary`, `/students`, `/students/{uid}`, `POST /students/{uid}/interventions`, `GET /export` | TEACHER |
| GV 2.2 | `GET /teacher/courses/{id}/progress?granularity=day\|week`, `/students/{uid}/compare` | TEACHER |

Quy ước: lỗi trả `{"detail": "..."}`. Danh sách phân trang trả `items, total, page, page_size`. Mọi response JSON có `data_updated_at`; file xuất có header `X-Data-Updated-At`.

## Quyết định kỹ thuật cần biết

- **"Hôm nay" = `LMS_AS_OF`.** KPI trong ngày, giờ hiện tại, snapshot mới nhất đều tính tại AS_OF, khớp với mock data và ETL. Để trống thì dùng thời gian thực.
- **Phân quyền 2 lớp.**
  - Tầng API: môn không có dữ liệu trả 404; môn không thuộc giảng viên trả 403.
  - Tầng SQL: mọi truy vấn trên bảng fact đều có `teacher_ids @> ARRAY[:teacher_id]`. Dùng `@>` thay cho `= ANY()` vì chỉ `@>` dùng được GIN index.
- **Vai trò đọc từ CSDL ở mỗi request**, không tin trường `role` trong token. Tài khoản bị khóa hoặc đổi vai trò mất quyền ngay.
- **Bảng cảnh báo dùng snapshot mới nhất của môn**, không dùng view `v_student_risk_latest`. View đó lấy bản mới nhất theo từng SV nên vẫn giữ những SV đã hết hạn hoặc hủy ghi danh (snapshot cũ), làm lệch tổng số với số SV đang học.
- **Số liệu một học kỳ = dòng mới nhất của từng môn**, nên môn kết thúc sớm vẫn được tính.
- **"SV có tương tác" ở cấp drill-down SV** = có log từ ngày bắt đầu môn (một tuần trong `weekly_activity` có `views + actions > 0`). Cách này khớp chính xác `total_active_students`; `total_access_count > 0` thì không khớp vì có log trước ngày bắt đầu môn.
- **Heatmap** lấy trung bình N tuần trọn ngày gần nhất, không tính hôm nay đang dở dang.
- **Tiến độ theo tuần:** tỷ lệ và "SV hoạt động 7 ngày" lấy tại ngày cuối tuần; lượt xem, thao tác và bài nộp cộng dồn trong tuần.
- **Đăng nhập sai quá 5 lần trong 5 phút** theo (IP, username) thì trả 429. Bộ đếm nằm trong bộ nhớ của một tiến trình; khi chạy nhiều worker cần chuyển sang Redis.
- **Giới hạn xuất file:** PDF tối đa 5.000 dòng, Excel tối đa 200.000 dòng (cấu hình được). Vượt giới hạn trả 422 kèm gợi ý.
- **Chạy uvicorn với `--timeout-keep-alive 65`.** Mặc định của uvicorn là 5 giây; khi người dùng có khoảng nghỉ vài giây giữa hai thao tác (đúng hành vi của Dashboard), client hay gửi request đúng lúc server đóng kết nối nhàn rỗi, khiến request đó phải chờ TCP hết giờ. Đo bằng Locust: giữ mặc định thì có vài request lẻ mất 30–69 giây (CSDL không hề có truy vấn nào quá 1 giây); đặt 65 giây thì chậm nhất còn 0,55 giây.
