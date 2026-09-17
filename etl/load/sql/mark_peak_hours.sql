-- is_peak_hour = total_requests > P90 của các giờ trong 28 ngày kết thúc tại ngày đó (SPEC 2.2, 4.2)
WITH days AS (
    SELECT DISTINCT stat_date
    FROM analytics.fact_server_traffic_hourly
    WHERE stat_date BETWEEN :from_date AND :to_date
), thresholds AS (
    SELECT d.stat_date,
           (SELECT percentile_cont(CAST(:percentile AS double precision)) WITHIN GROUP (ORDER BY h.total_requests)
            FROM analytics.fact_server_traffic_hourly h
            WHERE h.stat_date >  d.stat_date - CAST(:window_days AS integer)
              AND h.stat_date <= d.stat_date) AS threshold
    FROM days d
)
UPDATE analytics.fact_server_traffic_hourly f
SET is_peak_hour = (f.total_requests > t.threshold)
FROM thresholds t
WHERE f.stat_date = t.stat_date
  AND f.is_peak_hour IS DISTINCT FROM (f.total_requests > t.threshold)
