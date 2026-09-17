-- =============================================================================
-- MOODLE_SRC V004 – Plugin điểm danh mod_attendance (bản MOODLE_39_STABLE)
-- Nguồn cấu trúc: mod/attendance/db/install.xml
-- Lưu ý: đây là PLUGIN, không có sẵn trong Moodle core (SPEC Phần 1.1).
-- =============================================================================

-- ---------------------------------------------------------------- mdl_attendance
CREATE TABLE mdl_attendance (
    id                   BIGSERIAL      PRIMARY KEY,
    course               BIGINT         NOT NULL DEFAULT 0,
    name                 VARCHAR(255),
    grade                NUMERIC(10, 5) NOT NULL DEFAULT 100,
    timemodified         BIGINT         NOT NULL DEFAULT 0,
    intro                TEXT,
    introformat          SMALLINT       NOT NULL DEFAULT 0,
    subnet               VARCHAR(255),
    sessiondetailspos    VARCHAR(5)     NOT NULL DEFAULT 'left',
    showsessiondetails   SMALLINT       NOT NULL DEFAULT 1,
    showextrauserdetails SMALLINT       NOT NULL DEFAULT 1
);
CREATE INDEX mdl_atte_cou_ix ON mdl_attendance (course);

-- ---------------------------------------------------------------- mdl_attendance_sessions
CREATE TABLE mdl_attendance_sessions (
    id                BIGSERIAL    PRIMARY KEY,
    attendanceid      BIGINT       NOT NULL DEFAULT 0,
    groupid           BIGINT       NOT NULL DEFAULT 0,
    sessdate          BIGINT       NOT NULL DEFAULT 0,
    duration          BIGINT       NOT NULL DEFAULT 0,
    lasttaken         BIGINT,
    lasttakenby       BIGINT       NOT NULL DEFAULT 0,
    timemodified      BIGINT,
    description       TEXT         NOT NULL,
    descriptionformat SMALLINT     NOT NULL DEFAULT 0,
    studentscanmark   SMALLINT     NOT NULL DEFAULT 0,
    autoassignstatus  SMALLINT     NOT NULL DEFAULT 0,
    studentpassword   VARCHAR(50)           DEFAULT '',
    subnet            VARCHAR(255),
    automark          SMALLINT     NOT NULL DEFAULT 0,
    automarkcompleted SMALLINT     NOT NULL DEFAULT 0,
    statusset         INTEGER      NOT NULL DEFAULT 0,
    absenteereport    SMALLINT     NOT NULL DEFAULT 1,
    preventsharedip   SMALLINT     NOT NULL DEFAULT 0,
    preventsharediptime BIGINT,
    caleventid        BIGINT       NOT NULL DEFAULT 0,
    calendarevent     SMALLINT     NOT NULL DEFAULT 1,
    includeqrcode     SMALLINT     NOT NULL DEFAULT 0
);
CREATE INDEX mdl_attesess_att_ix ON mdl_attendance_sessions (attendanceid);
CREATE INDEX mdl_attesess_gro_ix ON mdl_attendance_sessions (groupid);
CREATE INDEX mdl_attesess_ses_ix ON mdl_attendance_sessions (sessdate);
CREATE INDEX mdl_attesess_cal_ix ON mdl_attendance_sessions (caleventid);
COMMENT ON COLUMN mdl_attendance_sessions.groupid IS '0 = buổi cho cả lớp; khác 0 = chỉ SV thuộc nhóm';
COMMENT ON COLUMN mdl_attendance_sessions.lasttaken IS 'Thời điểm điểm danh gần nhất; NULL/0 = chưa điểm danh';

-- ---------------------------------------------------------------- mdl_attendance_statuses
CREATE TABLE mdl_attendance_statuses (
    id                  BIGSERIAL     PRIMARY KEY,
    attendanceid        BIGINT        NOT NULL DEFAULT 0,
    acronym             VARCHAR(2)    NOT NULL DEFAULT '',
    description         VARCHAR(30)   NOT NULL DEFAULT '',
    grade               NUMERIC(5, 2) NOT NULL DEFAULT 0,
    studentavailability BIGINT,
    setunmarked         SMALLINT,
    visible             SMALLINT      NOT NULL DEFAULT 1,
    deleted             SMALLINT      NOT NULL DEFAULT 0,
    setnumber           INTEGER       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_attestat_att_ix ON mdl_attendance_statuses (attendanceid);
CREATE INDEX mdl_attestat_vis_ix ON mdl_attendance_statuses (visible);
CREATE INDEX mdl_attestat_del_ix ON mdl_attendance_statuses (deleted);
COMMENT ON COLUMN mdl_attendance_statuses.acronym IS 'P = có mặt, L = trễ, E = vắng có phép, A = vắng';

-- ---------------------------------------------------------------- mdl_attendance_log
CREATE TABLE mdl_attendance_log (
    id        BIGSERIAL     PRIMARY KEY,
    sessionid BIGINT        NOT NULL DEFAULT 0,
    studentid BIGINT        NOT NULL DEFAULT 0,
    statusid  BIGINT        NOT NULL DEFAULT 0,
    statusset VARCHAR(1333),
    timetaken BIGINT        NOT NULL DEFAULT 0,
    takenby   BIGINT        NOT NULL DEFAULT 0,
    remarks   VARCHAR(255),
    ipaddress VARCHAR(45)            DEFAULT ''
);
CREATE INDEX mdl_attelog_ses_ix ON mdl_attendance_log (sessionid);
CREATE INDEX mdl_attelog_stu_ix ON mdl_attendance_log (studentid);
CREATE INDEX mdl_attelog_sta_ix ON mdl_attendance_log (statusid);
