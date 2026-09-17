-- Số bài nộp trong ngày của :as_of theo môn (bài nộp nhóm tính 1 lần)
SELECT a.course AS course_id,
       COUNT(*) AS submissions_day
FROM mdl_assign_submission s
JOIN mdl_assign a          ON a.id = s.assignment
JOIN mdl_course_modules cm ON cm.instance = a.id AND cm.course = a.course
                          AND cm.visible = 1 AND cm.deletioninprogress = 0
JOIN mdl_modules m         ON m.id = cm.module AND m.name = 'assign'
WHERE a.course = ANY(CAST(:course_ids AS bigint[]))
  AND s.status = 'submitted'
  AND s.latest = 1
  AND s.timemodified >= :day_start
  AND s.timemodified <= :as_of
GROUP BY a.course
