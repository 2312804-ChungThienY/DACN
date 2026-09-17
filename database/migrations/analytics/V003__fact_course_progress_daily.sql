-- =============================================================================
-- V003 – FACT 2: fact_course_progress_daily
-- Tiến độ và tương tác của từng môn học theo ngày
-- Phục vụ: Admin 1.1 (Khoa → Môn → SV), Admin 1.3 (Export), Giảng viên 2.2 (Tiến độ lớp)
-- Tài liệu: SPEC/KE_HOACH_TRIEN_KHAI.md – Phần 1.3, 1.7, 2.2
-- =============================================================================

CREATE TABLE analytics.fact_course_progress_daily (
    stat_date                  DATE                       NOT NULL,
    course_id                  INTEGER                    NOT NULL,

    -- Chiều phi chuẩn hóa
    faculty_id                 INTEGER                    NOT NULL,
    faculty_name               VARCHAR(255)               NOT NULL,
    category_id                INTEGER                    NOT NULL,
    category_name              VARCHAR(255)               NOT NULL,
    course_shortname           VARCHAR(255)               NOT NULL,
    course_fullname            VARCHAR(255)               NOT NULL,
    academic_year              analytics.academic_year_t  NOT NULL,
    semester                   analytics.semester_t       NOT NULL,
    teacher_ids                INTEGER[]                  NOT NULL DEFAULT '{}',

    -- Quy mô & tương tác
    total_enrolled_students    INTEGER                    NOT NULL DEFAULT 0,
    active_students_day        INTEGER                    NOT NULL DEFAULT 0,
    active_students_7d         INTEGER                    NOT NULL DEFAULT 0,
    total_active_students      INTEGER                    NOT NULL DEFAULT 0,
    total_views_day            INTEGER                    NOT NULL DEFAULT 0,
    total_actions_day          INTEGER                    NOT NULL DEFAULT 0,
    submissions_day            INTEGER                    NOT NULL DEFAULT 0,

    -- Tiến độ
    total_assignments          SMALLINT                   NOT NULL DEFAULT 0,
    assignment_submission_rate analytics.percent_t        NOT NULL DEFAULT 0,
    attendance_rate            analytics.percent_t        NOT NULL DEFAULT 0,
    avg_completion_rate        analytics.percent_t        NOT NULL DEFAULT 0,
    avg_access_per_student     NUMERIC(8, 2)              NOT NULL DEFAULT 0,

    -- Phân bố đèn giao thông (lấy từ snapshot rủi ro cùng ngày)
    red_count                  INTEGER                    NOT NULL DEFAULT 0,
    yellow_count               INTEGER                    NOT NULL DEFAULT 0,
    green_count                INTEGER                    NOT NULL DEFAULT 0,

    section_progress           JSONB                      NOT NULL DEFAULT '[]',

    etl_run_id                 BIGINT,
    updated_at                 TIMESTAMPTZ                NOT NULL DEFAULT now(),

    CONSTRAINT pk_fact_course_progress_daily PRIMARY KEY (course_id, stat_date),
    CONSTRAINT fk_cpd_etl_run FOREIGN KEY (etl_run_id)
        REFERENCES analytics.etl_run_log (run_id) ON DELETE SET NULL,

    CONSTRAINT ck_cpd_teacher_ids_no_null CHECK (array_position(teacher_ids, NULL) IS NULL),
    CONSTRAINT ck_cpd_non_negative        CHECK (
        total_enrolled_students >= 0 AND active_students_day >= 0 AND active_students_7d >= 0
        AND total_active_students >= 0 AND total_views_day >= 0 AND total_actions_day >= 0
        AND submissions_day >= 0 AND total_assignments >= 0 AND avg_access_per_student >= 0
        AND red_count >= 0 AND yellow_count >= 0 AND green_count >= 0),
    -- Sinh viên hoạt động luôn là tập con của sinh viên đang ghi danh
    CONSTRAINT ck_cpd_active_subset       CHECK (active_students_day <= active_students_7d
                                                 AND active_students_7d <= total_enrolled_students
                                                 AND total_active_students <= total_enrolled_students),
    CONSTRAINT ck_cpd_section_progress    CHECK (jsonb_typeof(section_progress) = 'array')
);

COMMENT ON TABLE analytics.fact_course_progress_daily IS
    'Tổng hợp quy mô đào tạo, tương tác và tiến độ của từng môn học theo ngày';
COMMENT ON COLUMN analytics.fact_course_progress_daily.faculty_id IS 'Khoa = danh mục cấp 1 trong mdl_course_categories.path';
COMMENT ON COLUMN analytics.fact_course_progress_daily.total_active_students IS 'SV có ít nhất 1 log trong môn từ đầu học kỳ (lũy kế)';
COMMENT ON COLUMN analytics.fact_course_progress_daily.total_actions_day IS 'Số thao tác ghi (crud c/u) trong ngày';
COMMENT ON COLUMN analytics.fact_course_progress_daily.section_progress IS '[{"section":1,"name":"Chương 1","completion_rate":82.5}]';

-- Stacked bar / drill-down Admin: lọc học kỳ + khoa, lấy ngày mới nhất
CREATE INDEX ix_cpd_term_faculty ON analytics.fact_course_progress_daily
    (academic_year, semester, faculty_id, stat_date DESC);
-- Quét theo khoảng ngày (dữ liệu chèn tăng dần theo ngày -> BRIN rất nhỏ gọn)
CREATE INDEX ix_cpd_date_brin ON analytics.fact_course_progress_daily USING BRIN (stat_date);
-- Phân quyền giảng viên
CREATE INDEX ix_cpd_teacher_gin ON analytics.fact_course_progress_daily USING GIN (teacher_ids);
CREATE INDEX ix_cpd_etl_run ON analytics.fact_course_progress_daily (etl_run_id);

CREATE TRIGGER trg_cpd_updated_at
    BEFORE UPDATE ON analytics.fact_course_progress_daily
    FOR EACH ROW EXECUTE FUNCTION analytics.set_updated_at();
