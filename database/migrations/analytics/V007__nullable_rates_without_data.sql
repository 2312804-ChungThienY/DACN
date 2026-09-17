-- =============================================================================
-- V007 – Tỷ lệ "chưa có dữ liệu" lưu NULL thay vì 0
--
-- Trước đây khi mẫu số bằng 0 (môn chưa có buổi điểm danh, chưa có bài tập tới hạn, chưa có hoạt động
-- theo dõi hoàn thành), ETL ghi tỷ lệ = 0. Dashboard khi đó hiển thị "Chuyên cần 0%" – dễ bị hiểu là
-- không sinh viên nào đi học. Từ phiên bản này:
--     NULL = chưa có dữ liệu để tính (API/Frontend hiển thị "Chưa có dữ liệu")
--     0    = có dữ liệu và tỷ lệ thật sự bằng 0
-- Cần chạy lại ETL backfill để các tỷ lệ cũ không suy ra được từ bảng fact (vd attendance_rate của môn)
-- được ghi lại đúng.
-- =============================================================================

-- ---------------------------------------------------------------- fact_student_risk_summary
ALTER TABLE analytics.fact_student_risk_summary
    ALTER COLUMN absence_rate    DROP NOT NULL,
    ALTER COLUMN absence_rate    DROP DEFAULT,
    ALTER COLUMN completion_rate DROP NOT NULL,
    ALTER COLUMN completion_rate DROP DEFAULT;

-- Suy ra được ngay từ total_sessions: sửa dữ liệu cũ trước khi thêm ràng buộc
UPDATE analytics.fact_student_risk_summary
SET absence_rate = NULL
WHERE total_sessions = 0 AND absence_rate IS NOT NULL;

ALTER TABLE analytics.fact_student_risk_summary
    ADD CONSTRAINT ck_risk_absence_rate_no_data CHECK ((total_sessions = 0) = (absence_rate IS NULL));

COMMENT ON COLUMN analytics.fact_student_risk_summary.absence_rate IS
    '% buổi vắng / buổi đã điểm danh; NULL khi chưa có buổi điểm danh nào';
COMMENT ON COLUMN analytics.fact_student_risk_summary.completion_rate IS
    '% hoạt động đã hoàn thành / hoạt động theo dõi đã tới hạn; NULL khi chưa có hoạt động nào tới hạn';

-- ---------------------------------------------------------------- fact_course_progress_daily
ALTER TABLE analytics.fact_course_progress_daily
    ALTER COLUMN assignment_submission_rate DROP NOT NULL,
    ALTER COLUMN assignment_submission_rate DROP DEFAULT,
    ALTER COLUMN attendance_rate            DROP NOT NULL,
    ALTER COLUMN attendance_rate            DROP DEFAULT,
    ALTER COLUMN avg_completion_rate        DROP NOT NULL,
    ALTER COLUMN avg_completion_rate        DROP DEFAULT;

-- Suy ra được từ total_assignments (số bài đã tới hạn của môn)
UPDATE analytics.fact_course_progress_daily
SET assignment_submission_rate = NULL
WHERE total_assignments = 0 AND assignment_submission_rate IS NOT NULL;

COMMENT ON COLUMN analytics.fact_course_progress_daily.assignment_submission_rate IS
    '% bài đã nộp / (bài đã tới hạn × SV); NULL khi chưa có bài tới hạn';
COMMENT ON COLUMN analytics.fact_course_progress_daily.attendance_rate IS
    '% lượt có mặt / lượt điểm danh; NULL khi môn chưa có buổi điểm danh';
COMMENT ON COLUMN analytics.fact_course_progress_daily.avg_completion_rate IS
    '% hoạt động hoàn thành của lớp; NULL khi chưa có hoạt động theo dõi nào tới hạn';
