# KẾ HOẠCH TRIỂN KHAI TOÀN DIỆN (END-TO-END ROADMAP)
## Đề tài: Trực quan hóa dữ liệu hệ thống LMS Moodle phục vụ công tác quản lý và hỗ trợ giảng dạy

> Đơn vị: Khoa Công nghệ Thông tin – Trường Đại học Đà Lạt
> Tài liệu gốc: `SPEC/yeu_cau_xay_dung_web_truc_quan_hoa_lms.pdf`
> Phiên bản: 1.0 – 14/09/2026
> Nguồn schema: Moodle 3.9 – https://moodleschema.zoola.io/

---

## 0. TÓM TẮT KIẾN TRÚC & QUYẾT ĐỊNH CÔNG NGHỆ

```
┌──────────────────────┐   Extract (read-only,     ┌──────────────────────────┐    SQL < 1s     ┌─────────────────┐   REST/JSON   ┌───────────────────────┐
│  Moodle 3.9 (PG/MySQL)│   incremental watermark)  │  ETL Python (pandas,     │ ──────────────▶ │ PostgreSQL       │ ────────────▶ │ FastAPI Backend       │
│  mdl_* (460+ bảng)    │ ────────────────────────▶ │  SQLAlchemy, APScheduler)│  UPSERT/COPY    │ Analytics DB     │               │ (JWT, RBAC, Export)   │
│  + mod_attendance     │                           │  Transform: risk rules   │                 │ 3 bảng fact +    │               └──────────┬────────────┘
└──────────────────────┘                           └──────────────────────────┘                 │ bảng phụ trợ     │                          │
          ▲                                                                                     └─────────────────┘                          ▼
          │ Mock data generator (Faker/pandas)                                                                                ┌───────────────────────┐
          └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────  │ React + Vite + Chart.js│
                                                                                                                              │ Ant Design (Admin/GV) │
                                                                                                                              └───────────────────────┘
```

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Nguồn dữ liệu | Moodle 3.9 chạy Docker (`bitnami/moodle:3.9` + PostgreSQL 13) + plugin **mod_attendance** | Có môi trường thật để sinh dữ liệu và kiểm chứng. Các bảng `mdl_attendance*` là **plugin**, không có sẵn trong core |
| CSDL phân tích | PostgreSQL 15 (container riêng, tách khỏi Moodle) | Có UPSERT, BRIN, GIN, index một phần (partial index), JSONB |
| ETL | Python 3.11: pandas, SQLAlchemy 2, psycopg2 (COPY), APScheduler (hoặc cron) | Đúng đề cương. Không cần hàng đợi nên không dùng Celery (bớt Redis) |
| Backend | **FastAPI** + Pydantic + SQLAlchemy Core, JWT (python-jose), openpyxl (Excel), WeasyPrint/ReportLab (PDF) | Tự sinh Swagger, chạy async, nhanh |
| Frontend | **React 18 + Vite**, **Chart.js 4** (react-chartjs-2), Ant Design 5 (Table, Modal, Select, DatePicker) | Chart.js khớp đề cương, hỗ trợ trục kép, cột chồng, doughnut. AntD có sẵn bảng và modal |
| Triển khai | Docker Compose, Nginx reverse proxy | Chạy demo bằng một lệnh |
| Kiểm thử | pytest, Locust/k6, Playwright, `EXPLAIN ANALYZE` | Kiểm tra dữ liệu đúng, hiệu năng dưới 1 giây, E2E |

**Đối chiếu tên bảng với PDF:**

| Tài liệu này | Tên trong PDF (mục 3.2) | Phục vụ |
|---|---|---|
| `fact_student_risk_summary` | `student_risk_analytics` | GV 2.1, 2.2 (so sánh cá nhân) |
| `fact_course_progress_daily` | `summary_course_enrollment` (mở rộng thêm chiều ngày) | Admin 1.1, 1.3, GV 2.2 |
| `fact_server_traffic_hourly` | `fact_daily_system_traffic` | Admin 1.2 |

---

## PHẦN 1: MAPPING DỮ LIỆU MOODLE GỐC

### 1.1 Các bảng Moodle gốc được sử dụng

| Bảng | Cột dùng | Ghi chú |
|---|---|---|
| `mdl_course_categories` | `id, name, parent, path, depth, idnumber` | **Khoa** là danh mục cấp 1 (`depth=1`). Lấy khoa của môn từ `path` (`/3/12` → khoa id 3) |
| `mdl_course` | `id, category, fullname, shortname, idnumber, startdate, enddate, visible` | Loại `id = 1` (site course) |
| `mdl_user` | `id, username, idnumber (MSSV), firstname, lastname, email, deleted, suspended, lastaccess` | Lọc `deleted=0 AND suspended=0` |
| `mdl_enrol` | `id, courseid, enrol, status` | `status=0` là phương thức ghi danh đang bật |
| `mdl_user_enrolments` | `enrolid, userid, status, timestart, timeend` | `status=0` là ghi danh đang hiệu lực |
| `mdl_context` | `id, contextlevel, instanceid` | 10 = system, 50 = course, 70 = module |
| `mdl_role_assignments` | `roleid, contextid, userid` | Xác định vai trò trong khóa học |
| `mdl_role` | `id, shortname` | `student`, `editingteacher`, `teacher` |
| `mdl_logstore_standard_log` | `id, eventname, component, action, target, crud, edulevel, contextid, contextlevel, contextinstanceid, userid, courseid, anonymous, timecreated, origin, ip` | Bảng lớn nhất, **trích xuất tăng dần theo `id`** |
| `mdl_user_lastaccess` | `userid, courseid, timeaccess` | Lần truy cập môn học gần nhất |
| `mdl_sessions` | `sid, userid, timecreated, timemodified, lastip` | Người dùng online: `timemodified` trong 5 phút gần nhất |
| `mdl_assign` | `id, course, name, duedate, cutoffdate, teamsubmission` | Bài tập |
| `mdl_assign_submission` | `assignment, userid, status, timemodified, latest, attemptnumber, groupid` | `status='submitted'`, `latest=1` |
| `mdl_course_modules` | `id, course, module, instance, section, visible, completion, deletioninprogress` | Hoạt động có theo dõi hoàn thành (`completion>0`) |
| `mdl_modules` | `id, name` | `name='assign'`, `'attendance'` |
| `mdl_course_modules_completion` | `coursemoduleid, userid, completionstate, timemodified` | `completionstate IN (1,2)` là đã hoàn thành |
| `mdl_course_sections` | `id, course, section, name` | Tiến độ theo chương/tuần |
| `mdl_attendance` *(plugin)* | `id, course, name` | Hoạt động điểm danh |
| `mdl_attendance_sessions` *(plugin)* | `id, attendanceid, groupid, sessdate, duration, lasttaken` | Buổi học. `lasttaken>0` là đã điểm danh |
| `mdl_attendance_statuses` *(plugin)* | `id, attendanceid, acronym, grade, deleted` | P = có mặt, L = trễ, E = có phép, A = vắng |
| `mdl_attendance_log` *(plugin)* | `sessionid, studentid, statusid, timetaken, takenby` | Kết quả điểm danh |
| `mdl_groups_members` | `groupid, userid` | Dùng khi buổi học gắn nhóm (`groupid<>0`) |

> **Quy ước:** Moodle lưu thời gian dạng `bigint` epoch (giây). Khi chuyển đổi, dùng `to_timestamp(x) AT TIME ZONE 'Asia/Ho_Chi_Minh'` trên PostgreSQL, hoặc `FROM_UNIXTIME(x)` trên MySQL.
> **Học kỳ / Năm học** (Moodle không có sẵn), suy ra từ `mdl_course.startdate`: tháng 8–12 là HK1 năm Y–(Y+1); tháng 1–5 là HK2 năm (Y-1)–Y; tháng 6–7 là HK3 (hè). Quy tắc này đặt trong `etl/config.py` để dễ đổi (hoặc đọc từ `mdl_course.idnumber`, ví dụ `CT101_HK1_2026`).

### 1.2 CTE dùng chung: sinh viên ghi danh hợp lệ (`student_enrol`)

```sql
WITH student_enrol AS (
  SELECT DISTINCT c.id AS courseid, u.id AS userid
  FROM mdl_course c
  JOIN mdl_enrol e            ON e.courseid = c.id AND e.status = 0
  JOIN mdl_user_enrolments ue ON ue.enrolid = e.id AND ue.status = 0
       AND (ue.timeend = 0 OR ue.timeend > EXTRACT(EPOCH FROM now()))
  JOIN mdl_context ctx        ON ctx.instanceid = c.id AND ctx.contextlevel = 50
  JOIN mdl_role_assignments ra ON ra.contextid = ctx.id AND ra.userid = ue.userid
  JOIN mdl_role r             ON r.id = ra.roleid AND r.shortname = 'student'
  JOIN mdl_user u             ON u.id = ue.userid AND u.deleted = 0 AND u.suspended = 0
  WHERE c.id <> 1
)
```

### 1.3 Admin 1.1 – Thống kê phân cấp Khoa → Môn → Sinh viên

| Chỉ số | Bảng | JOIN / WHERE | Tổng hợp |
|---|---|---|---|
| Khoa | `mdl_course_categories` | `split_part(cc.path,'/',2)::int = khoa.id` | – |
| SV đăng ký | `student_enrol` | theo `courseid` | `COUNT(DISTINCT userid)` |
| SV có tương tác | `mdl_logstore_standard_log` ⋈ `student_enrol` | `l.anonymous=0 AND l.timecreated BETWEEN c.startdate AND COALESCE(NULLIF(c.enddate,0), now)` | `COUNT(DISTINCT l.userid)` |
| Tỷ lệ tương tác | – | – | `active / NULLIF(enrolled,0)` |
| Giảng viên | `mdl_role_assignments` ⋈ `mdl_role` | `shortname IN ('editingteacher','teacher')` | `array_agg(DISTINCT userid)` |

```sql
-- (dùng CTE student_enrol ở trên)
, active AS (
  SELECT l.courseid, COUNT(DISTINCT l.userid) AS active_students
  FROM mdl_logstore_standard_log l
  JOIN student_enrol se ON se.courseid = l.courseid AND se.userid = l.userid
  JOIN mdl_course c ON c.id = l.courseid
  WHERE l.anonymous = 0
    AND l.timecreated >= c.startdate
    AND l.timecreated <  COALESCE(NULLIF(c.enddate,0), EXTRACT(EPOCH FROM now())::bigint)
  GROUP BY l.courseid
)
SELECT fac.id AS faculty_id, fac.name AS faculty_name,
       c.id AS course_id, c.shortname, c.fullname, c.startdate,
       COUNT(DISTINCT se.userid)            AS total_enrolled_students,
       COALESCE(MAX(a.active_students), 0)  AS total_active_students
FROM mdl_course c
JOIN mdl_course_categories cc  ON cc.id = c.category
JOIN mdl_course_categories fac ON fac.id = split_part(cc.path, '/', 2)::int
LEFT JOIN student_enrol se ON se.courseid = c.id
LEFT JOIN active a         ON a.courseid = c.id
WHERE c.id <> 1 AND c.visible = 1
GROUP BY fac.id, fac.name, c.id, c.shortname, c.fullname, c.startdate;
```

### 1.4 Admin 1.2 – Lưu lượng & người truy cập

| Chỉ số | Bảng | WHERE | Tổng hợp |
|---|---|---|---|
| Tổng request/giờ *(proxy)* | `mdl_logstore_standard_log` | `timecreated` trong khung giờ | `COUNT(*)` nhóm theo `date_trunc('hour')` |
| User hoạt động/giờ | như trên | `userid > 0` | `COUNT(DISTINCT userid)` |
| Đăng nhập / đăng nhập lỗi | như trên | `eventname = '\core\event\user_loggedin'` / `'\core\event\user_login_failed'` | `COUNT(*) FILTER` |
| User online (thời gian thực) | `mdl_sessions` | `userid>0 AND timemodified >= now-300` | `COUNT(DISTINCT userid)`, chụp mỗi 5 phút |

> **Hạn chế cần nêu trong báo cáo:** logstore ghi **sự kiện nghiệp vụ**, không phải HTTP request. Số liệu này là chỉ số gần đúng. Nếu cần request thật, đọc thêm access log của Nginx/Apache (phần mở rộng, không bắt buộc).

```sql
SELECT date_trunc('hour', to_timestamp(l.timecreated) AT TIME ZONE 'Asia/Ho_Chi_Minh') AS stat_hour,
       COUNT(*)                                                          AS total_requests,
       COUNT(DISTINCT l.userid) FILTER (WHERE l.userid > 0)              AS unique_users,
       COUNT(*) FILTER (WHERE l.eventname = '\core\event\user_loggedin')     AS login_count,
       COUNT(*) FILTER (WHERE l.eventname = '\core\event\user_login_failed') AS failed_login_count,
       COUNT(*) FILTER (WHERE l.origin = 'ws')                           AS ws_requests
FROM mdl_logstore_standard_log l
WHERE l.id > :last_log_id AND l.id <= :max_log_id        -- incremental
GROUP BY 1;

-- Snapshot online users (mỗi 5 phút)
SELECT COUNT(DISTINCT userid) AS online_users
FROM mdl_sessions
WHERE userid > 0 AND timemodified >= EXTRACT(EPOCH FROM now())::bigint - 300;
```

### 1.5 Admin 1.3 – Xuất báo cáo
Không đọc Moodle trực tiếp. Dữ liệu lấy từ 3 bảng fact, lọc theo `faculty_id, academic_year, semester, course_id, risk_level, khoảng ngày`.

### 1.6 GV 2.1 – Cảnh báo sinh viên nguy cơ (3 tiêu chí)

**(a) Tiêu chí 1: Vắng học / không điểm danh**

| Bảng | JOIN | WHERE | Tổng hợp |
|---|---|---|---|
| `mdl_attendance` ⋈ `mdl_attendance_sessions` ⋈ `student_enrol` ⟕ `mdl_attendance_log` ⟕ `mdl_attendance_statuses` | `al.sessionid=s.id AND al.studentid=se.userid` | `s.lasttaken > 0 AND s.sessdate < now`; nếu `s.groupid<>0` thì SV phải thuộc nhóm | `total_sessions = COUNT(s.id)`; `absent = COUNT(*) FILTER (WHERE al.id IS NULL OR st.acronym='A')`; `absence_rate = absent/total` |

```sql
SELECT a.course AS courseid, se.userid,
       COUNT(s.id)                                                     AS total_sessions,
       COUNT(al.id) FILTER (WHERE st.acronym IN ('P','L','E'))         AS attended_sessions,
       COUNT(s.id)  FILTER (WHERE al.id IS NULL OR st.acronym = 'A')   AS absent_sessions,
       MAX(s.sessdate) FILTER (WHERE st.acronym IN ('P','L'))          AS last_attended
FROM mdl_attendance a
JOIN mdl_attendance_sessions s ON s.attendanceid = a.id
     AND s.lasttaken > 0 AND s.sessdate < EXTRACT(EPOCH FROM now())
JOIN student_enrol se ON se.courseid = a.course
LEFT JOIN mdl_groups_members gm ON gm.groupid = s.groupid AND gm.userid = se.userid
LEFT JOIN mdl_attendance_log al ON al.sessionid = s.id AND al.studentid = se.userid
LEFT JOIN mdl_attendance_statuses st ON st.id = al.statusid
WHERE s.groupid = 0 OR gm.id IS NOT NULL
GROUP BY a.course, se.userid;
```

**(b) Tiêu chí 2: Không đăng nhập / không tương tác môn học**

| Bảng | WHERE | Tổng hợp |
|---|---|---|
| `mdl_user_lastaccess` | `courseid=:c` | `timeaccess` → `days_since_last_access` (NULL nghĩa là chưa từng vào) |
| `mdl_logstore_standard_log` | `courseid=:c AND userid=:u AND anonymous=0` | `total_access_count = COUNT(*)`; `access_count_7d`, `access_count_14d` dùng `FILTER (WHERE timecreated >= now-7d)` |
| `mdl_logstore_standard_log` | thêm `crud IN ('c','u')` | `active_actions` (nộp bài, đăng diễn đàn...) |

```sql
SELECT se.courseid, se.userid,
       ula.timeaccess                                                        AS last_access,
       COUNT(l.id)                                                           AS total_access_count,
       COUNT(l.id) FILTER (WHERE l.timecreated >= EXTRACT(EPOCH FROM now() - interval '7 days'))  AS access_count_7d,
       COUNT(l.id) FILTER (WHERE l.timecreated >= EXTRACT(EPOCH FROM now() - interval '14 days')) AS access_count_14d,
       COUNT(l.id) FILTER (WHERE l.crud IN ('c','u'))                        AS active_actions
FROM student_enrol se
LEFT JOIN mdl_user_lastaccess ula ON ula.courseid = se.courseid AND ula.userid = se.userid
LEFT JOIN mdl_logstore_standard_log l ON l.courseid = se.courseid AND l.userid = se.userid AND l.anonymous = 0
GROUP BY se.courseid, se.userid, ula.timeaccess;
```

**(c) Tiêu chí 3: Nộp thiếu bài tập**

| Bảng | JOIN | WHERE | Tổng hợp |
|---|---|---|---|
| `mdl_assign` ⋈ `mdl_course_modules` ⋈ `mdl_modules` ⋈ `student_enrol` ⟕ `mdl_assign_submission` | `s.assignment=a.id AND s.userid=se.userid AND s.latest=1` | `m.name='assign' AND cm.visible=1 AND cm.deletioninprogress=0 AND a.duedate>0 AND a.duedate<now` | `total_due = COUNT(a.id)`; `submitted = COUNT(*) FILTER (WHERE s.status='submitted')`; `missing = total_due − submitted`; `late = FILTER (s.timemodified > a.duedate)` |

```sql
SELECT a.course AS courseid, se.userid,
       COUNT(a.id)                                                              AS total_assignments_due,
       COUNT(s.id) FILTER (WHERE s.status = 'submitted')                        AS submitted_assignments,
       COUNT(a.id) - COUNT(s.id) FILTER (WHERE s.status = 'submitted')          AS missing_assignments_count,
       COUNT(s.id) FILTER (WHERE s.status = 'submitted' AND s.timemodified > a.duedate) AS late_submissions
FROM mdl_assign a
JOIN mdl_course_modules cm ON cm.instance = a.id AND cm.course = a.course
     AND cm.visible = 1 AND cm.deletioninprogress = 0
JOIN mdl_modules m ON m.id = cm.module AND m.name = 'assign'
JOIN student_enrol se ON se.courseid = a.course
LEFT JOIN mdl_assign_submission s ON s.assignment = a.id AND s.userid = se.userid AND s.latest = 1
WHERE a.duedate > 0 AND a.duedate < EXTRACT(EPOCH FROM now())
GROUP BY a.course, se.userid;
-- Bài nộp theo nhóm (teamsubmission=1): submission có userid=0, groupid=nhóm → JOIN thêm mdl_groups_members.
```

**Danh sách môn của giảng viên** (phân quyền dữ liệu):
```sql
SELECT ctx.instanceid AS courseid, ra.userid AS teacher_id
FROM mdl_role_assignments ra
JOIN mdl_role r    ON r.id = ra.roleid AND r.shortname IN ('editingteacher','teacher')
JOIN mdl_context ctx ON ctx.id = ra.contextid AND ctx.contextlevel = 50;
```

### 1.7 GV 2.2 – Tiến độ & tương tác lớp

| Chỉ số | Bảng | JOIN / WHERE | Tổng hợp |
|---|---|---|---|
| Tỷ lệ hoàn thành hoạt động bắt buộc | `mdl_course_modules` ⋈ `student_enrol` ⟕ `mdl_course_modules_completion` | `cm.completion>0 AND cm.visible=1`; `cmc.completionstate IN (1,2)` | `completed / (số hoạt động × số SV)` |
| Tiến độ theo chương/tuần | thêm `mdl_course_sections` | `cm.section = cs.id` | `GROUP BY cs.section` → JSONB |
| Tương tác cá nhân so với trung bình lớp | kết quả 1.6(b) | – | `AVG(total_access_count) OVER (PARTITION BY courseid)` |
| Tỷ lệ nộp bài, chuyên cần của lớp | kết quả 1.6(a), (c) | – | `SUM(submitted)/SUM(total_due)`, `SUM(attended)/SUM(total_sessions)` |

```sql
SELECT cm.course AS courseid, cs.section AS section_no, COALESCE(cs.name, 'Tuần ' || cs.section) AS section_name,
       COUNT(DISTINCT cm.id)                                                       AS tracked_activities,
       COUNT(cmc.id) FILTER (WHERE cmc.completionstate IN (1,2))                   AS completed_marks,
       COUNT(DISTINCT se.userid)                                                   AS students
FROM mdl_course_modules cm
JOIN mdl_course_sections cs ON cs.id = cm.section
JOIN student_enrol se ON se.courseid = cm.course
LEFT JOIN mdl_course_modules_completion cmc ON cmc.coursemoduleid = cm.id AND cmc.userid = se.userid
WHERE cm.completion > 0 AND cm.visible = 1 AND cm.deletioninprogress = 0
GROUP BY cm.course, cs.section, cs.name;
-- completion_rate = completed_marks / (tracked_activities * students)
```

---

## PHẦN 2: THIẾT KẾ CSDL GỘP POSTGRESQL (3 BẢNG ETL)

### 2.1 Nguyên tắc
- **Phi chuẩn hóa (denormalized):** tên khoa, tên môn, MSSV, họ tên được ghi thẳng vào bảng fact để API **không phải JOIN**.
- **Phân quyền ngay trong dữ liệu:** cột `teacher_ids INT[]` có GIN index. API giảng viên luôn lọc `:uid = ANY(teacher_ids)`.
- Toàn bộ ghi dữ liệu dùng **UPSERT** (`INSERT ... ON CONFLICT DO UPDATE`), nên chạy lại ETL không sinh bản ghi trùng (idempotent).
- Khóa ngoại: 3 bảng fact **không có FK vật lý tới Moodle** (hai CSDL khác nhau). Chỉ có FK logic tới bảng phụ trợ `etl_run_log` qua `etl_run_id`.
- Có thêm **bảng phụ trợ** (không phải fact): `etl_watermark`, `etl_run_log`, `app_user`, `intervention_log`.

### 2.2 DDL đầy đủ (`sql/analytics_schema.sql`)

```sql
CREATE SCHEMA IF NOT EXISTS analytics;
SET search_path = analytics;

-- ============ BẢNG PHỤ TRỢ ============
CREATE TABLE etl_run_log (
  run_id        BIGSERIAL PRIMARY KEY,
  job_name      VARCHAR(50)  NOT NULL,          -- traffic | course_progress | student_risk
  started_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  status        VARCHAR(10)  NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','SUCCESS','FAILED')),
  rows_extracted INT, rows_loaded INT,
  error_message TEXT
);
CREATE INDEX ix_etl_run_job_time ON etl_run_log (job_name, started_at DESC);

CREATE TABLE etl_watermark (
  job_name     VARCHAR(50) PRIMARY KEY,
  last_log_id  BIGINT      NOT NULL DEFAULT 0,  -- mdl_logstore_standard_log.id đã xử lý
  last_run_at  TIMESTAMPTZ
);

CREATE TABLE app_user (
  user_id       INT PRIMARY KEY,                -- = mdl_user.id
  username      VARCHAR(100) UNIQUE NOT NULL,
  full_name     VARCHAR(255),
  email         VARCHAR(255),
  role          VARCHAR(10) NOT NULL CHECK (role IN ('ADMIN','TEACHER')),
  password_hash VARCHAR(255) NOT NULL,          -- bcrypt
  is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============ FACT 1: CẢNH BÁO SINH VIÊN ============
CREATE TABLE fact_student_risk_summary (
  snapshot_date             DATE         NOT NULL,
  course_id                 INT          NOT NULL,
  user_id                   INT          NOT NULL,
  -- chiều phi chuẩn hóa
  faculty_id                INT          NOT NULL,
  faculty_name              VARCHAR(255) NOT NULL,
  course_shortname          VARCHAR(255) NOT NULL,
  course_fullname           VARCHAR(255) NOT NULL,
  academic_year             VARCHAR(9)   NOT NULL,   -- '2026-2027'
  semester                  SMALLINT     NOT NULL CHECK (semester IN (1,2,3)),
  teacher_ids               INT[]        NOT NULL DEFAULT '{}',
  student_code              VARCHAR(100),            -- mdl_user.idnumber
  student_name              VARCHAR(255) NOT NULL,
  email                     VARCHAR(255),
  -- tiêu chí 2: tương tác
  total_access_count        INT          NOT NULL DEFAULT 0,
  access_count_7d           INT          NOT NULL DEFAULT 0,
  access_count_14d          INT          NOT NULL DEFAULT 0,
  active_actions            INT          NOT NULL DEFAULT 0,
  last_access_time          TIMESTAMPTZ,
  days_since_last_access    INT,                     -- NULL = chưa từng truy cập
  -- tiêu chí 1: điểm danh
  total_sessions            SMALLINT     NOT NULL DEFAULT 0,
  attended_sessions         SMALLINT     NOT NULL DEFAULT 0,
  absent_sessions           SMALLINT     NOT NULL DEFAULT 0,
  absence_rate              NUMERIC(5,2) NOT NULL DEFAULT 0,   -- %
  attendance_status         VARCHAR(10)  NOT NULL DEFAULT 'OK' CHECK (attendance_status IN ('OK','WARN','CRITICAL','NO_DATA')),
  -- tiêu chí 3: bài tập
  total_assignments         SMALLINT     NOT NULL DEFAULT 0,   -- đã tới hạn
  submitted_assignments     SMALLINT     NOT NULL DEFAULT 0,
  missing_assignments_count SMALLINT     NOT NULL DEFAULT 0,
  late_submissions          SMALLINT     NOT NULL DEFAULT 0,
  completion_rate           NUMERIC(5,2) NOT NULL DEFAULT 0,   -- % hoạt động hoàn thành
  -- kết quả đánh giá
  score_attendance          SMALLINT     NOT NULL DEFAULT 0 CHECK (score_attendance BETWEEN 0 AND 2),
  score_inactivity          SMALLINT     NOT NULL DEFAULT 0 CHECK (score_inactivity BETWEEN 0 AND 2),
  score_assignment          SMALLINT     NOT NULL DEFAULT 0 CHECK (score_assignment BETWEEN 0 AND 2),
  risk_score                SMALLINT     NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
  risk_level                VARCHAR(6)   NOT NULL CHECK (risk_level IN ('RED','YELLOW','GREEN')),
  risk_reasons              JSONB        NOT NULL DEFAULT '[]',  -- ["Vắng 5/12 buổi (41.7%)", ...]
  -- dữ liệu cho Modal chi tiết (tránh truy vấn Moodle)
  weekly_activity           JSONB        NOT NULL DEFAULT '[]',  -- [{"week":1,"views":12,"actions":2,"attended":true}]
  assignment_detail         JSONB        NOT NULL DEFAULT '[]',  -- [{"name":"BT1","duedate":"...","status":"submitted","late":false}]
  class_avg_access          NUMERIC(8,2),                        -- trung bình lớp (so sánh)
  etl_run_id                BIGINT REFERENCES etl_run_log(run_id),
  updated_at                TIMESTAMPTZ  NOT NULL DEFAULT now(),
  PRIMARY KEY (course_id, user_id, snapshot_date)
);
-- Bảng đèn giao thông của GV: lọc course + ngày mới nhất + mức rủi ro, sắp xếp theo điểm
CREATE INDEX ix_risk_course_date_level ON fact_student_risk_summary (course_id, snapshot_date DESC, risk_level, risk_score DESC);
CREATE INDEX ix_risk_teacher_gin       ON fact_student_risk_summary USING GIN (teacher_ids);
CREATE INDEX ix_risk_user              ON fact_student_risk_summary (user_id, snapshot_date DESC);
CREATE INDEX ix_risk_faculty_term      ON fact_student_risk_summary (faculty_id, academic_year, semester, snapshot_date);
CREATE INDEX ix_risk_red_partial       ON fact_student_risk_summary (course_id, snapshot_date) WHERE risk_level = 'RED';

-- View "bản mới nhất" dùng cho API
CREATE VIEW v_student_risk_latest AS
SELECT DISTINCT ON (course_id, user_id) *
FROM fact_student_risk_summary
ORDER BY course_id, user_id, snapshot_date DESC;

-- ============ FACT 2: TIẾN ĐỘ MÔN HỌC THEO NGÀY ============
CREATE TABLE fact_course_progress_daily (
  stat_date                  DATE         NOT NULL,
  course_id                  INT          NOT NULL,
  faculty_id                 INT          NOT NULL,
  faculty_name               VARCHAR(255) NOT NULL,
  category_id                INT          NOT NULL,
  category_name              VARCHAR(255) NOT NULL,
  course_shortname           VARCHAR(255) NOT NULL,
  course_fullname            VARCHAR(255) NOT NULL,
  academic_year              VARCHAR(9)   NOT NULL,
  semester                   SMALLINT     NOT NULL,
  teacher_ids                INT[]        NOT NULL DEFAULT '{}',
  total_enrolled_students    INT          NOT NULL DEFAULT 0,
  active_students_day        INT          NOT NULL DEFAULT 0,   -- có log trong ngày
  active_students_7d         INT          NOT NULL DEFAULT 0,
  total_active_students      INT          NOT NULL DEFAULT 0,   -- lũy kế từ đầu học kỳ (Admin 1.1)
  total_views_day            INT          NOT NULL DEFAULT 0,
  total_actions_day          INT          NOT NULL DEFAULT 0,   -- crud c/u
  submissions_day            INT          NOT NULL DEFAULT 0,
  total_assignments          SMALLINT     NOT NULL DEFAULT 0,
  assignment_submission_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
  attendance_rate            NUMERIC(5,2) NOT NULL DEFAULT 0,
  avg_completion_rate        NUMERIC(5,2) NOT NULL DEFAULT 0,
  avg_access_per_student     NUMERIC(8,2) NOT NULL DEFAULT 0,
  red_count                  INT          NOT NULL DEFAULT 0,
  yellow_count               INT          NOT NULL DEFAULT 0,
  green_count                INT          NOT NULL DEFAULT 0,
  section_progress           JSONB        NOT NULL DEFAULT '[]', -- [{"section":1,"name":"Chương 1","completion_rate":82.5}]
  etl_run_id                 BIGINT REFERENCES etl_run_log(run_id),
  updated_at                 TIMESTAMPTZ  NOT NULL DEFAULT now(),
  PRIMARY KEY (course_id, stat_date)
);
CREATE INDEX ix_cpd_term_faculty ON fact_course_progress_daily (academic_year, semester, faculty_id, stat_date DESC);
CREATE INDEX ix_cpd_date_brin    ON fact_course_progress_daily USING BRIN (stat_date);
CREATE INDEX ix_cpd_teacher_gin  ON fact_course_progress_daily USING GIN (teacher_ids);

-- ============ FACT 3: LƯU LƯỢNG SERVER THEO GIỜ ============
CREATE TABLE fact_server_traffic_hourly (
  stat_hour           TIMESTAMP    NOT NULL PRIMARY KEY,    -- giờ địa phương Asia/Ho_Chi_Minh, đã cắt về đầu giờ
  stat_date           DATE         NOT NULL,
  hour_of_day         SMALLINT     NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
  day_of_week         SMALLINT     NOT NULL CHECK (day_of_week BETWEEN 1 AND 7), -- ISO
  total_requests      INT          NOT NULL DEFAULT 0,
  unique_users        INT          NOT NULL DEFAULT 0,
  login_count         INT          NOT NULL DEFAULT 0,
  failed_login_count  INT          NOT NULL DEFAULT 0,
  ws_requests         INT          NOT NULL DEFAULT 0,
  peak_online_users   INT          NOT NULL DEFAULT 0,       -- MAX các snapshot 5 phút
  avg_online_users    NUMERIC(8,2) NOT NULL DEFAULT 0,
  online_sample_count SMALLINT     NOT NULL DEFAULT 0,       -- dùng cập nhật trung bình cộng dồn
  is_peak_hour        BOOLEAN      NOT NULL DEFAULT FALSE,   -- requests > P90 của 28 ngày
  etl_run_id          BIGINT REFERENCES etl_run_log(run_id),
  updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_traffic_date_hour ON fact_server_traffic_hourly (stat_date, hour_of_day);
CREATE INDEX ix_traffic_brin      ON fact_server_traffic_hourly USING BRIN (stat_hour);

-- ============ NHẬT KÝ CAN THIỆP (nút hành động GV) ============
CREATE TABLE intervention_log (
  id           BIGSERIAL PRIMARY KEY,
  course_id    INT NOT NULL,
  user_id      INT NOT NULL,
  teacher_id   INT NOT NULL REFERENCES app_user(user_id),
  action_type  VARCHAR(20) NOT NULL CHECK (action_type IN ('MESSAGE','EMAIL','NOTE','MEETING')),
  content      TEXT,
  risk_level_at_time VARCHAR(6),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_intervention_course_user ON intervention_log (course_id, user_id, created_at DESC);
```

### 2.3 Quy tắc chấm điểm rủi ro (Transform)

| Tiêu chí | 0 điểm (Xanh) | 1 điểm (Vàng) | 2 điểm (Đỏ) |
|---|---|---|---|
| **C1 Vắng học** (`absence_rate`) | < 15% | 15% – < 30% | ≥ 30% *(ví dụ vắng ≥ 3/10 buổi)* |
| **C2 Không tương tác** | truy cập trong 7 ngày và `access_count_14d` ≥ 50% trung vị lớp | 7–14 ngày chưa vào **hoặc** `access_count_14d` < 50% trung vị lớp | chưa từng vào môn **hoặc** > 14 ngày không truy cập |
| **C3 Thiếu bài tập** (`missing/total_due`) | < 20% | 20% – < 60% | ≥ 60% *(tương đương bỏ ≥ 3/5 bài)* |

- `risk_score = round(100 × (0.35·C1 + 0.35·C3 + 0.30·C2) / 2)`
- **RED**: có ít nhất một tiêu chí = 2 **hoặc** tổng ≥ 3 · **YELLOW**: tổng ≥ 1 · **GREEN**: tổng = 0
- Khi chưa có dữ liệu (0 buổi điểm danh hoặc 0 bài tới hạn), tiêu chí đó = 0 và `attendance_status='NO_DATA'`.
- Mọi ngưỡng đặt trong `etl/config.py` (`RISK_THRESHOLDS`) để có thể tinh chỉnh khi họp với giảng viên.

```python
# etl/transform/risk_rules.py
def score_student(r: dict, class_median_14d: float, cfg=RISK_THRESHOLDS) -> dict:
    reasons = []
    # C1
    c1 = 0
    if r["total_sessions"] > 0:
        rate = r["absent_sessions"] / r["total_sessions"]
        c1 = 2 if rate >= cfg["absence_red"] else 1 if rate >= cfg["absence_yellow"] else 0
        if c1: reasons.append(f"Vắng {r['absent_sessions']}/{r['total_sessions']} buổi ({rate:.0%})")
    # C2
    d = r["days_since_last_access"]
    low = class_median_14d > 0 and r["access_count_14d"] < cfg["low_access_ratio"] * class_median_14d
    c2 = 2 if d is None or d > cfg["inactive_red_days"] else 1 if d > cfg["inactive_yellow_days"] or low else 0
    if d is None: reasons.append("Chưa từng truy cập môn học")
    elif c2: reasons.append(f"{d} ngày chưa truy cập" if d > cfg["inactive_yellow_days"] else "Tương tác thấp hơn 50% trung vị lớp")
    # C3
    c3 = 0
    if r["total_assignments"] > 0:
        miss = r["missing_assignments_count"] / r["total_assignments"]
        c3 = 2 if miss >= cfg["missing_red"] else 1 if miss >= cfg["missing_yellow"] else 0
        if c3: reasons.append(f"Thiếu {r['missing_assignments_count']}/{r['total_assignments']} bài tập")
    total = c1 + c2 + c3
    level = "RED" if 2 in (c1, c2, c3) or total >= 3 else "YELLOW" if total >= 1 else "GREEN"
    score = round(100 * (0.35 * c1 + 0.30 * c2 + 0.35 * c3) / 2)
    return dict(score_attendance=c1, score_inactivity=c2, score_assignment=c3,
                risk_score=score, risk_level=level, risk_reasons=reasons)

RISK_THRESHOLDS = dict(absence_yellow=0.15, absence_red=0.30, inactive_yellow_days=7,
                       inactive_red_days=14, low_access_ratio=0.5, missing_yellow=0.20, missing_red=0.60)
```

### 2.4 Truy vấn mẫu của Dashboard (mục tiêu < 100 ms)
```sql
-- Bảng đèn giao thông (GV)
SELECT user_id, student_code, student_name, risk_level, risk_score, risk_reasons,
       absence_rate, missing_assignments_count, total_assignments, days_since_last_access
FROM analytics.v_student_risk_latest
WHERE course_id = :course_id AND :teacher_id = ANY(teacher_ids)
ORDER BY CASE risk_level WHEN 'RED' THEN 0 WHEN 'YELLOW' THEN 1 ELSE 2 END, risk_score DESC
LIMIT 50 OFFSET :offset;

-- Stacked bar theo khoa (Admin)
SELECT faculty_id, faculty_name, SUM(total_enrolled_students) enrolled, SUM(total_active_students) active
FROM analytics.fact_course_progress_daily
WHERE academic_year = :ay AND semester = :sem
  AND stat_date = (SELECT MAX(stat_date) FROM analytics.fact_course_progress_daily WHERE academic_year=:ay AND semester=:sem)
GROUP BY faculty_id, faculty_name ORDER BY enrolled DESC;
```
> Nếu `DISTINCT ON` chậm khi dữ liệu lớn, chuyển `v_student_risk_latest` thành **MATERIALIZED VIEW** và `REFRESH ... CONCURRENTLY` ở cuối job risk (cần UNIQUE INDEX `(course_id, user_id)`).

---

## PHẦN 3: KẾ HOẠCH SINH DỮ LIỆU GIẢ LẬP

### 3.1 Gap Analysis

| Dữ liệu cần | Moodle mặc định/cài mới | Thiếu gì | Cách bổ sung |
|---|---|---|---|
| Cây Khoa → Môn | Không có | Toàn bộ | Python seed `mdl_course_categories` hoặc CLI `admin/cli` + `tool_generator` |
| Người dùng, ghi danh, vai trò | Chỉ có admin | 2.000 SV, 40 GV | `admin/tool/generator/cli/maketestcourse.php` (size M) + Python seed tên tiếng Việt (Faker `vi_VN`) |
| Log truy cập | Rất ít | Hành vi theo 15 tuần, giờ cao điểm, nhóm rủi ro | **Python** chèn `mdl_logstore_standard_log`, `mdl_user_lastaccess` |
| Điểm danh | **Không có** (plugin) | Plugin, buổi học, trạng thái, log | Cài `mod_attendance` (bản cho 3.9), Python tạo sessions/logs |
| Bài tập & bài nộp | Không có | ≥ 5 bài/môn, SV bỏ bài | Python chèn `mdl_assign`, `mdl_course_modules`, `mdl_context`, `mdl_assign_submission` |
| Hoàn thành hoạt động | Tắt | `enablecompletion`, dữ liệu completion | Bật `enablecompletion=1`, chèn `mdl_course_modules_completion` |
| Sessions online | Không có | Snapshot đồng thời | Script chèn/cập nhật `mdl_sessions` mỗi 5 phút (chế độ "live") |
| Ca biên | – | SV chưa từng vào, SV hủy ghi danh, bài nộp nhóm, môn chưa có buổi điểm danh | Bổ sung chủ động (~2% mỗi loại) |

### 3.2 Quy mô & quy tắc phân bổ

| Tham số | Giá trị |
|---|---|
| Khoa (category cấp 1) | 5 (CNTT, Kinh tế, Ngoại ngữ, Sinh học, Luật) |
| Môn học | 40 (8/khoa), HK1 2026-2027, bắt đầu 07/09/2026, dài 15 tuần |
| Sinh viên / GV | 2.000 / 40; mỗi SV học 4–6 môn → ~10.000 ghi danh |
| Bài tập | 5–8 bài/môn, hạn nộp rải đều tuần 3–14 |
| Buổi điểm danh | 1–2 buổi/tuần/môn → 15–30 buổi |
| Log dự kiến | 2–3 triệu dòng (đủ để đo hiệu năng); bản stress x10 = 25 triệu |

**Hồ sơ hành vi** (gán cho mỗi cặp SV–môn, 80% giữ theo hồ sơ chung của SV để có tính nhất quán):

| Hồ sơ | Tỷ lệ | Phiên/tuần | Xác suất điểm danh có mặt | Xác suất nộp bài | Đặc biệt |
|---|---|---|---|---|---|
| GREEN | 65% | 4–9 | 0.95 | 0.95 | trễ hạn 5% |
| YELLOW | 20% | 1–4 | 0.80 | 0.70 | trễ hạn 25% |
| RED | **15%** | 0–1 | 0.50 | 0.30 | 35% trong nhóm **chưa từng truy cập**; đảm bảo thiếu ≥ 3/5 bài; 30% "bỏ dần" (hoạt động giảm sau tuần 6) |

**Phân bổ thời gian:**
- Trọng số giờ (GMT+7): cao điểm **08–10h** và **14–16h** (hệ số 3.0–3.2), tối 20–22h (1.6–1.8), 0–5h (0.1–0.3).
- Thứ 2–6 hệ số 1.0; Thứ 7 0.5; Chủ nhật 0.4.
- Tăng đột biến: 48 giờ trước hạn nộp bài (×2.5 cho môn đó); tuần thi giữa kỳ (tuần 8) ×1.5.

### 3.3 Mã Python mẫu (`mockdata/generate_activity.py`)

```python
"""
Sinh dữ liệu hành vi giả lập cho Moodle 3.9 (PostgreSQL, prefix mdl_).
Tiền điều kiện: đã có categories/courses/users/enrolments (seed_structure.py hoặc tool_generator),
đã cài mod_attendance và tạo sẵn mdl_assign + mdl_attendance_sessions cho mỗi môn.
pip install faker pandas numpy sqlalchemy psycopg2-binary
"""
import io, os, random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import create_engine, text

DB_URL = os.getenv("MOODLE_DB_URL", "postgresql+psycopg2://moodle:moodle@localhost:5433/moodle")
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SEM_START = datetime(2026, 9, 7, tzinfo=TZ)
WEEKS = 15
MOCK_IP_PREFIX = "10.99."          # dấu hiệu để xóa dữ liệu giả lập khi cần
rng = np.random.default_rng(2026); random.seed(2026); fake = Faker("vi_VN")

PROFILES = {"GREEN": 0.65, "YELLOW": 0.20, "RED": 0.15}
BEHAVIOR = {
    "GREEN":  dict(sess=(4, 9), attend=0.95, submit=0.95, late=0.05, never=0.00, dropout=0.00),
    "YELLOW": dict(sess=(1, 4), attend=0.80, submit=0.70, late=0.25, never=0.00, dropout=0.10),
    "RED":    dict(sess=(0, 1), attend=0.50, submit=0.30, late=0.40, never=0.35, dropout=0.30),
}
HOUR_W = np.array([.3,.2,.1,.1,.1,.2,.6,1.5,3.0,3.2,3.0,2.0,1.0,1.5,3.0,3.2,2.8,1.8,1.2,1.4,1.8,1.6,1.0,.6])
HOUR_P = HOUR_W / HOUR_W.sum()
DOW_W = [1, 1, 1, 1, 1, .5, .4]

engine = create_engine(DB_URL)

def q(sql, **kw) -> pd.DataFrame:
    with engine.connect() as c:
        return pd.read_sql(text(sql), c, params=kw)

def copy_df(df: pd.DataFrame, table: str):
    """Bulk insert bằng COPY (nhanh hơn to_sql ~20 lần)."""
    buf = io.StringIO(); df.to_csv(buf, index=False, header=False, na_rep=""); buf.seek(0)
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.copy_expert(f"COPY {table} ({','.join(df.columns)}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
        raw.commit()
    finally:
        raw.close()

def ts(week: int, dow: int, hour: int) -> int:
    d = SEM_START + timedelta(weeks=week, days=dow, hours=hour, minutes=int(rng.integers(0, 60)),
                              seconds=int(rng.integers(0, 60)))
    return int(d.timestamp())

def load_context():
    enrol = q("""
        SELECT DISTINCT c.id courseid, ra.userid, ctx.id course_ctx
        FROM mdl_course c
        JOIN mdl_context ctx ON ctx.instanceid=c.id AND ctx.contextlevel=50
        JOIN mdl_role_assignments ra ON ra.contextid=ctx.id
        JOIN mdl_role r ON r.id=ra.roleid AND r.shortname='student'
        WHERE c.id<>1""")
    assigns = q("""
        SELECT a.id assignid, a.course courseid, a.duedate, cx.id module_ctx, cm.id cmid
        FROM mdl_assign a
        JOIN mdl_course_modules cm ON cm.instance=a.id
        JOIN mdl_modules m ON m.id=cm.module AND m.name='assign'
        JOIN mdl_context cx ON cx.instanceid=cm.id AND cx.contextlevel=70""")
    sessions = q("""
        SELECT s.id sessionid, a.course courseid, s.sessdate, a.id attendanceid
        FROM mdl_attendance_sessions s JOIN mdl_attendance a ON a.id=s.attendanceid""")
    statuses = q("SELECT id, attendanceid, acronym FROM mdl_attendance_statuses WHERE deleted=0")
    return enrol, assigns, sessions, statuses

def assign_profiles(enrol: pd.DataFrame) -> pd.DataFrame:
    users = enrol["userid"].unique()
    base = dict(zip(users, rng.choice(list(PROFILES), size=len(users), p=list(PROFILES.values()))))
    def pick(uid):  # 80% giữ hồ sơ chung, 20% dao động theo môn
        return base[uid] if rng.random() < .8 else rng.choice(list(PROFILES), p=list(PROFILES.values()))
    enrol = enrol.copy()
    enrol["profile"] = enrol["userid"].map(pick)
    enrol["never"] = [rng.random() < BEHAVIOR[p]["never"] for p in enrol["profile"]]
    enrol["dropout"] = [rng.random() < BEHAVIOR[p]["dropout"] for p in enrol["profile"]]
    return enrol

def log_row(uid, courseid, ctxid, t, event="\\core\\event\\course_viewed", action="viewed",
            target="course", crud="r", ctxlevel=50, instance=None, component="core"):
    return dict(eventname=event, component=component, action=action, target=target, objecttable=None,
                objectid=None, crud=crud, edulevel=2, contextid=ctxid, contextlevel=ctxlevel,
                contextinstanceid=instance or courseid, userid=uid, courseid=courseid,
                relateduserid=None, anonymous=0, other="null", timecreated=t, origin="web",
                ip=f"{MOCK_IP_PREFIX}{rng.integers(0,255)}.{rng.integers(1,254)}", realuserid=None)

def gen_logs(enrol: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for e in enrol.itertuples():
        if e.never:
            continue
        b = BEHAVIOR[e.profile]
        for w in range(WEEKS):
            lo, hi = b["sess"]
            if e.dropout and w >= 6:
                hi = max(0, hi // 3)
            for _ in range(int(rng.integers(lo, hi + 1))):
                dow = random.choices(range(7), weights=DOW_W)[0]
                hour = int(rng.choice(24, p=HOUR_P))
                t0 = ts(w, dow, hour)
                rows.append(log_row(e.userid, 0, 1, t0, "\\core\\event\\user_loggedin", "loggedin",
                                    "user", ctxlevel=10, instance=0))
                for k in range(int(rng.integers(3, 16))):          # 3–15 thao tác mỗi phiên
                    rows.append(log_row(e.userid, e.courseid, e.course_ctx, t0 + k * int(rng.integers(20, 180))))
    return pd.DataFrame(rows).astype({"relateduserid": "Int64", "objectid": "Int64", "realuserid": "Int64"})

def gen_submissions(enrol, assigns):
    subs, logs = [], []
    for courseid, grp in enrol.groupby("courseid"):
        a_list = assigns[assigns.courseid == courseid].sort_values("duedate")
        for e in grp.itertuples():
            b = BEHAVIOR[e.profile]
            n = len(a_list)
            if e.profile == "RED" and n:                     # đảm bảo thiếu ≥ 60% bài
                keep = set(rng.choice(a_list.assignid, size=int(n * 0.4), replace=False))
            else:
                keep = {a for a in a_list.assignid if rng.random() < b["submit"]}
            for a in a_list.itertuples():
                if a.assignid not in keep or e.never:
                    continue
                late = rng.random() < b["late"]
                t = int(a.duedate + (rng.integers(3600, 3 * 86400) if late else -rng.integers(600, 3 * 86400)))
                subs.append(dict(assignment=a.assignid, userid=e.userid, timecreated=t - 3600,
                                 timemodified=t, status="submitted", groupid=0, attemptnumber=0, latest=1))
                logs.append(log_row(e.userid, courseid, a.module_ctx, t, "\\mod_assign\\event\\assessable_submitted",
                                    "submitted", "assessable", crud="u", ctxlevel=70, instance=a.cmid,
                                    component="mod_assign"))
    return pd.DataFrame(subs), pd.DataFrame(logs).astype({"relateduserid": "Int64", "objectid": "Int64", "realuserid": "Int64"})

def gen_attendance(enrol, sessions, statuses):
    now = int(datetime.now(TZ).timestamp()); rows = []
    for s in sessions[sessions.sessdate < now].itertuples():
        st = statuses[statuses.attendanceid == s.attendanceid].set_index("acronym")["id"]
        for e in enrol[enrol.courseid == s.courseid].itertuples():
            p = BEHAVIOR[e.profile]["attend"] * (0.6 if e.dropout and s.sessdate > SEM_START.timestamp() + 6*7*86400 else 1)
            r = rng.random()
            acr = "P" if r < p else "L" if r < p + .03 else "E" if r < p + .05 else "A"
            rows.append(dict(sessionid=s.sessionid, studentid=e.userid, statusid=int(st[acr]),
                             statusset=",".join(map(str, st.values)), timetaken=s.sessdate + 900,
                             takenby=2, remarks=""))
    return pd.DataFrame(rows)

def main():
    enrol, assigns, sessions, statuses = load_context()
    enrol = assign_profiles(enrol)
    logs = gen_logs(enrol)
    subs, sub_logs = gen_submissions(enrol, assigns)
    att = gen_attendance(enrol, sessions, statuses)
    all_logs = pd.concat([logs, sub_logs]).sort_values("timecreated")
    copy_df(all_logs, "mdl_logstore_standard_log")
    copy_df(subs, "mdl_assign_submission")
    copy_df(att, "mdl_attendance_log")
    with engine.begin() as c:
        c.execute(text("""UPDATE mdl_attendance_sessions s SET lasttaken = s.sessdate + 900, lasttakenby = 2
                          WHERE s.sessdate < EXTRACT(EPOCH FROM now())"""))
        c.execute(text("""INSERT INTO mdl_user_lastaccess (userid, courseid, timeaccess)
                          SELECT userid, courseid, MAX(timecreated) FROM mdl_logstore_standard_log
                          WHERE courseid > 1 AND ip LIKE :p GROUP BY userid, courseid
                          ON CONFLICT (userid, courseid) DO UPDATE SET timeaccess = EXCLUDED.timeaccess"""),
                  {"p": MOCK_IP_PREFIX + "%"})
    enrol[["courseid", "userid", "profile"]].to_csv("mockdata/ground_truth_profiles.csv", index=False)
    print(f"logs={len(all_logs):,} submissions={len(subs):,} attendance={len(att):,}")

if __name__ == "__main__":
    main()
```

> Ghi chú: (1) `mdl_user_lastaccess` có unique index `(userid, courseid)` nên dùng được `ON CONFLICT`. (2) File **`ground_truth_profiles.csv`** là "đáp án" để đo độ chính xác của bộ luật rủi ro (Phần 6). (3) Có script `mockdata/cleanup.py` xóa các dòng log có `ip LIKE '10.99.%'`. (4) Script `mockdata/live_sessions.py` chạy lặp mỗi 5 phút, cập nhật `mdl_sessions` theo trọng số giờ để demo mục "online thời gian thực".

---

## PHẦN 4: TIẾN TRÌNH ETL & LẬP LỊCH

### 4.1 Kiến trúc

```
etl/
├── config.py            # DSN, timezone, RISK_THRESHOLDS, quy tắc học kỳ
├── db.py                # engine Moodle (read-only user, replica nếu có) + engine Analytics
├── extract/             # *.sql ở Phần 1, tham số :last_log_id, :max_log_id, :snapshot_date
├── transform/
│   ├── risk_rules.py    # score_student()
│   ├── progress.py      # tính tỷ lệ, section_progress JSONB
│   └── semester.py      # suy ra academic_year/semester
├── load/upsert.py       # COPY vào bảng staging TEMP → INSERT ... ON CONFLICT DO UPDATE
├── jobs/
│   ├── job_traffic.py
│   ├── job_course_progress.py
│   └── job_student_risk.py
└── scheduler.py         # APScheduler BlockingScheduler (container `etl`)
```

**Luồng mỗi job:**
1. `pg_try_advisory_lock(job_id)`: nếu job trước chưa xong thì bỏ qua lượt này, tránh chạy chồng.
2. Ghi `etl_run_log` (RUNNING).
3. **Extract**: đọc `etl_watermark.last_log_id`, lấy `max_id = SELECT MAX(id) FROM mdl_logstore_standard_log`, chỉ đọc khoảng `(last, max]` theo từng lô 200k dòng. Dữ liệu trạng thái (điểm danh, bài nộp, ghi danh) được đọc lại toàn bộ cho các môn **đang diễn ra**.
4. **Transform** bằng pandas: làm sạch (loại user đã xóa, `anonymous=1`, `userid=0` với dữ liệu SV), đổi múi giờ, suy ra học kỳ, chấm điểm rủi ro.
5. **Load**: `COPY` vào `tmp_*`, rồi `INSERT ... ON CONFLICT DO UPDATE`; cập nhật watermark **trong cùng transaction**.
6. Ghi `etl_run_log` (SUCCESS/FAILED). Nếu lỗi: retry 3 lần (backoff 1–5–15 phút), sau đó ghi log ERROR.

```python
# load/upsert.py (rút gọn)
def upsert(conn, df, table, pk_cols):
    tmp = f"tmp_{table}"
    conn.exec_driver_sql(f"CREATE TEMP TABLE {tmp} (LIKE analytics.{table} INCLUDING DEFAULTS) ON COMMIT DROP")
    copy_df_conn(conn, df, tmp)
    cols = ",".join(df.columns)
    updates = ",".join(f"{c}=EXCLUDED.{c}" for c in df.columns if c not in pk_cols)
    conn.exec_driver_sql(f"""INSERT INTO analytics.{table} ({cols}) SELECT {cols} FROM {tmp}
                             ON CONFLICT ({','.join(pk_cols)}) DO UPDATE SET {updates}, updated_at=now()""")

# job_traffic: phần cộng dồn online users
# avg_new = (avg_old*n + sample)/(n+1); peak = GREATEST(peak_old, sample)
```

### 4.2 Lịch chạy

| Job | Tần suất | Phạm vi xử lý | Lý do |
|---|---|---|---|
| `traffic_online_snapshot` | **mỗi 5 phút** (`*/5 * * * *`) | chụp `mdl_sessions` → cập nhật peak/avg của giờ hiện tại | Gần thời gian thực, truy vấn rất nhẹ |
| `traffic_hourly` | **mỗi 5 phút** (cùng job) | log mới theo watermark → UPSERT giờ hiện tại và giờ trước | Log có thể ghi trễ vài phút |
| `course_progress_intraday` | **mỗi 1 giờ** (`5 * * * *`) | các môn đang diễn ra, `stat_date = hôm nay` | Admin xem số liệu trong ngày |
| `student_risk_intraday` | **mỗi 2 giờ từ 07h–21h** (`15 7-21/2 * * *`) | các môn đang diễn ra, snapshot hôm nay (ghi đè) | GV cần cảnh báo kịp trong ngày học |
| `nightly_full_rebuild` | **01:00 hằng đêm** | tính lại progress của ngày hôm qua (chốt số), risk snapshot chốt ngày, đánh dấu `is_peak_hour` (P90 28 ngày), `REFRESH MATERIALIZED VIEW` | Đảm bảo số liệu nhất quán, sửa log đến trễ |
| `weekly_maintenance` | **CN 03:00** | `VACUUM ANALYZE` các bảng fact, xóa risk snapshot > 180 ngày (giữ snapshot cuối mỗi tuần) | Giữ bảng gọn |
| `backfill` (thủ công) | CLI `python -m etl.jobs.backfill --from 2026-09-07` | nạp lại lịch sử | Lần đầu nạp dữ liệu |

```python
# scheduler.py
sched = BlockingScheduler(timezone="Asia/Ho_Chi_Minh")
sched.add_job(job_traffic.run,          CronTrigger(minute="*/5"),                 max_instances=1, coalesce=True)
sched.add_job(job_course_progress.run,  CronTrigger(minute=5))
sched.add_job(job_student_risk.run,     CronTrigger(hour="7-21/2", minute=15))
sched.add_job(nightly.run,              CronTrigger(hour=1, minute=0))
sched.add_job(maintenance.run,          CronTrigger(day_of_week="sun", hour=3))
sched.start()
```
Nếu chạy bằng crontab Linux thay APScheduler:
```
*/5 * * * *    cd /opt/etl && python -m etl.jobs.job_traffic          >> /var/log/etl/traffic.log 2>&1
5 * * * *      cd /opt/etl && python -m etl.jobs.job_course_progress  >> /var/log/etl/progress.log 2>&1
15 7-21/2 * * * cd /opt/etl && python -m etl.jobs.job_student_risk    >> /var/log/etl/risk.log 2>&1
0 1 * * *      cd /opt/etl && python -m etl.jobs.nightly              >> /var/log/etl/nightly.log 2>&1
```

**An toàn cho Moodle:** dùng user CSDL chỉ có quyền `SELECT`; đặt `statement_timeout = 60s`; nếu có replica thì đọc từ replica. Khuyến nghị Moodle có index `mdl_logsstanlog_tim_ix (timecreated)` và `mdl_logsstanlog_couusecon_ix (courseid, userid, ...)` (Moodle 3.9 đã có sẵn).

---

## PHẦN 5: THIẾT KẾ & XÂY DỰNG WEB DASHBOARD

### 5.1 RESTful API (FastAPI, tiền tố `/api/v1`)

Quy ước chung: xác thực `Authorization: Bearer <JWT>`. Lỗi trả `{"detail": "..."}`. Danh sách phân trang trả `{"items": [...], "total": n, "page": p, "page_size": s}`. Mỗi response có `data_updated_at` (thời điểm ETL chạy xong gần nhất).

**Xác thực & dùng chung**

| Method | URL | Tham số | Response |
|---|---|---|---|
| POST | `/auth/login` | body `{username, password}` | `{access_token, token_type, user:{id, full_name, role}}` |
| GET | `/auth/me` | – | `{id, username, full_name, role}` |
| GET | `/filters` | – | `{faculties:[{id,name}], academic_years:["2026-2027"], semesters:[1,2,3]}` |
| GET | `/etl/status` | – | `[{job_name, last_success_at, status}]` |

**Admin** (`role=ADMIN`)

| Method | URL | Tham số | Response mẫu |
|---|---|---|---|
| GET | `/admin/overview/kpis` | `academic_year, semester, faculty_id?` | `{"total_courses":40,"total_enrolled":10124,"total_active":8870,"active_rate":87.6,"peak_requests_today":{"hour":"09:00","value":15320},"avg_online_users_today":212,"current_online":187,"red_students":1480}` |
| GET | `/admin/enrollment/by-faculty` | `academic_year, semester` | `{"items":[{"faculty_id":3,"faculty_name":"CNTT","enrolled":2450,"active":2190,"inactive":260,"course_count":8}]}` |
| GET | `/admin/enrollment/faculties/{faculty_id}/courses` | `academic_year, semester, sort=active_rate` | `{"items":[{"course_id":101,"shortname":"CT101","fullname":"Cơ sở dữ liệu","enrolled":62,"active":55,"active_rate":88.7,"red_count":7}]}` |
| GET | `/admin/enrollment/courses/{course_id}/students` | `page, page_size, status=active\|inactive` | danh sách SV (cấp drill-down cuối) |
| GET | `/admin/traffic/hourly` | `from=2026-09-14, to=2026-09-20` | `{"items":[{"stat_hour":"2026-09-14T09:00:00","total_requests":15320,"unique_users":930,"peak_online_users":265,"avg_online_users":210.5,"is_peak_hour":true}]}` |
| GET | `/admin/traffic/realtime` | – | `{"current_hour":"2026-09-14T10:00:00","current_online":187,"requests_so_far":8420,"series_24h":[...]}` (frontend gọi lại mỗi 60 giây) |
| GET | `/admin/traffic/heatmap` | `weeks=4` | `{"matrix":[{"day_of_week":1,"hour_of_day":9,"avg_requests":14800}]}` |
| GET | `/admin/reports/preview` | `report_type=enrollment\|traffic\|risk, faculty_id?, academic_year, semester, course_id?, risk_level?, from?, to?, page` | `{"columns":[{"key":"faculty_name","title":"Khoa"}],"items":[...],"total":320}` |
| GET | `/admin/reports/export` | cùng tham số với preview + `format=xlsx\|pdf` | file stream (`Content-Disposition: attachment; filename=bao_cao_enrollment_HK1_2026-2027.xlsx`) |

**Giảng viên** (`role=TEACHER`, **mọi endpoint kiểm tra `teacher_id ∈ teacher_ids`**, sai trả 403)

| Method | URL | Tham số | Response mẫu |
|---|---|---|---|
| GET | `/teacher/courses` | `academic_year?, semester?` | `{"items":[{"course_id":101,"shortname":"CT101","fullname":"Cơ sở dữ liệu","enrolled":62,"red":7,"yellow":12,"green":43}]}` |
| GET | `/teacher/courses/{course_id}/risk-summary` | – | `{"red":7,"yellow":12,"green":43,"by_criterion":{"attendance":9,"inactivity":11,"assignment":8},"snapshot_date":"2026-09-14"}` |
| GET | `/teacher/courses/{course_id}/students` | `risk_level?, criterion?, search?, sort=risk_score, order=desc, page, page_size` | `{"items":[{"user_id":2301,"student_code":"2112345","student_name":"Nguyễn Văn A","risk_level":"RED","risk_score":85,"absence_rate":41.7,"missing_assignments":"4/5","days_since_last_access":16,"risk_reasons":["Vắng 5/12 buổi (42%)","Thiếu 4/5 bài tập"]}],"total":62}` |
| GET | `/teacher/courses/{course_id}/students/{user_id}` | – | toàn bộ cột risk + `weekly_activity`, `assignment_detail`, `class_avg_access`, `risk_history:[{date, risk_level, risk_score}]`, `interventions:[...]` |
| POST | `/teacher/courses/{course_id}/students/{user_id}/interventions` | body `{action_type:"MESSAGE"\|"EMAIL"\|"NOTE", content}` | `201 {"id":55,"created_at":"..."}`. Với MESSAGE có thể gọi Moodle Web Service `core_message_send_instant_messages` (tùy chọn) |
| GET | `/teacher/courses/{course_id}/progress` | `granularity=day\|week` | `{"summary":{"avg_completion_rate":71.2,"submission_rate":78.5,"attendance_rate":88.1},"series":[{"period":"2026-W38","active_students":51,"avg_completion_rate":65.0}],"sections":[{"section":1,"name":"Chương 1","completion_rate":92.0}]}` |
| GET | `/teacher/courses/{course_id}/students/{user_id}/compare` | – | `{"metrics":[{"key":"access_14d","label":"Truy cập 14 ngày","student":3,"class_avg":24.6},{"key":"submission_rate","student":20,"class_avg":78.5},{"key":"attendance_rate","student":58.3,"class_avg":88.1},{"key":"completion_rate","student":15,"class_avg":71.2}]}` |
| GET | `/teacher/courses/{course_id}/export` | `format=xlsx, risk_level?` | file danh sách cảnh báo |

**Backend cấu trúc:** `backend/app/main.py`, `core/security.py` (JWT, `require_role`), `routers/{auth,admin,teacher,reports}.py`, `repositories/*.py` (SQL thuần bằng `text()`), `schemas/*.py` (Pydantic), `services/export_excel.py` (openpyxl), `services/export_pdf.py` (Jinja2 + WeasyPrint). Pool kết nối `asyncpg`/SQLAlchemy `pool_size=10`. Cache TTL 60 giây trong bộ nhớ (`cachetools`) cho các endpoint KPI.

### 5.2 Layout Trang Admin

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ LOGO  LMS Analytics      [Tổng quan] [Lưu lượng] [Báo cáo]          Cập nhật: 10:05  👤 Admin│
├───────────────────────────────────────────────────────────────────────────────────────────┤
│ BỘ LỌC:  [Năm học ▼ 2026-2027] [Học kỳ ▼ HK1] [Khoa ▼ Tất cả]     [⟳ Làm mới] [⬇ Export ▼]│
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│ Tổng môn học │ SV đăng ký   │ SV tương tác │ Online hiện  │ Peak hôm nay │ SV nguy cơ ĐỎ  │  ← KPI Cards
│     40       │   10.124     │ 8.870 (87.6%)│ tại  187 ●   │ 15.320 req   │ 1.480 (14.6%)  │
│              │              │              │              │ lúc 09:00 🔺 │                │
├──────────────┴──────────────┴──────────────┴──────┬───────┴──────────────┴────────────────┤
│ LƯU LƯỢNG TRUY CẬP (Dual-axis Line)  [24h|7 ngày] │ SV ĐĂNG KÝ vs TƯƠNG TÁC THEO KHOA      │
│  Trục trái: Requests/giờ ─── Trục phải: Online ---│ (Stacked Bar: Active | Inactive)       │
│  ▁▂▅█▇▅▃▄█▇▅▃▂▃▄▃▂▁                               │ CNTT   ███████████░░                    │
│  vùng tô nền 08–10h, 14–16h (giờ cao điểm)        │ KT     █████████░░░   ← click để drill  │
├───────────────────────────────────────────────────┴────────────────────────────────────────┤
│ BẢNG PHÂN CẤP DRILL-DOWN:  Khoa ▸ Môn ▸ Sinh viên        (breadcrumb: Tất cả › CNTT › CT101)│
│ ▸ CNTT | 8 môn | 2.450 ĐK | 2.190 TT | 89.4% ▓▓▓▓▓▓▓▓░ | 🔴 210                            │
│   ▾ CT101 Cơ sở dữ liệu | 62 | 55 | 88.7% | 🔴 7   → [Xem SV]                               │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│ HEATMAP GIỜ × THỨ (4 tuần)  – hỗ trợ dự báo giờ cao điểm                                    │
└────────────────────────────────────────────────────────────────────────────────────────────┘
Trang "Báo cáo": [Loại báo cáo ▼] + bộ lọc đa chiều → Data Preview Table (phân trang) → [Xuất Excel] [Xuất PDF]
```

### 5.3 Layout Trang Giảng viên

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ LOGO  LMS Analytics   Môn: [CT101 – Cơ sở dữ liệu ▼]   [Cảnh báo] [Tiến độ lớp]  👤 GV Trần B│
├──────────────────┬──────────────────┬──────────────────┬───────────────────────────────────┤
│ 🔴 Nguy cơ cao   │ 🟡 Cần lưu ý     │ 🟢 An toàn       │  DOUGHNUT tỷ lệ rủi ro             │
│   7 SV (11%)     │   12 SV (19%)    │   43 SV (70%)    │     (click lát cắt = lọc bảng)     │
│ [click để lọc]   │                  │                  │  Theo tiêu chí: Vắng 9 | Không TT 11│
├──────────────────┴──────────────────┴──────────────────┤  | Thiếu bài 8                       │
│ BẢNG CẢNH BÁO   [🔍 Tìm MSSV/tên] [Mức ▼] [Tiêu chí ▼] └───────────────────────────────────┤
│ ● | MSSV    | Họ tên        | Vắng     | Truy cập cuối | Bài tập | Điểm | Lý do     | ⋯     │
│ 🔴| 2112345 | Nguyễn Văn A  | 42%      | 16 ngày trước | 1/5     |  85  | Vắng, Thiếu| [Chi tiết]│
│ 🟡| 2112399 | Lê Thị C      | 18%      | 9 ngày trước  | 3/5     |  40  | Ít TT     | [Chi tiết]│
│ 🟢| ...                                                                        [⬇ Excel]  │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│ TIẾN ĐỘ LỚP: Hoàn thành hoạt động ▓▓▓▓▓▓▓░░ 71% | Nộp bài ▓▓▓▓▓▓▓▓░ 78% | Chuyên cần 88%   │
│ Theo chương: Ch1 ▓▓▓▓▓▓▓▓▓ 92%  Ch2 ▓▓▓▓▓▓▓░ 80%  Ch3 ▓▓▓▓░░░ 55%  (Progress Bar ngang)    │
│ Line: SV hoạt động theo tuần                                                                │
└────────────────────────────────────────────────────────────────────────────────────────────┘

MODAL CHI TIẾT SINH VIÊN (mở khi bấm [Chi tiết])
┌────────────────────────────────────────────────────────────────┐
│ 🔴 Nguyễn Văn A – 2112345 – a@dlu.edu.vn        Điểm rủi ro 85 │
│ Lý do: • Vắng 5/12 buổi (42%)  • Thiếu 4/5 bài  • 16 ngày chưa vào│
├──────────────────────────────┬─────────────────────────────────┤
│ Bar so sánh: SV vs TB lớp    │ Line hoạt động 15 tuần (views)   │
│ Truy cập 14d  ▇ 3 | ███ 24.6 │ ▅▅▃▂▁▁▁                          │
│ Nộp bài       ▇ 20%| ███ 78% │ ● = có mặt buổi học, ○ = vắng    │
├──────────────────────────────┴─────────────────────────────────┤
│ Bài tập: BT1 ✔ đúng hạn | BT2 ✘ | BT3 ✘ | BT4 ✘ | BT5 ✘          │
│ Lịch sử cảnh báo: 01/09 🟢 → 07/09 🟡 → 14/09 🔴                 │
│ Can thiệp trước: 10/09 NOTE "Đã nhắc trên lớp"                   │
├────────────────────────────────────────────────────────────────┤
│ [✉ Gửi tin nhắn Moodle] [📧 Email] [📝 Ghi chú] [📅 Hẹn gặp]  [Đóng]│
└────────────────────────────────────────────────────────────────┘
```

### 5.4 Thư viện đồ họa

| Nhu cầu | Chart.js 4 (chọn) | Ghi chú |
|---|---|---|
| Dual-axis line | `scales.y` + `scales.y1` (`position:'right'`) | ✔ |
| Stacked bar + drill-down | `stacked:true` + sự kiện `onClick` → `getElementsAtEventForMode` | ✔ |
| Doughnut rủi ro | `type:'doughnut'` | ✔ |
| Progress bar | Ant Design `<Progress>` hoặc bar ngang `indexAxis:'y'` | ✔ |
| Heatmap | plugin `chartjs-chart-matrix` | ✔ |
| Vùng giờ cao điểm | plugin `chartjs-plugin-annotation` | ✔ |

Tiêu chí chọn: nhẹ (~70 KB gzip), có bản React (`react-chartjs-2`), dễ học, khớp đề cương. Nếu sau này cần > 50k điểm dữ liệu trên một biểu đồ, có thể thay bằng Apache ECharts.
**Màu đèn giao thông (dễ đọc cả với người mù màu, luôn đi kèm biểu tượng + chữ):** Đỏ `#D64545` + "●  Nguy cơ cao", Vàng `#E0A100` + "▲ Cần lưu ý", Xanh `#2E9D5B` + "✔ An toàn".

### 5.5 Mã nguồn mẫu Frontend (HTML + Chart.js, chạy độc lập để làm prototype)

File `frontend/prototype/index.html`: mở trực tiếp bằng trình duyệt. Khi có API, thay `mockTraffic`/`mockStudents` bằng `fetch`.

```html
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Prototype – LMS Analytics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root { --red:#D64545; --yellow:#E0A100; --green:#2E9D5B; --bg:#f5f7fb; --card:#fff; --text:#1f2937; }
  body { font-family: system-ui, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; }
  .card { background: var(--card); border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
  .kpi b { display: block; font-size: 26px; }
  .chart-box { position: relative; height: 320px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 14px; }
  tr:hover { background: #f9fafb; cursor: pointer; }
  .badge { display: inline-flex; gap: 6px; align-items: center; padding: 2px 10px; border-radius: 999px; font-weight: 600; font-size: 12px; color: #fff; }
  .RED { background: var(--red); } .YELLOW { background: var(--yellow); } .GREEN { background: var(--green); }
  .filters button { border: 1px solid #d1d5db; background: #fff; border-radius: 6px; padding: 6px 12px; cursor: pointer; }
  .filters button.active { background: #1f2937; color: #fff; }
  dialog { border: none; border-radius: 12px; width: min(560px, 92vw); }
  dialog::backdrop { background: rgba(0,0,0,.4); }
</style>
</head>
<body>
  <div class="card kpis">
    <div class="kpi">Online hiện tại<b id="kpiOnline">–</b></div>
    <div class="kpi">Peak requests<b id="kpiPeak">–</b></div>
    <div class="kpi">TB user/giờ<b id="kpiAvg">–</b></div>
  </div>

  <div class="card">
    <h3>Lưu lượng truy cập 24 giờ</h3>
    <div class="chart-box"><canvas id="trafficChart"></canvas></div>
  </div>

  <div class="card">
    <h3>Cảnh báo sinh viên – CT101</h3>
    <div class="filters">
      <button data-level="ALL" class="active">Tất cả</button>
      <button data-level="RED">🔴 Nguy cơ cao</button>
      <button data-level="YELLOW">🟡 Cần lưu ý</button>
      <button data-level="GREEN">🟢 An toàn</button>
    </div>
    <table>
      <thead><tr><th>Mức</th><th>MSSV</th><th>Họ tên</th><th>Vắng</th><th>Bài tập</th><th>Truy cập cuối</th><th>Điểm</th></tr></thead>
      <tbody id="riskBody"></tbody>
    </table>
  </div>

  <dialog id="studentModal">
    <h3 id="mTitle"></h3>
    <ul id="mReasons"></ul>
    <div class="chart-box" style="height:220px"><canvas id="compareChart"></canvas></div>
    <p><button onclick="alert('Gọi POST /interventions')">✉ Gửi nhắc nhở</button>
       <button onclick="studentModal.close()">Đóng</button></p>
  </dialog>

<script>
const LABEL = { RED: "● Nguy cơ cao", YELLOW: "▲ Cần lưu ý", GREEN: "✔ An toàn" };
const ORDER = { RED: 0, YELLOW: 1, GREEN: 2 };

// ---- Mock data (thay bằng fetch('/api/v1/admin/traffic/hourly?...')) ----
const w = [.3,.2,.1,.1,.1,.2,.6,1.5,3,3.2,3,2,1,1.5,3,3.2,2.8,1.8,1.2,1.4,1.8,1.6,1,.6];
const mockTraffic = w.map((x, h) => ({
  hour: `${String(h).padStart(2, "0")}:00`,
  total_requests: Math.round(x * 4800 + Math.random() * 600),
  avg_online_users: Math.round(x * 70 + Math.random() * 15),
}));
const mockStudents = [
  { user_id: 1, code: "2112345", name: "Nguyễn Văn A", level: "RED", score: 85, absence: 41.7, sub: "1/5", days: 16,
    reasons: ["Vắng 5/12 buổi (42%)", "Thiếu 4/5 bài tập", "16 ngày chưa truy cập"], cmp: [3, 20, 58] },
  { user_id: 2, code: "2112399", name: "Lê Thị C", level: "YELLOW", score: 40, absence: 18.0, sub: "3/5", days: 9,
    reasons: ["9 ngày chưa truy cập"], cmp: [11, 60, 82] },
  { user_id: 3, code: "2112401", name: "Phạm Minh D", level: "GREEN", score: 0, absence: 0, sub: "5/5", days: 1,
    reasons: [], cmp: [31, 100, 100] },
];
const classAvg = [24.6, 78.5, 88.1];

// ---- Dual-axis line chart ----
function renderTraffic(data) {
  const peak = data.reduce((a, b) => (b.total_requests > a.total_requests ? b : a));
  kpiOnline.textContent = data.at(-1).avg_online_users;
  kpiPeak.textContent = `${peak.total_requests.toLocaleString("vi-VN")} (${peak.hour})`;
  kpiAvg.textContent = Math.round(data.reduce((s, d) => s + d.avg_online_users, 0) / data.length);

  new Chart(trafficChart, {
    type: "line",
    data: {
      labels: data.map(d => d.hour),
      datasets: [
        { label: "Requests/giờ", data: data.map(d => d.total_requests), yAxisID: "y",
          borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,.12)", fill: true, tension: .35, pointRadius: 2 },
        { label: "User online (TB)", data: data.map(d => d.avg_online_users), yAxisID: "y1",
          borderColor: "#f97316", borderDash: [6, 4], tension: .35, pointRadius: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y.toLocaleString("vi-VN")}` } } },
      scales: {
        y:  { position: "left",  title: { display: true, text: "Requests" }, beginAtZero: true },
        y1: { position: "right", title: { display: true, text: "Users online" }, beginAtZero: true,
              grid: { drawOnChartArea: false } },
      },
    },
  });
}

// ---- Traffic-light table ----
function renderTable(level = "ALL") {
  const rows = mockStudents
    .filter(s => level === "ALL" || s.level === level)
    .sort((a, b) => ORDER[a.level] - ORDER[b.level] || b.score - a.score);
  riskBody.innerHTML = rows.map(s => `
    <tr data-id="${s.user_id}">
      <td><span class="badge ${s.level}">${LABEL[s.level]}</span></td>
      <td>${s.code}</td><td>${s.name}</td><td>${s.absence}%</td>
      <td>${s.sub}</td><td>${s.days} ngày trước</td><td>${s.score}</td>
    </tr>`).join("");
}

let cmpChart;
function openModal(id) {
  const s = mockStudents.find(x => x.user_id === id);
  mTitle.innerHTML = `<span class="badge ${s.level}">${LABEL[s.level]}</span> ${s.name} – ${s.code}`;
  mReasons.innerHTML = s.reasons.length ? s.reasons.map(r => `<li>${r}</li>`).join("") : "<li>Không có bất thường</li>";
  cmpChart?.destroy();
  cmpChart = new Chart(compareChart, {
    type: "bar",
    data: { labels: ["Truy cập 14 ngày", "Nộp bài (%)", "Chuyên cần (%)"],
            datasets: [{ label: "Sinh viên", data: s.cmp, backgroundColor: "#D64545" },
                       { label: "TB lớp", data: classAvg, backgroundColor: "#9ca3af" }] },
    options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
  });
  studentModal.showModal();
}

document.querySelectorAll(".filters button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".filters button").forEach(x => x.classList.remove("active"));
  b.classList.add("active"); renderTable(b.dataset.level);
});
riskBody.onclick = e => { const tr = e.target.closest("tr"); if (tr) openModal(+tr.dataset.id); };

renderTraffic(mockTraffic);
renderTable();
</script>
</body>
</html>
```

**Khi chuyển sang React:** `components/TrafficDualAxisChart.jsx` (`<Line data options />` của react-chartjs-2 với đúng `options` như trên), `components/RiskBadge.jsx`, `components/RiskTable.jsx` (AntD `<Table>` + `rowClassName`), `components/StudentDetailModal.jsx`, `hooks/useApi.js` (axios + React Query, `refetchInterval: 60000` cho realtime), `pages/AdminDashboard.jsx`, `pages/TeacherDashboard.jsx`, `pages/Reports.jsx`, `routes/ProtectedRoute.jsx` (kiểm tra vai trò).

---

## PHẦN 6: TRIỂN KHAI, KIỂM THỬ VÀ HOÀN THÀNH ĐỒ ÁN

### 6.1 Kiểm thử tính đúng đắn dữ liệu

| Loại | Cách làm | Tiêu chí đạt |
|---|---|---|
| **Unit test luật rủi ro** | `pytest tests/test_risk_rules.py`: ≥ 20 ca biên (vắng đúng 30%, bỏ đúng 3/5, chưa có buổi điểm danh, `days=None`, lớp trung vị 0) | 100% pass |
| **Đối soát (reconciliation)** | `tests/reconcile.py`: với 5 môn chọn ngẫu nhiên, chạy SQL trực tiếp trên Moodle (Phần 1) rồi so với fact: enrolled, active, requests/giờ, missing, absent | Sai lệch = 0 (dữ liệu trạng thái) và ≤ 0.5% (log, do dữ liệu mới ghi trong lúc chạy) |
| **Đối chiếu ground truth** | So `risk_level` với `ground_truth_profiles.csv` từ mock: tính Precision/Recall cho lớp RED, ma trận nhầm lẫn | Recall(RED) ≥ 90%, Precision(RED) ≥ 80%. Đưa ma trận nhầm lẫn vào báo cáo |
| **Idempotency** | Chạy cùng một job 2 lần liên tiếp | Số dòng và checksum (`md5(string_agg)`) không đổi |
| **Incremental đúng** | Chèn thêm 10.000 log, chạy job | Chỉ các giờ hoặc môn liên quan bị cập nhật, watermark tăng đúng |
| **Ràng buộc dữ liệu** | Test SQL: `active ≤ enrolled`, `submitted ≤ total`, tỷ lệ trong 0–100, không NULL ở cột bắt buộc | 0 vi phạm |
| **Kiểm thử thủ công với GV** | Cho 2–3 GV xem danh sách ĐỎ của một lớp thật hoặc mô phỏng | GV đồng ý ≥ 80% trường hợp |

### 6.2 Kiểm thử hiệu năng (mục tiêu Dashboard < 1 giây)

| Hạng mục | Công cụ | Kịch bản | Mục tiêu |
|---|---|---|---|
| Truy vấn SQL | `EXPLAIN (ANALYZE, BUFFERS)` | 10 truy vấn chính (Phần 2.4 và các API) trên dữ liệu **x1** (2–3 triệu log) và **x10** (25 triệu log, ~1 triệu dòng risk snapshot) | ≤ 100 ms mỗi truy vấn; plan dùng Index/Bitmap scan, không Seq scan trên bảng lớn |
| API | **Locust** (hoặc k6) | 50 người dùng đồng thời (40 GV, 10 Admin), 10 phút, think-time 2–5 giây | **p95 < 500 ms**, p99 < 1 s, lỗi < 0.1% |
| Tải trang | Lighthouse, Chrome DevTools | Trang Admin và GV, cache lạnh | Hiển thị biểu đồ đầu tiên < 1 s (sau khi có API), LCP < 2.5 s, TTI < 3 s |
| ETL | log `etl_run_log` | job traffic 5 phút, risk trên 10.000 ghi danh | traffic < 30 s; risk < 5 phút; nightly < 20 phút; CPU Moodle DB tăng < 20% |
| Export | pytest-benchmark | Excel 10.000 dòng, PDF 500 dòng | < 5 s |

Nếu không đạt: thêm index hoặc covering index (`INCLUDE`), materialized view, cache API 60 giây, giảm cột trả về, phân trang phía server.

**Bảng kết quả benchmark (mẫu cho báo cáo):**

| Endpoint | Dataset | p50 | p95 | p99 | Đạt |
|---|---|---|---|---|---|
| GET /teacher/courses/{id}/students | x10 | … | … | … | ☐ |
| GET /admin/enrollment/by-faculty | x10 | … | … | … | ☐ |
| GET /admin/traffic/hourly (7 ngày) | x10 | … | … | … | ☐ |

### 6.3 Kiểm thử giao diện & chức năng
- **E2E Playwright:** đăng nhập Admin → lọc HK1 → click cột CNTT → bảng drill-down hiện môn → Export Excel tải file. Đăng nhập GV → lọc ĐỎ → mở Modal → gửi can thiệp → thấy trong lịch sử.
- **Phân quyền:** GV A gọi API môn của GV B phải nhận 403; GV gọi `/admin/*` phải nhận 403; token hết hạn phải nhận 401.
- **Responsive:** 1920, 1366, 768, 390 px. Biểu đồ co giãn, bảng cuộn ngang.
- **Khả dụng:** màu đèn luôn kèm chữ và biểu tượng; tương phản đạt WCAG AA; tooltip số theo định dạng `vi-VN`.
- **Bảo mật cơ bản:** SQL chỉ dùng tham số bind, CORS giới hạn domain, mật khẩu bcrypt, rate-limit endpoint login.

### 6.4 Triển khai
- `docker-compose.yml`: `moodle-db` (PG13), `moodle` (3.9), `analytics-db` (PG15), `etl`, `backend`, `frontend` (Nginx phục vụ build Vite, proxy `/api`).
- `.env.example` chứa DSN và JWT secret. Có `Makefile`/`scripts/`: `setup`, `seed`, `mock`, `etl-backfill`, `test`, `bench`.
- README hướng dẫn chạy demo từ đầu trong ≤ 15 phút.

### 6.5 Tiến độ (khớp 5 giai đoạn trong PDF)

| Giai đoạn | Thời gian | Công việc chính | Sản phẩm bàn giao |
|---|---|---|---|
| 0 – Chuẩn bị | 14/09 – 21/09/2026 | Tạo repo GitHub, Docker Moodle 3.9 + mod_attendance, đọc schema | Môi trường chạy được |
| 1 – Đề cương | 22/09 – 05/10/2026 | Khảo sát GV/phòng đào tạo (5–10 phiếu), chốt tiêu chí và ngưỡng rủi ro, viết đề cương | Đề cương, tài liệu yêu cầu |
| 2 – Nghiên cứu CSDL | 06/10 – 26/10/2026 | Mapping Phần 1, viết và chạy thử 12 truy vấn trích xuất, gap analysis, **sinh mock data** (Phần 3) | `sql/extract/*.sql`, Moodle có dữ liệu mẫu, sơ đồ ERD bảng liên quan |
| 3 – Thiết kế | 27/10 – 17/11/2026 | DDL analytics, ETL 3 job + scheduler, unit test luật, wireframe (Figma hoặc prototype HTML ở 5.5), đặc tả OpenAPI | `analytics_schema.sql`, `etl/`, wireframe, `openapi.yaml` |
| 4 – Lập trình | 18/11 – 15/12/2026 | Tuần 1: auth + API Admin; Tuần 2: API GV + export; Tuần 3: Frontend Admin; Tuần 4: Frontend GV + Modal + can thiệp; ETL tự động trong Docker | Web chạy đủ chức năng 1.1–1.3, 2.1–2.2 |
| 5 – Kiểm thử & báo cáo | 16/12/2026 – 20/01/2027 | Phần 6.1–6.3, tối ưu, benchmark x10, UAT với GV, viết báo cáo, slide, video demo | Báo cáo, kết quả benchmark, slide, video 5 phút |

**Mốc kiểm soát (milestones):** M1 26/10 có mock data · M2 17/11 ETL chạy tự động · M3 15/12 feature freeze · M4 10/01 báo cáo nháp · M5 20/01 nộp.

### 6.6 Cấu trúc báo cáo đồ án đề xuất
1. **Chương 1 – Tổng quan:** bối cảnh, mục tiêu, phạm vi, phương pháp.
2. **Chương 2 – Cơ sở lý thuyết:** Learning Analytics (mô tả, chẩn đoán, cảnh báo sớm), nguyên tắc thiết kế dashboard, kiến trúc Moodle và logstore, ETL/Data Mart.
3. **Chương 3 – Phân tích & thiết kế:** use case Admin/GV, mapping dữ liệu, thiết kế 3 bảng fact, luật rủi ro, API, wireframe.
4. **Chương 4 – Cài đặt:** mock data, ETL, backend, frontend, triển khai Docker.
5. **Chương 5 – Thực nghiệm & đánh giá:** độ đúng dữ liệu, Precision/Recall luật rủi ro, benchmark < 1 s, phản hồi GV.
6. **Chương 6 – Kết luận & hướng phát triển:** mô hình ML dự báo (Logistic Regression hoặc Random Forest trên các đặc trưng đã có), Moodle Local Plugin nhúng dashboard, dùng access log Nginx làm traffic thật.

### 6.7 Rủi ro dự án & phương án

| Rủi ro | Phương án |
|---|---|
| Không có dữ liệu Moodle thật của trường | Dùng mock data có ground truth; nếu có dữ liệu thật thì ẩn danh hóa (hash MSSV) trước khi dùng |
| Plugin attendance không tương thích | Dùng bản `mod_attendance` 3.9 (MOODLE_39_STABLE). Phương án dự phòng: coi "buổi học" là `course_viewed` trong khung giờ lớp |
| Logstore quá lớn làm ETL chậm | Đọc tăng dần theo `id`, theo lô, đọc từ replica, chạy nightly |
| Ngưỡng rủi ro chưa hợp lý | Đặt thành tham số cấu hình, hiệu chỉnh qua UAT với GV |

---

## PHỤ LỤC A – CẤU TRÚC THƯ MỤC DỰ ÁN

```
Do_an_chuyen_nganh/
├── SPEC/                         # tài liệu yêu cầu + kế hoạch này
├── docker-compose.yml
├── .env.example
├── sql/
│   ├── analytics_schema.sql
│   └── extract/                  # enrolment.sql, active.sql, traffic.sql, attendance.sql, assignments.sql, completion.sql
├── mockdata/                     # seed_structure.py, generate_activity.py, live_sessions.py, cleanup.py
├── etl/                          # (Phần 4.1)
├── backend/app/                  # main.py, core/, routers/, repositories/, schemas/, services/
├── frontend/                     # Vite React: src/pages, src/components, src/hooks; prototype/index.html
├── tests/                        # test_risk_rules.py, reconcile.py, api/, e2e/ (Playwright), locustfile.py
└── docs/                         # báo cáo, ERD, wireframe, kết quả benchmark
```

## PHỤ LỤC B – CHECKLIST HOÀN THÀNH
- [ ] Moodle 3.9 + mod_attendance chạy trên Docker
- [ ] Mock data: 5 khoa / 40 môn / 2.000 SV / ≥ 2 triệu log / 15% RED
- [ ] 3 bảng fact + index + view
- [ ] 3 job ETL + scheduler + etl_run_log
- [ ] API Admin (KPI, by-faculty, drill-down, traffic, report, export)
- [ ] API GV (courses, risk-summary, students, detail, interventions, progress, compare)
- [ ] UI Admin: KPI, dual-axis, stacked bar drill-down, bảng phân cấp, export
- [ ] UI GV: đèn giao thông, doughnut, bảng, modal, progress, comparative bar
- [ ] Unit test + reconcile + Precision/Recall
- [ ] Benchmark p95 < 500 ms, p99 < 1 s
- [ ] Báo cáo, slide, video demo
