-- =============================================================================
-- V006 – (1) Bảng mẫu người dùng online theo khung 5 phút
--        (2) Ràng buộc attendance_status khớp điểm tiêu chí C1
-- Tài liệu: SPEC/KE_HOACH_TRIEN_KHAI.md – Phần 1.4, 2.3, 4.2
-- =============================================================================

-- -----------------------------------------------------------------------------
-- (1) etl_online_snapshot
-- Mỗi dòng là một mẫu "số người dùng online" của khung 5 phút [slot_start, slot_start + 5').
-- peak_online_users / avg_online_users / online_sample_count của fact_server_traffic_hourly
-- được TÍNH LẠI từ các mẫu trong giờ (MAX / AVG / COUNT), nhờ đó job chạy lại nhiều lần
-- vẫn cho cùng kết quả (idempotent) – thay cho cộng dồn trung bình dễ bị đếm trùng.
-- Nguồn mẫu:
--   SESSIONS : chụp mdl_sessions (timemodified trong 5 phút) – job traffic mỗi 5 phút.
--   LOGSTORE : số user khác nhau có sự kiện trong khung 5 phút – dùng khi nạp lịch sử
--              (backfill) hoặc bù khung bị lỡ; KHÔNG ghi đè mẫu SESSIONS.
-- -----------------------------------------------------------------------------
CREATE TABLE analytics.etl_online_snapshot (
    slot_start    TIMESTAMP    NOT NULL,
    online_users  INTEGER      NOT NULL,
    source        VARCHAR(10)  NOT NULL,
    etl_run_id    BIGINT,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT pk_etl_online_snapshot PRIMARY KEY (slot_start),
    CONSTRAINT fk_online_etl_run FOREIGN KEY (etl_run_id)
        REFERENCES analytics.etl_run_log (run_id) ON DELETE SET NULL,
    CONSTRAINT ck_online_slot_5min CHECK (slot_start = date_trunc('minute', slot_start)
                                          AND EXTRACT(MINUTE FROM slot_start)::int % 5 = 0),
    CONSTRAINT ck_online_users     CHECK (online_users >= 0),
    CONSTRAINT ck_online_source    CHECK (source IN ('SESSIONS', 'LOGSTORE'))
);
COMMENT ON TABLE analytics.etl_online_snapshot IS
    'Mẫu số người dùng online theo khung 5 phút (giờ địa phương), nguồn để tính peak/avg online theo giờ';
COMMENT ON COLUMN analytics.etl_online_snapshot.slot_start IS 'Đầu khung 5 phút, giờ địa phương Asia/Ho_Chi_Minh';

CREATE INDEX ix_online_etl_run ON analytics.etl_online_snapshot (etl_run_id);

CREATE TRIGGER trg_online_updated_at
    BEFORE UPDATE ON analytics.etl_online_snapshot
    FOR EACH ROW EXECUTE FUNCTION analytics.set_updated_at();

-- -----------------------------------------------------------------------------
-- (2) attendance_status phải khớp score_attendance (quy tắc đã thống nhất):
--     NO_DATA  : chưa có buổi điểm danh nào (score = 0)
--     OK       : C1 = 0   |   WARN : C1 = 1   |   CRITICAL : C1 = 2
-- -----------------------------------------------------------------------------
ALTER TABLE analytics.fact_student_risk_summary
    ADD CONSTRAINT ck_risk_attendance_status_score CHECK (
        (attendance_status IN ('NO_DATA', 'OK') AND score_attendance = 0)
        OR (attendance_status = 'WARN'     AND score_attendance = 1)
        OR (attendance_status = 'CRITICAL' AND score_attendance = 2)
    );
COMMENT ON COLUMN analytics.fact_student_risk_summary.attendance_status IS
    'NO_DATA = chưa có buổi điểm danh; OK/WARN/CRITICAL tương ứng score_attendance 0/1/2';
