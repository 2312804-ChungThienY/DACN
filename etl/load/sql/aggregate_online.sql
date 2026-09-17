-- Tính lại peak/avg/số mẫu online của các giờ trong [:from_hour, :to_hour) từ etl_online_snapshot
WITH samples AS (
    SELECT h.stat_hour,
           COALESCE(MAX(o.online_users), 0)            AS peak,
           COALESCE(ROUND(AVG(o.online_users), 2), 0)  AS avg,
           COUNT(o.slot_start)                         AS n
    FROM analytics.fact_server_traffic_hourly h
    LEFT JOIN analytics.etl_online_snapshot o
           ON o.slot_start >= h.stat_hour
          AND o.slot_start <  h.stat_hour + INTERVAL '1 hour'
    WHERE h.stat_hour >= :from_hour
      AND h.stat_hour <  :to_hour
    GROUP BY h.stat_hour
)
UPDATE analytics.fact_server_traffic_hourly f
SET peak_online_users   = s.peak,
    avg_online_users    = s.avg,
    online_sample_count = s.n,
    etl_run_id          = :run_id
FROM samples s
WHERE f.stat_hour = s.stat_hour
  AND (f.peak_online_users, f.avg_online_users, f.online_sample_count) IS DISTINCT FROM (s.peak, s.avg, s.n)
