-- Hoàn thành hoạt động theo chương/tuần của từng SV (SPEC 1.7).
-- Chỉ tính hoạt động bắt buộc (completion > 0) ĐÃ ĐẾN HẠN hoàn thành dự kiến tại :as_of
-- (completionexpected = 0 nghĩa là không đặt hạn -> luôn tính), để tỷ lệ giữa kỳ không bị kéo xuống
-- bởi các tuần chưa học.
WITH student_enrol AS ({{student_enrol}})
SELECT cm.course                                               AS course_id,
       se.user_id,
       cs.section                                              AS section_no,
       COALESCE(NULLIF(cs.name, ''), 'Tuần ' || cs.section)    AS section_name,
       COUNT(*)                                                AS tracked_activities,
       COUNT(cmc.id) FILTER (WHERE cmc.completionstate IN (1, 2)
                              AND cmc.timemodified <= :as_of)  AS completed_activities
FROM mdl_course_modules cm
JOIN mdl_course_sections cs  ON cs.id = cm.section
JOIN student_enrol se        ON se.course_id = cm.course
LEFT JOIN mdl_course_modules_completion cmc
                             ON cmc.coursemoduleid = cm.id AND cmc.userid = se.user_id
WHERE cm.course = ANY(CAST(:course_ids AS bigint[]))
  AND cm.completion > 0
  AND cm.visible = 1
  AND cm.deletioninprogress = 0
  AND cm.added <= :as_of
  AND (cm.completionexpected = 0 OR cm.completionexpected <= :as_of)
GROUP BY cm.course, se.user_id, cs.section, cs.name
ORDER BY 1, 2, 3
