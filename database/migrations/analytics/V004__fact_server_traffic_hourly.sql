-- =============================================================================
-- V004 – FACT 3: fact_server_traffic_hourly
-- Lưu lượng truy cập và người dùng online theo từng giờ
-- Phục vụ: Admin 1.2 (Dual-axis Line, Peak Traffic Card, Heatmap)
-- Tài liệu: SPEC/KE_HOACH_TRIEN_KHAI.md – Phần 1.4, 2.2
--
-- stat_date / hour_of_day / day_of_week là GENERATED COLUMN tính từ stat_hour,
-- nên không bao giờ lệch nhau (ETL chỉ ghi stat_hour).
-- =============================================================================

CREATE TABLE analytics.fact_server_traffic_hourly (
    stat_hour           TIMESTAMP     NOT NULL,
    stat_date           DATE          GENERATED ALWAYS AS (stat_hour::date) STORED,
    hour_of_day         SMALLINT      GENERATED ALWAYS AS (EXTRACT(HOUR FROM stat_hour)::smallint) STORED,
    day_of_week         SMALLINT      GENERATED ALWAYS AS (EXTRACT(ISODOW FROM stat_hour)::smallint) STORED,

    total_requests      INTEGER       NOT NULL DEFAULT 0,
    unique_users        INTEGER       NOT NULL DEFAULT 0,
    login_count         INTEGER       NOT NULL DEFAULT 0,
    failed_login_count  INTEGER       NOT NULL DEFAULT 0,
    ws_requests         INTEGER       NOT NULL DEFAULT 0,

    peak_online_users   INTEGER       NOT NULL DEFAULT 0,
    avg_online_users    NUMERIC(8, 2) NOT NULL DEFAULT 0,
    online_sample_count SMALLINT      NOT NULL DEFAULT 0,
    is_peak_hour        BOOLEAN       NOT NULL DEFAULT FALSE,

    etl_run_id          BIGINT,
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT pk_fact_server_traffic_hourly PRIMARY KEY (stat_hour),
    CONSTRAINT fk_traffic_etl_run FOREIGN KEY (etl_run_id)
        REFERENCES analytics.etl_run_log (run_id) ON DELETE SET NULL,

    CONSTRAINT ck_traffic_truncated_hour CHECK (stat_hour = date_trunc('hour', stat_hour)),
    CONSTRAINT ck_traffic_non_negative   CHECK (
        total_requests >= 0 AND unique_users >= 0 AND login_count >= 0 AND failed_login_count >= 0
        AND ws_requests >= 0 AND peak_online_users >= 0 AND avg_online_users >= 0 AND online_sample_count >= 0),
    -- Mỗi user hoạt động sinh ít nhất 1 sự kiện; các loại sự kiện là tập con của tổng
    CONSTRAINT ck_traffic_subsets        CHECK (unique_users <= total_requests
                                                AND login_count + failed_login_count <= total_requests
                                                AND ws_requests <= total_requests),
    -- Trung bình các snapshot không vượt quá giá trị lớn nhất
    CONSTRAINT ck_traffic_online_avg     CHECK (avg_online_users <= peak_online_users),
    CONSTRAINT ck_traffic_online_samples CHECK (online_sample_count > 0
                                                OR (peak_online_users = 0 AND avg_online_users = 0))
);

COMMENT ON TABLE analytics.fact_server_traffic_hourly IS
    'Lưu lượng truy cập (sự kiện logstore) và người dùng online theo giờ';
COMMENT ON COLUMN analytics.fact_server_traffic_hourly.stat_hour IS 'Đầu giờ, theo giờ địa phương Asia/Ho_Chi_Minh';
COMMENT ON COLUMN analytics.fact_server_traffic_hourly.day_of_week IS 'ISO: 1 = Thứ 2 ... 7 = Chủ nhật';
COMMENT ON COLUMN analytics.fact_server_traffic_hourly.total_requests IS
    'Proxy lượt request = số sự kiện trong mdl_logstore_standard_log (không phải HTTP request thật)';
COMMENT ON COLUMN analytics.fact_server_traffic_hourly.peak_online_users IS 'MAX các snapshot mdl_sessions 5 phút trong giờ';
COMMENT ON COLUMN analytics.fact_server_traffic_hourly.online_sample_count IS 'Số snapshot đã gộp, dùng để cập nhật trung bình cộng dồn';
COMMENT ON COLUMN analytics.fact_server_traffic_hourly.is_peak_hour IS 'total_requests > P90 của 28 ngày gần nhất';

-- Heatmap giờ × ngày, lọc theo ngày
CREATE INDEX ix_traffic_date_hour ON analytics.fact_server_traffic_hourly (stat_date, hour_of_day);
-- Quét khoảng thời gian dài
CREATE INDEX ix_traffic_brin ON analytics.fact_server_traffic_hourly USING BRIN (stat_hour);
CREATE INDEX ix_traffic_etl_run ON analytics.fact_server_traffic_hourly (etl_run_id);

CREATE TRIGGER trg_traffic_updated_at
    BEFORE UPDATE ON analytics.fact_server_traffic_hourly
    FOR EACH ROW EXECUTE FUNCTION analytics.set_updated_at();
