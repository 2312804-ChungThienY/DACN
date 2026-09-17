-- Người dùng online tại :as_of: phiên có hoạt động trong :window giây gần nhất (SPEC 1.4)
SELECT COUNT(DISTINCT userid) AS online_users
FROM mdl_sessions
WHERE userid > 0
  AND timemodified >= CAST(:as_of AS bigint) - CAST(:window AS bigint)
  AND timemodified <= :as_of
