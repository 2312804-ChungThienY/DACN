-- CTE dùng chung (SPEC 1.2): sinh viên ghi danh hợp lệ tại thời điểm tham chiếu, trong các môn được chọn.
-- Viết dạng semi-join (EXISTS) cho vai trò 'student': cùng ngữ nghĩa với phép JOIN trong spec nhưng tránh việc
-- planner nhân dồn selectivity của các điều kiện tương quan (course + userid) -> ước lượng 1 dòng -> Nested Loop
-- quét log cho từng SV (nguyên nhân timeout đã gặp).
SELECT DISTINCT e.courseid AS course_id, ue.userid AS user_id
FROM mdl_user_enrolments ue
JOIN mdl_enrol e ON e.id = ue.enrolid AND e.status = 0
JOIN mdl_user u  ON u.id = ue.userid AND u.deleted = 0 AND u.suspended = 0
WHERE ue.status = 0
  AND ue.timestart <= :as_of
  AND (ue.timeend = 0 OR ue.timeend > :as_of)
  AND e.courseid <> 1
  AND e.courseid = ANY(CAST(:course_ids AS bigint[]))
  AND EXISTS (
        SELECT 1
        FROM mdl_context ctx
        JOIN mdl_role_assignments ra ON ra.contextid = ctx.id
        JOIN mdl_role r              ON r.id = ra.roleid AND r.shortname = 'student'
        WHERE ctx.contextlevel = 50
          AND ctx.instanceid = e.courseid
          AND ra.userid = ue.userid)
