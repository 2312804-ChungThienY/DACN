-- =============================================================================
-- V001 – Schema "analytics", domain dùng chung, bảng phụ trợ ETL & ứng dụng
-- Tài liệu: SPEC/KE_HOACH_TRIEN_KHAI.md – Phần 2.1, 2.2 (BẢNG PHỤ TRỢ)
-- Lưu ý: database/migrate.py tự bọc mỗi file trong 1 transaction,
--        KHÔNG viết BEGIN/COMMIT trong file migration.
-- =============================================================================

CREATE SCHEMA analytics;
COMMENT ON SCHEMA analytics IS
    'CSDL phân tích LMS: 3 bảng fact phục vụ Dashboard và các bảng phụ trợ ETL/ứng dụng';

-- -----------------------------------------------------------------------------
-- Domain: gom các ràng buộc lặp lại ở nhiều bảng về một chỗ
-- -----------------------------------------------------------------------------
CREATE DOMAIN analytics.academic_year_t AS VARCHAR(9)
    CHECK (
        VALUE IS NULL OR
        CASE WHEN VALUE ~ '^[0-9]{4}-[0-9]{4}$'
             THEN substr(VALUE, 6, 4)::int = substr(VALUE, 1, 4)::int + 1
             ELSE FALSE
        END
    );
COMMENT ON DOMAIN analytics.academic_year_t IS 'Năm học dạng YYYY-YYYY, năm sau = năm trước + 1 (vd 2026-2027)';

CREATE DOMAIN analytics.semester_t AS SMALLINT
    CHECK (VALUE BETWEEN 1 AND 3);
COMMENT ON DOMAIN analytics.semester_t IS 'Học kỳ: 1 = HK1, 2 = HK2, 3 = HK hè';

CREATE DOMAIN analytics.percent_t AS NUMERIC(5, 2)
    CHECK (VALUE BETWEEN 0 AND 100);
COMMENT ON DOMAIN analytics.percent_t IS 'Tỷ lệ phần trăm 0.00 – 100.00';

CREATE DOMAIN analytics.risk_level_t AS VARCHAR(6)
    CHECK (VALUE IN ('RED', 'YELLOW', 'GREEN'));
COMMENT ON DOMAIN analytics.risk_level_t IS 'Đèn giao thông: RED = nguy cơ cao, YELLOW = cần lưu ý, GREEN = an toàn';

-- -----------------------------------------------------------------------------
-- Trigger dùng chung: luôn cập nhật updated_at khi bản ghi bị UPDATE
-- (kể cả qua INSERT ... ON CONFLICT DO UPDATE của ETL)
-- -----------------------------------------------------------------------------
CREATE FUNCTION analytics.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql AS
$$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- -----------------------------------------------------------------------------
-- etl_run_log: nhật ký mỗi lần chạy job ETL
-- -----------------------------------------------------------------------------
CREATE TABLE analytics.etl_run_log (
    run_id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_name        VARCHAR(50)  NOT NULL,
    started_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(10)  NOT NULL DEFAULT 'RUNNING',
    rows_extracted  INTEGER,
    rows_loaded     INTEGER,
    error_message   TEXT,
    CONSTRAINT ck_etl_run_status   CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    CONSTRAINT ck_etl_run_finished CHECK ((status = 'RUNNING') = (finished_at IS NULL)),
    CONSTRAINT ck_etl_run_time     CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT ck_etl_run_rows     CHECK (COALESCE(rows_extracted, 0) >= 0 AND COALESCE(rows_loaded, 0) >= 0),
    CONSTRAINT ck_etl_run_error    CHECK (status <> 'FAILED' OR error_message IS NOT NULL)
);
COMMENT ON TABLE analytics.etl_run_log IS 'Nhật ký chạy ETL (traffic | course_progress | student_risk | nightly | ...)';

CREATE INDEX ix_etl_run_job_time ON analytics.etl_run_log (job_name, started_at DESC);

-- -----------------------------------------------------------------------------
-- etl_watermark: mốc trích xuất tăng dần theo mdl_logstore_standard_log.id
-- -----------------------------------------------------------------------------
CREATE TABLE analytics.etl_watermark (
    job_name     VARCHAR(50) PRIMARY KEY,
    last_log_id  BIGINT      NOT NULL DEFAULT 0,
    last_run_at  TIMESTAMPTZ,
    CONSTRAINT ck_watermark_log_id CHECK (last_log_id >= 0)
);
COMMENT ON TABLE analytics.etl_watermark IS 'Watermark trích xuất incremental cho từng job ETL';
COMMENT ON COLUMN analytics.etl_watermark.last_log_id IS 'mdl_logstore_standard_log.id lớn nhất đã xử lý';

-- -----------------------------------------------------------------------------
-- app_user: tài khoản đăng nhập Dashboard (Admin / Giảng viên)
-- -----------------------------------------------------------------------------
CREATE TABLE analytics.app_user (
    user_id        INTEGER      PRIMARY KEY,
    username       VARCHAR(100) NOT NULL,
    full_name      VARCHAR(255),
    email          VARCHAR(255),
    role           VARCHAR(10)  NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_app_user_username UNIQUE (username),
    CONSTRAINT ck_app_user_role     CHECK (role IN ('ADMIN', 'TEACHER'))
);
COMMENT ON TABLE analytics.app_user IS 'Tài khoản Dashboard; user_id = mdl_user.id để khớp teacher_ids trong bảng fact';
COMMENT ON COLUMN analytics.app_user.password_hash IS 'bcrypt hash';

CREATE TRIGGER trg_app_user_updated_at
    BEFORE UPDATE ON analytics.app_user
    FOR EACH ROW EXECUTE FUNCTION analytics.set_updated_at();
