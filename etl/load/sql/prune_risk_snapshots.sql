-- Bảo trì hằng tuần: với snapshot rủi ro cũ hơn :cutoff, chỉ giữ snapshot CUỐI mỗi tuần của từng (môn, SV)
DELETE FROM analytics.fact_student_risk_summary f
WHERE f.snapshot_date < :cutoff
  AND f.snapshot_date <> (
        SELECT MAX(x.snapshot_date)
        FROM analytics.fact_student_risk_summary x
        WHERE x.course_id = f.course_id
          AND x.user_id = f.user_id
          AND date_trunc('week', x.snapshot_date) = date_trunc('week', f.snapshot_date))
