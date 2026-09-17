# Mock data – CSDL nguồn Moodle rút gọn `moodle_src`

Tài liệu thiết kế: [SPEC/KE_HOACH_TRIEN_KHAI.md](../SPEC/KE_HOACH_TRIEN_KHAI.md), Phần 3.

## Phạm vi đã thống nhất

| Tham số | Giá trị |
|---|---|
| Khoa | 1: Khoa Công nghệ Thông tin, gồm 4 bộ môn (danh mục cấp 2) |
| Môn học | 15, HK1 2026-2027, bắt đầu 07/09/2026, dài 15 tuần |
| Người dùng | 500 sinh viên, 8 giảng viên; mỗi SV học 4–6 môn (khoảng 2.500 lượt ghi danh) |
| Thời điểm tham chiếu | `LMS_AS_OF` trong `.env` (mặc định 06/11/2026 10:30, tuần 9). Mọi dữ liệu có thời điểm ≤ AS_OF |
| Hồ sơ hành vi | GREEN 65%, YELLOW 20%, RED 15%, theo đúng SPEC 3.2 |

Các ca biên được sinh chủ động:
- SV bị khóa, SV bị xóa.
- Ghi danh bị tạm dừng, ghi danh hết hạn ở tuần 3.
- Phương thức ghi danh bị tắt.
- Bài nộp nhóm (IT008, IT009).
- Buổi điểm danh theo nhóm (IT013).
- Môn chưa có buổi điểm danh (IT015).
- SV chưa từng truy cập, SV "bỏ dần".
- Đăng nhập lỗi; truy cập từ ứng dụng di động (`origin = ws`).

## Chạy

```powershell
python -m database.migrate up --target moodle     # tạo moodle_src + 25 bảng mdl_*
python -m mockdata.seed_structure --reset         # khoa, môn, người dùng, ghi danh, bài tập, buổi học
python -m mockdata.generate_activity --reset      # log, bài nộp, điểm danh, hoàn thành, phiên online (~1 phút)
python -m pytest tests/mockdata -q                # kiểm tra toàn vẹn dữ liệu
```

Dọn dữ liệu: `python -m mockdata.cleanup --activity` (chỉ xóa hành vi) hoặc `--all` (xóa toàn bộ).

`mockdata/output/ground_truth_profiles.csv` là "đáp án" hồ sơ của từng cặp SV–môn. File này dùng để đo Precision/Recall của luật rủi ro.

> Nếu đổi `LMS_AS_OF`, phải chạy lại `generate_activity --reset` rồi chạy lại ETL backfill.

## Thành phần

| File | Nội dung |
|---|---|
| `config.py` | Toàn bộ tham số: quy mô, hồ sơ hành vi, trọng số giờ/thứ, hệ số cao điểm, ca biên |
| `names.py` | Sinh họ tên tiếng Việt tái lập được |
| `db.py` | Kết nối và nạp dữ liệu (COPY) vào `moodle_src` |
| `seed_structure.py` | Cấu trúc Moodle |
| `generate_activity.py` | Hành vi học tập |
| `cleanup.py` | Xóa dữ liệu giả lập |
