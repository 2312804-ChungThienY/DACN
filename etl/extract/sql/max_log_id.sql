-- id lớn nhất hiện có của logstore (dùng khóa chính -> rất nhanh)
SELECT COALESCE(MAX(id), 0) AS max_id
FROM mdl_logstore_standard_log
