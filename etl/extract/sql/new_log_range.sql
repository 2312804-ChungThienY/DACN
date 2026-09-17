-- Khoảng thời gian của các log mới trong khoảng watermark (:last_id, :max_id]
SELECT COUNT(*)          AS new_logs,
       MIN(timecreated)  AS min_ts,
       MAX(timecreated)  AS max_ts
FROM mdl_logstore_standard_log
WHERE id > :last_id
  AND id <= :max_id
