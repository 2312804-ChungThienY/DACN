# ETL Layer – `moodle_src` → `lms_analytics`

Tài liệu thiết kế: [SPEC/KE_HOACH_TRIEN_KHAI.md](../SPEC/KE_HOACH_TRIEN_KHAI.md), Phần 1, 2.3 và 4.

## Kiến trúc

```
etl/
├── config.py               ngưỡng rủi ro, quy tắc học kỳ, khóa job, timeout
├── db.py                   engine Moodle (read-only + statement_timeout) và engine Analytics
├── sqlfile.py              nạp file SQL tĩnh, hỗ trợ {{include}}
├── extract/
│   ├── sql/*.sql           truy vấn trích xuất SPEC Phần 1, tham số :as_of
│   └── course_data.py      đọc toàn bộ dữ liệu môn học trong 1 transaction REPEATABLE READ
├── transform/
│   ├── risk_rules.py       luật đèn giao thông (SPEC 2.3)
│   ├── student_risk.py     → fact_student_risk_summary
│   ├── course_progress.py  → fact_course_progress_daily
│   ├── traffic.py          → fact_server_traffic_hourly, etl_online_snapshot
│   └── semester.py         suy ra năm học/học kỳ
├── load/
│   ├── upsert.py           COPY → bảng tạm → INSERT ... ON CONFLICT (chỉ cập nhật khi giá trị đổi)
│   └── sql/*.sql           SQL phía analytics (gộp mẫu online, P90 giờ cao điểm, dọn snapshot...)
├── jobs/                   runner (advisory lock, etl_run_log, retry) + các job
└── scheduler.py            APScheduler
```

## Chạy

```powershell
# Lần đầu: nạp lịch sử từ đầu học kỳ tới LMS_AS_OF (~6 phút với 61 ngày)
python -m etl.jobs.backfill --from 2026-09-07

# Chạy từng job (đều nhận --as-of ISO 8601 để ghi đè LMS_AS_OF)
python -m etl.jobs.job_traffic
python -m etl.jobs.job_student_risk
python -m etl.jobs.job_course_progress
python -m etl.jobs.nightly
python -m etl.jobs.maintenance

# Chạy tự động theo lịch
python -m etl.scheduler
```

Mã thoát: `0` thành công, `3` bị bỏ qua vì job khác đang giữ khóa, `1` lỗi (chi tiết ghi trong `analytics.etl_run_log`).

## Lịch (SPEC 4.2)

| Job | Lịch | Việc |
|---|---|---|
| `traffic` | mỗi 5 phút | Tính lại các giờ có log mới (theo watermark) cùng giờ hiện tại và giờ trước; chụp `mdl_sessions` |
| `course_progress` | phút 05 mỗi giờ | Tiến độ trong ngày của các môn đang diễn ra |
| `student_risk` | 07:15–21:15, 2 giờ/lần | Snapshot rủi ro hôm nay (ghi đè) |
| `nightly` | 01:00 | Chốt số liệu hôm qua lúc 23:59:59, tính lại 24 giờ lưu lượng, đánh dấu P90 giờ cao điểm |
| `maintenance` | Chủ nhật 03:00 | Snapshot cũ hơn 180 ngày chỉ giữ bản cuối tuần; VACUUM ANALYZE |

## Quyết định kỹ thuật cần biết

- **`AS_OF` thay cho `now()`.** Mọi truy vấn đều tính "tại thời điểm AS_OF", nên backfill dựng lại được đúng lịch sử từng ngày.
- **Lần truy cập cuối lấy từ logstore**, không lấy từ `mdl_user_lastaccess`. Lý do: `mdl_user_lastaccess` chỉ giữ giá trị hiện tại nên không dựng lại được quá khứ.
- **Tỷ lệ hoàn thành chỉ tính hoạt động đã tới hạn** (`completionexpected ≤ AS_OF`). Nếu tính cả các tuần chưa học, số liệu giữa kỳ sẽ bị kéo xuống.
- **Online users được lưu thành mẫu 5 phút** trong `etl_online_snapshot`, rồi mới tính peak/avg theo giờ. Có hai nguồn mẫu:
  - `SESSIONS`: chụp từ `mdl_sessions`, được ưu tiên.
  - `LOGSTORE`: số user có sự kiện trong 5 phút, dùng khi backfill hoặc bù khung bị lỡ.
- **Tránh nối trực tiếp bảng log với danh sách ghi danh.** Mọi truy vấn trên bảng log đều gom log trước rồi mới join. Danh sách ghi danh viết dạng semi-join `EXISTS`, vì dạng JOIN nhiều bảng khiến planner ước lượng 1 dòng, chọn Nested Loop và bị timeout.
- **Không sửa được dữ liệu Moodle.** Engine Moodle đặt `default_transaction_read_only=on` và `statement_timeout=60s`.

## Hiệu chỉnh luật rủi ro (SPEC 6.7 – "Ngưỡng rủi ro chưa hợp lý")

Đo trên ground truth mock tại 06/11/2026 (2.383 cặp SV–môn). Luật xếp mức gốc của SPEC 2.3 cho Precision(RED) = 62,9%, không đạt mục tiêu 80% của SPEC 6.1. Nguyên nhân: mới đến tuần 9, mỗi môn chỉ có 3–4 bài tới hạn, nên chỉ cần thiếu 2 bài là đã đỏ.

| Quy tắc RED | % RED | Recall | Precision |
|---|---|---|---|
| Spec gốc: bất kỳ tiêu chí = 2 hoặc tổng ≥ 3 | 23,8% | 100% | 62,9% |
| **Đang dùng:** C2 = 2 hoặc ≥ 2 tiêu chí = 2 hoặc tổng ≥ 4 | 17,1% | 97,8% | 85,3% |

Không đổi gì khác: ngưỡng từng tiêu chí, công thức `risk_score`, các cột dữ liệu và cách trực quan hóa vẫn giữ nguyên. Muốn quay về luật gốc, sửa `RISK_LEVEL_RULES` trong `config.py` thành `red_min_red_criteria=1, red_min_total=3`.

## Kiểm thử

```powershell
python -m pytest tests/etl -q          # unit: luật rủi ro (>= 20 ca biên), học kỳ, transform
python -m pytest tests/integration -q  # cần mock data + backfill: đối soát, idempotency, incremental, ground truth
```
