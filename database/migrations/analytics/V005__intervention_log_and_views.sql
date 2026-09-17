-- =============================================================================
-- V005 – Nhật ký can thiệp của giảng viên + view snapshot rủi ro mới nhất
-- Tài liệu: SPEC/KE_HOACH_TRIEN_KHAI.md – Phần 2.2, 5.1 (POST interventions)
-- =============================================================================

CREATE TABLE analytics.intervention_log (
    id                  BIGINT                  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id           INTEGER                 NOT NULL,
    user_id             INTEGER                 NOT NULL,
    teacher_id          INTEGER                 NOT NULL,
    action_type         VARCHAR(20)             NOT NULL,
    content             TEXT,
    risk_level_at_time  analytics.risk_level_t,
    created_at          TIMESTAMPTZ             NOT NULL DEFAULT now(),
    CONSTRAINT fk_intervention_teacher FOREIGN KEY (teacher_id)
        REFERENCES analytics.app_user (user_id) ON DELETE RESTRICT,
    CONSTRAINT ck_intervention_action  CHECK (action_type IN ('MESSAGE', 'EMAIL', 'NOTE', 'MEETING'))
);

COMMENT ON TABLE analytics.intervention_log IS 'Hành động can thiệp của GV với sinh viên nguy cơ (nút trong Modal chi tiết)';
COMMENT ON COLUMN analytics.intervention_log.risk_level_at_time IS 'Mức rủi ro của SV tại thời điểm can thiệp';

CREATE INDEX ix_intervention_course_user ON analytics.intervention_log (course_id, user_id, created_at DESC);
CREATE INDEX ix_intervention_teacher ON analytics.intervention_log (teacher_id);

-- -----------------------------------------------------------------------------
-- View: snapshot rủi ro mới nhất của mỗi (môn, sinh viên) – API giảng viên dùng view này.
-- Lưu ý: "*" được PostgreSQL mở rộng lúc tạo view; khi thêm cột mới vào bảng fact
-- phải tạo migration CREATE OR REPLACE VIEW tương ứng.
-- -----------------------------------------------------------------------------
CREATE VIEW analytics.v_student_risk_latest AS
SELECT DISTINCT ON (course_id, user_id) *
FROM analytics.fact_student_risk_summary
ORDER BY course_id, user_id, snapshot_date DESC;

COMMENT ON VIEW analytics.v_student_risk_latest IS 'Bản ghi rủi ro mới nhất theo từng (course_id, user_id)';
