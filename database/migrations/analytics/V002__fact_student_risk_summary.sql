-- =============================================================================
-- V002 – FACT 1: fact_student_risk_summary
-- Cảnh báo sinh viên nguy cơ theo từng (môn, sinh viên, ngày snapshot)
-- Phục vụ: Giảng viên 2.1 (Đèn giao thông, Modal chi tiết), 2.2 (so sánh cá nhân)
-- Tài liệu: SPEC/KE_HOACH_TRIEN_KHAI.md – Phần 1.6, 2.2, 2.3
-- =============================================================================

CREATE TABLE analytics.fact_student_risk_summary (
    snapshot_date             DATE                       NOT NULL,
    course_id                 INTEGER                    NOT NULL,
    user_id                   INTEGER                    NOT NULL,

    -- Chiều phi chuẩn hóa (API không cần JOIN)
    faculty_id                INTEGER                    NOT NULL,
    faculty_name              VARCHAR(255)               NOT NULL,
    course_shortname          VARCHAR(255)               NOT NULL,
    course_fullname           VARCHAR(255)               NOT NULL,
    academic_year             analytics.academic_year_t  NOT NULL,
    semester                  analytics.semester_t       NOT NULL,
    teacher_ids               INTEGER[]                  NOT NULL DEFAULT '{}',
    student_code              VARCHAR(100),
    student_name              VARCHAR(255)               NOT NULL,
    email                     VARCHAR(255),

    -- Tiêu chí 2: tương tác
    total_access_count        INTEGER                    NOT NULL DEFAULT 0,
    access_count_7d           INTEGER                    NOT NULL DEFAULT 0,
    access_count_14d          INTEGER                    NOT NULL DEFAULT 0,
    active_actions            INTEGER                    NOT NULL DEFAULT 0,
    last_access_time          TIMESTAMPTZ,
    days_since_last_access    INTEGER,

    -- Tiêu chí 1: điểm danh
    total_sessions            SMALLINT                   NOT NULL DEFAULT 0,
    attended_sessions         SMALLINT                   NOT NULL DEFAULT 0,
    absent_sessions           SMALLINT                   NOT NULL DEFAULT 0,
    absence_rate              analytics.percent_t        NOT NULL DEFAULT 0,
    attendance_status         VARCHAR(10)                NOT NULL DEFAULT 'NO_DATA',

    -- Tiêu chí 3: bài tập
    total_assignments         SMALLINT                   NOT NULL DEFAULT 0,
    submitted_assignments     SMALLINT                   NOT NULL DEFAULT 0,
    missing_assignments_count SMALLINT                   NOT NULL DEFAULT 0,
    late_submissions          SMALLINT                   NOT NULL DEFAULT 0,
    completion_rate           analytics.percent_t        NOT NULL DEFAULT 0,

    -- Kết quả đánh giá rủi ro
    score_attendance          SMALLINT                   NOT NULL DEFAULT 0,
    score_inactivity          SMALLINT                   NOT NULL DEFAULT 0,
    score_assignment          SMALLINT                   NOT NULL DEFAULT 0,
    risk_score                SMALLINT                   NOT NULL DEFAULT 0,
    risk_level                analytics.risk_level_t     NOT NULL,
    risk_reasons              JSONB                      NOT NULL DEFAULT '[]',

    -- Dữ liệu cho Modal chi tiết (tránh truy vấn ngược về Moodle)
    weekly_activity           JSONB                      NOT NULL DEFAULT '[]',
    assignment_detail         JSONB                      NOT NULL DEFAULT '[]',
    class_avg_access          NUMERIC(8, 2),

    etl_run_id                BIGINT,
    updated_at                TIMESTAMPTZ                NOT NULL DEFAULT now(),

    CONSTRAINT pk_fact_student_risk_summary PRIMARY KEY (course_id, user_id, snapshot_date),
    CONSTRAINT fk_risk_etl_run FOREIGN KEY (etl_run_id)
        REFERENCES analytics.etl_run_log (run_id) ON DELETE SET NULL,

    -- Toàn vẹn dữ liệu
    CONSTRAINT ck_risk_teacher_ids_no_null CHECK (array_position(teacher_ids, NULL) IS NULL),
    CONSTRAINT ck_risk_access_non_negative CHECK (
        total_access_count >= 0 AND access_count_7d >= 0 AND access_count_14d >= 0 AND active_actions >= 0),
    CONSTRAINT ck_risk_access_windows      CHECK (access_count_7d <= access_count_14d
                                                  AND access_count_14d <= total_access_count),
    CONSTRAINT ck_risk_last_access_pair    CHECK ((last_access_time IS NULL) = (days_since_last_access IS NULL)),
    CONSTRAINT ck_risk_days_non_negative   CHECK (days_since_last_access IS NULL OR days_since_last_access >= 0),
    CONSTRAINT ck_risk_sessions            CHECK (attended_sessions >= 0 AND absent_sessions >= 0
                                                  AND attended_sessions + absent_sessions <= total_sessions),
    CONSTRAINT ck_risk_attendance_status   CHECK (attendance_status IN ('OK', 'WARN', 'CRITICAL', 'NO_DATA')),
    CONSTRAINT ck_risk_attendance_no_data  CHECK ((total_sessions = 0) = (attendance_status = 'NO_DATA')),
    CONSTRAINT ck_risk_assignments         CHECK (submitted_assignments >= 0
                                                  AND submitted_assignments <= total_assignments
                                                  AND missing_assignments_count = total_assignments - submitted_assignments
                                                  AND late_submissions BETWEEN 0 AND submitted_assignments),
    CONSTRAINT ck_risk_scores              CHECK (score_attendance BETWEEN 0 AND 2
                                                  AND score_inactivity BETWEEN 0 AND 2
                                                  AND score_assignment BETWEEN 0 AND 2
                                                  AND risk_score BETWEEN 0 AND 100),
    CONSTRAINT ck_risk_json_arrays         CHECK (jsonb_typeof(risk_reasons) = 'array'
                                                  AND jsonb_typeof(weekly_activity) = 'array'
                                                  AND jsonb_typeof(assignment_detail) = 'array'),
    CONSTRAINT ck_risk_class_avg           CHECK (class_avg_access IS NULL OR class_avg_access >= 0)
);

COMMENT ON TABLE analytics.fact_student_risk_summary IS
    'Tổng hợp chỉ số tương tác và cảnh báo rủi ro của từng sinh viên theo môn, mỗi ngày một snapshot';
COMMENT ON COLUMN analytics.fact_student_risk_summary.teacher_ids IS 'mdl_user.id của GV (editingteacher/teacher) – dùng phân quyền';
COMMENT ON COLUMN analytics.fact_student_risk_summary.student_code IS 'MSSV = mdl_user.idnumber';
COMMENT ON COLUMN analytics.fact_student_risk_summary.days_since_last_access IS 'NULL = chưa từng truy cập môn học';
COMMENT ON COLUMN analytics.fact_student_risk_summary.total_assignments IS 'Số bài tập đã tới hạn nộp';
COMMENT ON COLUMN analytics.fact_student_risk_summary.risk_reasons IS 'Mảng lý do, vd ["Vắng 5/12 buổi (42%)", "Thiếu 4/5 bài tập"]';
COMMENT ON COLUMN analytics.fact_student_risk_summary.weekly_activity IS '[{"week":1,"views":12,"actions":2,"attended":true}]';
COMMENT ON COLUMN analytics.fact_student_risk_summary.assignment_detail IS '[{"name":"BT1","duedate":"...","status":"submitted","late":false}]';

-- Bảng đèn giao thông của GV: lọc môn + snapshot mới nhất + mức rủi ro, sắp xếp theo điểm
CREATE INDEX ix_risk_course_date_level ON analytics.fact_student_risk_summary
    (course_id, snapshot_date DESC, risk_level, risk_score DESC);
-- Phân quyền giảng viên: :teacher_id = ANY(teacher_ids)
CREATE INDEX ix_risk_teacher_gin ON analytics.fact_student_risk_summary USING GIN (teacher_ids);
-- Lịch sử cảnh báo của một sinh viên
CREATE INDEX ix_risk_user ON analytics.fact_student_risk_summary (user_id, snapshot_date DESC);
-- Báo cáo/Export theo khoa – học kỳ
CREATE INDEX ix_risk_faculty_term ON analytics.fact_student_risk_summary
    (faculty_id, academic_year, semester, snapshot_date);
-- Đếm nhanh sinh viên ĐỎ
CREATE INDEX ix_risk_red_partial ON analytics.fact_student_risk_summary (course_id, snapshot_date)
    WHERE risk_level = 'RED';
-- Liên kết tới lần chạy ETL (hỗ trợ ON DELETE SET NULL khi dọn etl_run_log)
CREATE INDEX ix_risk_etl_run ON analytics.fact_student_risk_summary (etl_run_id);

CREATE TRIGGER trg_risk_updated_at
    BEFORE UPDATE ON analytics.fact_student_risk_summary
    FOR EACH ROW EXECUTE FUNCTION analytics.set_updated_at();
