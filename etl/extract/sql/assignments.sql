-- Tiêu chí 3 – bài tập (SPEC 1.6c), trả về MỖI (SV, bài tập) để tính tổng và chi tiết cho Modal.
-- Bài nộp hợp lệ: status = 'submitted', latest = 1, nộp trước :as_of.
-- Bài nộp nhóm (teamsubmission = 1): bản ghi userid = 0, groupid = nhóm của SV trong môn.
-- Việc "đã tới hạn" (duedate < :as_of) được xét ở bước Transform.
WITH student_enrol AS ({{student_enrol}}),
member_groups AS (
    SELECT g.courseid, gm.userid, gm.groupid
    FROM mdl_groups g
    JOIN mdl_groups_members gm ON gm.groupid = g.id
    WHERE g.courseid = ANY(CAST(:course_ids AS bigint[]))
)
SELECT a.course        AS course_id,
       se.user_id,
       a.id            AS assign_id,
       a.name          AS assign_name,
       a.duedate,
       sub.submitted_ts
FROM mdl_assign a
JOIN mdl_course_modules cm ON cm.instance = a.id AND cm.course = a.course
                          AND cm.visible = 1 AND cm.deletioninprogress = 0 AND cm.added <= :as_of
JOIN mdl_modules m         ON m.id = cm.module AND m.name = 'assign'
JOIN student_enrol se      ON se.course_id = a.course
LEFT JOIN LATERAL (
    SELECT MIN(s.timemodified) AS submitted_ts
    FROM mdl_assign_submission s
    WHERE s.assignment = a.id
      AND s.latest = 1
      AND s.status = 'submitted'
      AND s.timemodified <= :as_of
      AND (
            (a.teamsubmission = 0 AND s.userid = se.user_id)
         OR (a.teamsubmission = 1 AND s.userid = 0 AND s.groupid IN (
                SELECT mg.groupid FROM member_groups mg WHERE mg.courseid = a.course AND mg.userid = se.user_id))
      )
) sub ON TRUE
WHERE a.course = ANY(CAST(:course_ids AS bigint[]))
  AND a.duedate > 0
ORDER BY a.course, se.user_id, a.duedate, a.id
