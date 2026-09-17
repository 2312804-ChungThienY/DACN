-- Tiêu chí 2 – tương tác (SPEC 1.6b) + chỉ số trong ngày cho tiến độ môn (SPEC 1.7)
-- Lần truy cập cuối lấy từ logstore (MAX timecreated <= :as_of) thay vì mdl_user_lastaccess
-- để tính đúng cả khi nạp lại lịch sử (mdl_user_lastaccess chỉ lưu giá trị hiện tại).
-- Gom log theo (môn, SV) một lần rồi mới nối với danh sách ghi danh để tận dụng index (courseid, anonymous, timecreated).
WITH student_enrol AS ({{student_enrol}}),
logs AS (
    SELECT l.courseid AS course_id,
           l.userid   AS user_id,
           MAX(l.timecreated)                                                          AS last_access_ts,
           COUNT(*)                                                                    AS total_access_count,
           COUNT(*) FILTER (WHERE l.timecreated > :as_of - 7 * 86400)                  AS access_count_7d,
           COUNT(*) FILTER (WHERE l.timecreated > :as_of - 14 * 86400)                 AS access_count_14d,
           COUNT(*) FILTER (WHERE l.crud IN ('c', 'u'))                                AS active_actions,
           COUNT(*) FILTER (WHERE l.timecreated >= c.startdate)                        AS term_access_count,
           COUNT(*) FILTER (WHERE l.timecreated >= :day_start)                         AS access_count_day,
           COUNT(*) FILTER (WHERE l.timecreated >= :day_start AND l.crud = 'r')        AS views_day,
           COUNT(*) FILTER (WHERE l.timecreated >= :day_start AND l.crud IN ('c', 'u')) AS actions_day
    FROM mdl_logstore_standard_log l
    JOIN mdl_course c ON c.id = l.courseid
    WHERE l.courseid = ANY(CAST(:course_ids AS bigint[]))
      AND l.anonymous = 0
      AND l.timecreated <= :as_of
    GROUP BY l.courseid, l.userid
)
SELECT se.course_id,
       se.user_id,
       lg.last_access_ts,
       COALESCE(lg.total_access_count, 0) AS total_access_count,
       COALESCE(lg.access_count_7d, 0)    AS access_count_7d,
       COALESCE(lg.access_count_14d, 0)   AS access_count_14d,
       COALESCE(lg.active_actions, 0)     AS active_actions,
       COALESCE(lg.term_access_count, 0)  AS term_access_count,
       COALESCE(lg.access_count_day, 0)   AS access_count_day,
       COALESCE(lg.views_day, 0)          AS views_day,
       COALESCE(lg.actions_day, 0)        AS actions_day
FROM student_enrol se
LEFT JOIN logs lg ON lg.course_id = se.course_id AND lg.user_id = se.user_id
ORDER BY se.course_id, se.user_id
