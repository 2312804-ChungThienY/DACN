# Database Layer – CSDL phân tích `lms_analytics`

Tài liệu thiết kế: [SPEC/KE_HOACH_TRIEN_KHAI.md](../SPEC/KE_HOACH_TRIEN_KHAI.md), Phần 2.

## Thành phần

| File | Nội dung |
|---|---|
| `config.py` | Đọc thông tin kết nối từ `.env` (tiền tố `ANALYTICS_DB_*`, `MOODLE_DB_*`) |
| `migrate.py` | Runner migration: tự tạo database, áp dụng file SQL theo phiên bản, kiểm tra checksum |
| `migrations/analytics/V001__schema_domains_support_tables.sql` | Schema `analytics`, các domain dùng chung, `etl_run_log`, `etl_watermark`, `app_user` |
| `migrations/analytics/V002__fact_student_risk_summary.sql` | Bảng FACT 1: cảnh báo sinh viên nguy cơ |
| `migrations/analytics/V003__fact_course_progress_daily.sql` | Bảng FACT 2: tiến độ môn học theo ngày |
| `migrations/analytics/V004__fact_server_traffic_hourly.sql` | Bảng FACT 3: lưu lượng truy cập theo giờ |
| `migrations/analytics/V005__intervention_log_and_views.sql` | `intervention_log` và view `v_student_risk_latest` |
| `migrations/analytics/V006__online_snapshot_attendance_status_rule.sql` | `etl_online_snapshot` (mẫu online 5 phút), ràng buộc `attendance_status` khớp điểm C1 |
| `migrations/analytics/V007__nullable_rates_without_data.sql` | Tỷ lệ chưa có dữ liệu (0 buổi điểm danh, 0 bài tới hạn, 0 hoạt động tới hạn) lưu `NULL` thay vì 0. Sau khi áp dụng phải chạy lại ETL backfill |

## Chạy

```powershell
# 1. Cấu hình: sao chép .env.example thành .env rồi điền ANALYTICS_DB_PASSWORD
Copy-Item .env.example .env

# 2. Cài thư viện
python -m pip install -r requirements.txt

# 3. Xem trạng thái và áp dụng migration
python -m database.migrate status --target analytics
python -m database.migrate up     --target analytics

# 4. Kiểm thử schema
python -m pytest tests/database -v
```

## Quy tắc khi thay đổi schema

- **Không sửa** file migration đã áp dụng. Runner phát hiện qua checksum và dừng lại.
- Tạo file mới với số phiên bản kế tiếp, ví dụ `V006__add_column_x.sql`.
- Không viết `BEGIN`/`COMMIT` trong file: runner đã bọc mỗi file trong một transaction.
