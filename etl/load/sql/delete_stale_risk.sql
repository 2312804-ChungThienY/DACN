-- Snapshot trong ngày được ghi đè: xóa SV không còn trong lần tính mới (vd đã hủy ghi danh từ lượt chạy trước)
DELETE FROM analytics.fact_student_risk_summary f
WHERE f.snapshot_date = :snapshot_date
  AND f.course_id = ANY(CAST(:course_ids AS integer[]))
  AND NOT EXISTS (
        SELECT 1 FROM tmp_fact_student_risk_summary t
        WHERE t.course_id = f.course_id AND t.user_id = f.user_id)
