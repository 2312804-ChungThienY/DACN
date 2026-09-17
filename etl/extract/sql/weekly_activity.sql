-- Hoạt động theo tuần học của từng SV (dữ liệu biểu đồ "Line hoạt động 15 tuần" trong Modal chi tiết – SPEC 5.3)
-- Tuần 1 bắt đầu tại mdl_course.startdate.
-- Gom log theo (môn, SV, tuần) TRƯỚC rồi mới nối với danh sách ghi danh (hash join trên kết quả đã gom),
-- không nối trực tiếp bảng log lớn với CTE ghi danh.
WITH student_enrol AS ({{student_enrol}}),
weekly AS (
    SELECT l.courseid                                          AS course_id,
           l.userid                                            AS user_id,
           ((l.timecreated - c.startdate) / 604800)::int + 1   AS week,
           COUNT(*) FILTER (WHERE l.crud = 'r')                AS views,
           COUNT(*) FILTER (WHERE l.crud IN ('c', 'u'))        AS actions
    FROM mdl_logstore_standard_log l
    JOIN mdl_course c ON c.id = l.courseid
    WHERE l.courseid = ANY(CAST(:course_ids AS bigint[]))
      AND l.anonymous = 0
      AND l.timecreated >= c.startdate
      AND l.timecreated <= :as_of
    GROUP BY 1, 2, 3
)
SELECT w.course_id, w.user_id, w.week, w.views, w.actions
FROM weekly w
JOIN student_enrol se ON se.course_id = w.course_id AND se.user_id = w.user_id
ORDER BY 1, 2, 3
