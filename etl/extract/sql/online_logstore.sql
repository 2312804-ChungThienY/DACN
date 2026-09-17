-- Số người dùng khác nhau có sự kiện trong từng khung :slot giây của [:from_ts, :to_ts)
-- (:from_ts phải là mốc chia hết cho khung – đầu giờ). Khung không có sự kiện không xuất hiện ở đây,
-- bước Transform bổ sung giá trị 0.
SELECT to_timestamp(CAST(:from_ts AS bigint)
                    + ((l.timecreated - CAST(:from_ts AS bigint)) / CAST(:slot AS bigint)) * CAST(:slot AS bigint))
           AT TIME ZONE :tz            AS slot_start,
       COUNT(DISTINCT l.userid)        AS online_users
FROM mdl_logstore_standard_log l
WHERE l.timecreated >= :from_ts
  AND l.timecreated <  :to_ts
  AND l.userid > 0
GROUP BY 1
ORDER BY 1
