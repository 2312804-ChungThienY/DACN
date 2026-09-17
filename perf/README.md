# Kiểm thử hiệu năng (SPEC 6.2)

Mọi script dùng **CSDL riêng**, không đụng dữ liệu demo (`lms_analytics`, `moodle_src`). Kết quả JSON ghi vào `perf/results/`.

| Hạng mục | Dữ liệu | Lệnh |
|---|---|---|
| Dựng dữ liệu x10 cho SQL/API | `lms_analytics_x10`: nhân 10 lần bảng fact (150 môn, ~1,46 triệu dòng rủi ro) | `python -m perf.build_x10` |
| Truy vấn SQL: `EXPLAIN (ANALYZE, BUFFERS)` | Các câu SQL mà API thật sự gửi xuống CSDL | `python -m perf.explain_queries --dataset x1` và `--dataset x10` |
| API: Locust 50 người dùng (40 GV, 10 Admin), think-time 2–5 giây | x1 hoặc x10 (chạy API với `ANALYTICS_DB_NAME=lms_analytics_x10`) | xem bên dưới |
| ETL | `moodle_src_x4` (2.000 SV, ~10.000 lượt ghi danh) → `lms_analytics_etlbench` | `python -m perf.etl_bench prepare` rồi `python -m perf.etl_bench measure` |
| Tải trang (cache lạnh) | Bản build production | `cd frontend; npm run build; npm run preview` rồi `npm run perf` |

## Locust

```powershell
# Cửa sổ 1 – API trên bộ x10 (2 worker)
$env:ANALYTICS_DB_NAME = "lms_analytics_x10"
python -m uvicorn backend.app.main:app --port 8000 --workers 2

# Cửa sổ 2 – 50 người dùng trong 10 phút
$env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
$env:LOCUST_TEACHERS = "gv.tranminhhung,gv.nguyenthilan,...,gv.hohaiyen.9"   # 80 GV của bộ x10
python -m locust -f perf/locustfile.py --host http://127.0.0.1:8000 --headless -u 50 -r 5 -t 10m `
    --csv perf/results/locust_x10 --html perf/results/locust_x10.html
```

Hoặc chạy cả hai lượt bằng một lệnh (tự bật/tắt API cho từng bộ dữ liệu):

```powershell
$env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
.\perf\run_locust.ps1 -Minutes 10 -MinutesX1 5      # đặt 0 để bỏ qua một lượt
```

Locust và API chạy trên cùng một máy nên kết quả là cận trên (máy vừa tạo tải vừa phục vụ).

**Lưu ý về keep-alive.** API phải chạy với `--timeout-keep-alive 65`. Với mặc định 5 giây của uvicorn, client có think-time 2–5 giây thỉnh thoảng gửi request đúng lúc server đóng kết nối nhàn rỗi và phải chờ TCP hết giờ: đo được vài request lẻ mất 30–69 giây trong khi PostgreSQL không ghi nhận truy vấn nào quá 1 giây. Đặt 65 giây thì request chậm nhất còn 0,55 giây.

## Mục tiêu

| Hạng mục | Mục tiêu |
|---|---|
| Truy vấn SQL | ≤ 100 ms mỗi truy vấn; không Seq Scan trên bảng fact lớn |
| API | p95 < 500 ms, p99 < 1 s, lỗi < 0,1% |
| Tải trang | Biểu đồ đầu tiên < 1 s, LCP < 2,5 s, TTI < 3 s |
| ETL | traffic < 30 s, risk < 5 phút, nightly < 20 phút |
| Export | Excel 10.000 dòng, PDF 500 dòng < 5 s |
