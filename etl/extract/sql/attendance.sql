-- Tiêu chí 1 – điểm danh (SPEC 1.6a), trả về MỖI (SV, buổi) để tính cả tổng và theo tuần.
-- Buổi được tính khi đã diễn ra và đã điểm danh trước :as_of. Buổi gắn nhóm chỉ tính SV thuộc nhóm.
-- acronym NULL = không có bản ghi điểm danh -> coi là vắng.
WITH student_enrol AS ({{student_enrol}})
SELECT a.course     AS course_id,
       se.user_id,
       s.id         AS session_id,
       s.sessdate,
       st.acronym
FROM mdl_attendance a
JOIN mdl_attendance_sessions s        ON s.attendanceid = a.id
                                     AND s.lasttaken > 0
                                     AND s.lasttaken <= :as_of
                                     AND s.sessdate < :as_of
JOIN student_enrol se                 ON se.course_id = a.course
LEFT JOIN mdl_groups_members gm       ON gm.groupid = s.groupid AND gm.userid = se.user_id
LEFT JOIN mdl_attendance_log al       ON al.sessionid = s.id AND al.studentid = se.user_id
LEFT JOIN mdl_attendance_statuses st  ON st.id = al.statusid
WHERE a.course = ANY(CAST(:course_ids AS bigint[]))
  AND (s.groupid = 0 OR gm.id IS NOT NULL)
ORDER BY a.course, se.user_id, s.sessdate
