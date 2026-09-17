-- Gộp mẫu online từ bảng tạm. Quy tắc ưu tiên nguồn:
--   mẫu SESSIONS (chụp thật từ mdl_sessions) luôn ghi đè; mẫu LOGSTORE (suy ra từ log) không ghi đè mẫu SESSIONS.
INSERT INTO analytics.etl_online_snapshot AS o (slot_start, online_users, source, etl_run_id)
SELECT slot_start, online_users, source, etl_run_id
FROM tmp_etl_online_snapshot
ON CONFLICT (slot_start) DO UPDATE
SET online_users = EXCLUDED.online_users,
    source       = EXCLUDED.source,
    etl_run_id   = EXCLUDED.etl_run_id
WHERE (o.source = 'LOGSTORE' OR EXCLUDED.source = 'SESSIONS')
  AND (o.online_users, o.source) IS DISTINCT FROM (EXCLUDED.online_users, EXCLUDED.source)
