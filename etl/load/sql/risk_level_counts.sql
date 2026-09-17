-- Phân bố đèn giao thông của mỗi môn từ snapshot rủi ro mới nhất không muộn hơn :stat_date
-- (giữ số liệu tiến độ môn khớp với bảng cảnh báo mà giảng viên đang xem)
SELECT r.course_id,
       COUNT(*) FILTER (WHERE r.risk_level = 'RED')    AS red_count,
       COUNT(*) FILTER (WHERE r.risk_level = 'YELLOW') AS yellow_count,
       COUNT(*) FILTER (WHERE r.risk_level = 'GREEN')  AS green_count
FROM analytics.fact_student_risk_summary r
JOIN (
    SELECT course_id, MAX(snapshot_date) AS snapshot_date
    FROM analytics.fact_student_risk_summary
    WHERE course_id = ANY(CAST(:course_ids AS integer[]))
      AND snapshot_date <= :stat_date
    GROUP BY course_id
) latest ON latest.course_id = r.course_id AND latest.snapshot_date = r.snapshot_date
GROUP BY r.course_id
