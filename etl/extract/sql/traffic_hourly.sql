-- Admin 1.2 – lưu lượng theo giờ địa phương trong [:from_ts, :to_ts) (SPEC 1.4)
-- Tính lại TOÀN BỘ các giờ bị ảnh hưởng (không cộng dồn) để COUNT(DISTINCT userid) luôn đúng khi chạy lại.
SELECT date_trunc('hour', to_timestamp(l.timecreated) AT TIME ZONE :tz)  AS stat_hour,
       COUNT(*)                                                         AS total_requests,
       COUNT(DISTINCT l.userid) FILTER (WHERE l.userid > 0)             AS unique_users,
       COUNT(*) FILTER (WHERE l.eventname = :login_event)               AS login_count,
       COUNT(*) FILTER (WHERE l.eventname = :failed_login_event)        AS failed_login_count,
       COUNT(*) FILTER (WHERE l.origin = 'ws')                          AS ws_requests
FROM mdl_logstore_standard_log l
WHERE l.timecreated >= :from_ts
  AND l.timecreated <  :to_ts
GROUP BY 1
ORDER BY 1
