-- Môn học đang diễn ra trong ngày của :as_of, kèm chiều phi chuẩn hóa (SPEC 1.3, 1.6 "danh sách môn của GV")
-- Khoa = danh mục cấp 1 lấy từ path (/<khoa>/<bo_mon>); môn đặt thẳng trong Khoa thì khoa = chính danh mục đó.
SELECT c.id                AS course_id,
       c.shortname         AS course_shortname,
       c.fullname          AS course_fullname,
       c.startdate,
       c.enddate,
       cc.id               AS category_id,
       cc.name             AS category_name,
       fac.id              AS faculty_id,
       fac.name            AS faculty_name,
       COALESCE(t.teacher_ids, ARRAY[]::bigint[]) AS teacher_ids
FROM mdl_course c
JOIN mdl_course_categories cc  ON cc.id = c.category
JOIN mdl_course_categories fac ON fac.id = split_part(cc.path, '/', 2)::bigint
LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT ra.userid ORDER BY ra.userid) AS teacher_ids
    FROM mdl_context ctx
    JOIN mdl_role_assignments ra ON ra.contextid = ctx.id
    JOIN mdl_role r              ON r.id = ra.roleid AND r.shortname IN ('editingteacher', 'teacher')
    JOIN mdl_user u              ON u.id = ra.userid AND u.deleted = 0
    WHERE ctx.contextlevel = 50 AND ctx.instanceid = c.id
) t ON TRUE
WHERE c.id <> 1
  AND c.visible = 1
  AND c.startdate > 0
  AND c.startdate <= :as_of
  AND (c.enddate = 0 OR c.enddate >= :day_start)
ORDER BY c.id
