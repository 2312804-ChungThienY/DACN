-- =============================================================================
-- MOODLE_SRC V002 – Nhật ký sự kiện, phiên đăng nhập, lần truy cập môn gần nhất
-- Nguồn cấu trúc: Moodle 3.9 (admin/tool/log/store/standard/db/install.xml, lib/db/install.xml)
-- =============================================================================

-- ---------------------------------------------------------------- mdl_logstore_standard_log
CREATE TABLE mdl_logstore_standard_log (
    id                BIGSERIAL    PRIMARY KEY,
    eventname         VARCHAR(255) NOT NULL DEFAULT '',
    component         VARCHAR(100) NOT NULL DEFAULT '',
    action            VARCHAR(100) NOT NULL DEFAULT '',
    target            VARCHAR(100) NOT NULL DEFAULT '',
    objecttable       VARCHAR(50),
    objectid          BIGINT,
    crud              VARCHAR(1)   NOT NULL DEFAULT '',
    edulevel          SMALLINT     NOT NULL,
    contextid         BIGINT       NOT NULL,
    contextlevel      BIGINT       NOT NULL,
    contextinstanceid BIGINT       NOT NULL,
    userid            BIGINT       NOT NULL,
    courseid          BIGINT,
    relateduserid     BIGINT,
    anonymous         SMALLINT     NOT NULL DEFAULT 0,
    other             TEXT,
    timecreated       BIGINT       NOT NULL,
    origin            VARCHAR(10),
    ip                VARCHAR(45),
    realuserid        BIGINT
);
-- Index gốc của logstore_standard trong Moodle 3.9
CREATE INDEX mdl_logsstanlog_tim_ix ON mdl_logstore_standard_log (timecreated);
CREATE INDEX mdl_logsstanlog_couanotim_ix ON mdl_logstore_standard_log (courseid, anonymous, timecreated);
CREATE INDEX mdl_logsstanlog_useconconcr_ix ON mdl_logstore_standard_log
    (userid, contextlevel, contextinstanceid, crud, edulevel, timecreated);
CREATE INDEX mdl_logsstanlog_con_ix ON mdl_logstore_standard_log (contextid);
COMMENT ON TABLE mdl_logstore_standard_log IS 'Sự kiện nghiệp vụ Moodle (không phải HTTP request). Bảng lớn nhất, ETL đọc tăng dần theo id';
COMMENT ON COLUMN mdl_logstore_standard_log.crud IS 'c=create, r=read, u=update, d=delete';
COMMENT ON COLUMN mdl_logstore_standard_log.origin IS 'web | cli | ws (web service / ứng dụng di động) | restore';

-- ---------------------------------------------------------------- mdl_sessions
CREATE TABLE mdl_sessions (
    id           BIGSERIAL    PRIMARY KEY,
    state        BIGINT       NOT NULL DEFAULT 0,
    sid          VARCHAR(128) NOT NULL DEFAULT '',
    userid       BIGINT       NOT NULL,
    sessdata     TEXT,
    timecreated  BIGINT       NOT NULL,
    timemodified BIGINT       NOT NULL,
    firstip      VARCHAR(45),
    lastip       VARCHAR(45),
    CONSTRAINT mdl_sess_sid_uix UNIQUE (sid)
);
CREATE INDEX mdl_sess_sta_ix ON mdl_sessions (state);
CREATE INDEX mdl_sess_tim_ix ON mdl_sessions (timecreated);
CREATE INDEX mdl_sess_tim2_ix ON mdl_sessions (timemodified);
CREATE INDEX mdl_sess_use_ix ON mdl_sessions (userid);
COMMENT ON TABLE mdl_sessions IS 'Phiên đăng nhập hiện hành. timemodified trong 5 phút gần nhất = đang online';

-- ---------------------------------------------------------------- mdl_user_lastaccess
CREATE TABLE mdl_user_lastaccess (
    id         BIGSERIAL PRIMARY KEY,
    userid     BIGINT    NOT NULL DEFAULT 0,
    courseid   BIGINT    NOT NULL DEFAULT 0,
    timeaccess BIGINT    NOT NULL DEFAULT 0,
    CONSTRAINT mdl_userlast_usecou_uix UNIQUE (userid, courseid)
);
CREATE INDEX mdl_userlast_use_ix ON mdl_user_lastaccess (userid);
CREATE INDEX mdl_userlast_cou_ix ON mdl_user_lastaccess (courseid);
