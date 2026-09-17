-- =============================================================================
-- MOODLE_SRC V003 – Cấu trúc nội dung môn học, bài tập, theo dõi hoàn thành
-- Nguồn cấu trúc: Moodle 3.9 (lib/db/install.xml, mod/assign, mod/page, mod/forum)
-- mdl_page, mdl_forum: bảng instance của hoạt động "Trang bài giảng" và "Diễn đàn"
-- (cần để mdl_course_modules.instance trỏ tới bản ghi có thật).
-- =============================================================================

-- ---------------------------------------------------------------- mdl_modules
CREATE TABLE mdl_modules (
    id       BIGSERIAL   PRIMARY KEY,
    name     VARCHAR(20) NOT NULL DEFAULT '',
    cron     BIGINT      NOT NULL DEFAULT 0,
    lastcron BIGINT      NOT NULL DEFAULT 0,
    search   VARCHAR(255) NOT NULL DEFAULT '',
    visible  SMALLINT    NOT NULL DEFAULT 1
);
CREATE INDEX mdl_modu_nam_ix ON mdl_modules (name);

-- ---------------------------------------------------------------- mdl_course_sections
CREATE TABLE mdl_course_sections (
    id            BIGSERIAL    PRIMARY KEY,
    course        BIGINT       NOT NULL DEFAULT 0,
    section       BIGINT       NOT NULL DEFAULT 0,
    name          VARCHAR(255),
    summary       TEXT,
    summaryformat SMALLINT     NOT NULL DEFAULT 0,
    sequence      TEXT,
    visible       SMALLINT     NOT NULL DEFAULT 1,
    availability  TEXT,
    timemodified  BIGINT       NOT NULL DEFAULT 0,
    CONSTRAINT mdl_coursect_cousec_uix UNIQUE (course, section)
);

-- ---------------------------------------------------------------- mdl_course_modules
CREATE TABLE mdl_course_modules (
    id                        BIGSERIAL    PRIMARY KEY,
    course                    BIGINT       NOT NULL DEFAULT 0,
    module                    BIGINT       NOT NULL DEFAULT 0,
    instance                  BIGINT       NOT NULL DEFAULT 0,
    section                   BIGINT       NOT NULL DEFAULT 0,
    idnumber                  VARCHAR(100),
    added                     BIGINT       NOT NULL DEFAULT 0,
    score                     SMALLINT     NOT NULL DEFAULT 0,
    indent                    INTEGER      NOT NULL DEFAULT 0,
    visible                   SMALLINT     NOT NULL DEFAULT 1,
    visibleoncoursepage       SMALLINT     NOT NULL DEFAULT 1,
    visibleold                SMALLINT     NOT NULL DEFAULT 1,
    groupmode                 SMALLINT     NOT NULL DEFAULT 0,
    groupingid                BIGINT       NOT NULL DEFAULT 0,
    completion                SMALLINT     NOT NULL DEFAULT 0,
    completiongradeitemnumber BIGINT,
    completionview            SMALLINT     NOT NULL DEFAULT 0,
    completionexpected        BIGINT       NOT NULL DEFAULT 0,
    showdescription           SMALLINT     NOT NULL DEFAULT 0,
    availability              TEXT,
    deletioninprogress        SMALLINT     NOT NULL DEFAULT 0
);
CREATE INDEX mdl_courmodu_vis_ix ON mdl_course_modules (visible);
CREATE INDEX mdl_courmodu_cou_ix ON mdl_course_modules (course);
CREATE INDEX mdl_courmodu_mod_ix ON mdl_course_modules (module);
CREATE INDEX mdl_courmodu_ins_ix ON mdl_course_modules (instance);
CREATE INDEX mdl_courmodu_idncou_ix ON mdl_course_modules (idnumber, course);
CREATE INDEX mdl_courmodu_gro_ix ON mdl_course_modules (groupingid);
COMMENT ON COLUMN mdl_course_modules.section IS 'mdl_course_sections.id (không phải số thứ tự chương)';
COMMENT ON COLUMN mdl_course_modules.completion IS '0 = không theo dõi, 1 = SV tự đánh dấu, 2 = tự động theo điều kiện';
COMMENT ON COLUMN mdl_course_modules.completionexpected IS 'Hạn hoàn thành dự kiến (epoch), 0 = không đặt';

-- ---------------------------------------------------------------- mdl_course_modules_completion
CREATE TABLE mdl_course_modules_completion (
    id              BIGSERIAL PRIMARY KEY,
    coursemoduleid  BIGINT    NOT NULL,
    userid          BIGINT    NOT NULL,
    completionstate SMALLINT  NOT NULL,
    viewed          SMALLINT,
    overrideby      BIGINT,
    timemodified    BIGINT    NOT NULL,
    CONSTRAINT mdl_courmoducomp_usecou_uix UNIQUE (userid, coursemoduleid)
);
CREATE INDEX mdl_courmoducomp_cou_ix ON mdl_course_modules_completion (coursemoduleid);
COMMENT ON COLUMN mdl_course_modules_completion.completionstate IS '0=chưa, 1=hoàn thành, 2=hoàn thành đạt, 3=hoàn thành không đạt';

-- ---------------------------------------------------------------- mdl_assign
CREATE TABLE mdl_assign (
    id                          BIGSERIAL    PRIMARY KEY,
    course                      BIGINT       NOT NULL DEFAULT 0,
    name                        VARCHAR(255) NOT NULL DEFAULT '',
    intro                       TEXT         NOT NULL,
    introformat                 SMALLINT     NOT NULL DEFAULT 0,
    alwaysshowdescription       SMALLINT     NOT NULL DEFAULT 0,
    nosubmissions               SMALLINT     NOT NULL DEFAULT 0,
    submissiondrafts            SMALLINT     NOT NULL DEFAULT 0,
    sendnotifications           SMALLINT     NOT NULL DEFAULT 0,
    sendlatenotifications       SMALLINT     NOT NULL DEFAULT 0,
    duedate                     BIGINT       NOT NULL DEFAULT 0,
    allowsubmissionsfromdate    BIGINT       NOT NULL DEFAULT 0,
    grade                       BIGINT       NOT NULL DEFAULT 0,
    timemodified                BIGINT       NOT NULL DEFAULT 0,
    requiresubmissionstatement  SMALLINT     NOT NULL DEFAULT 0,
    completionsubmit            SMALLINT     NOT NULL DEFAULT 0,
    cutoffdate                  BIGINT       NOT NULL DEFAULT 0,
    gradingduedate              BIGINT       NOT NULL DEFAULT 0,
    teamsubmission              SMALLINT     NOT NULL DEFAULT 0,
    requireallteammemberssubmit SMALLINT     NOT NULL DEFAULT 0,
    teamsubmissiongroupingid    BIGINT       NOT NULL DEFAULT 0,
    blindmarking                SMALLINT     NOT NULL DEFAULT 0,
    attemptreopenmethod         VARCHAR(10)  NOT NULL DEFAULT 'none',
    maxattempts                 INTEGER      NOT NULL DEFAULT -1,
    markingworkflow             SMALLINT     NOT NULL DEFAULT 0,
    preventsubmissionnotingroup SMALLINT     NOT NULL DEFAULT 0
);
CREATE INDEX mdl_assi_cou_ix ON mdl_assign (course);
CREATE INDEX mdl_assi_tea_ix ON mdl_assign (teamsubmissiongroupingid);

-- ---------------------------------------------------------------- mdl_assign_submission
CREATE TABLE mdl_assign_submission (
    id            BIGSERIAL   PRIMARY KEY,
    assignment    BIGINT      NOT NULL DEFAULT 0,
    userid        BIGINT      NOT NULL DEFAULT 0,
    timecreated   BIGINT      NOT NULL DEFAULT 0,
    timemodified  BIGINT      NOT NULL DEFAULT 0,
    status        VARCHAR(10),
    groupid       BIGINT      NOT NULL DEFAULT 0,
    attemptnumber BIGINT      NOT NULL DEFAULT 0,
    latest        SMALLINT    NOT NULL DEFAULT 0,
    CONSTRAINT mdl_assisubm_assusegroatt_uix UNIQUE (assignment, userid, groupid, attemptnumber)
);
CREATE INDEX mdl_assisubm_ass_ix ON mdl_assign_submission (assignment);
CREATE INDEX mdl_assisubm_use_ix ON mdl_assign_submission (userid);
CREATE INDEX mdl_assisubm_att_ix ON mdl_assign_submission (attemptnumber);
CREATE INDEX mdl_assisubm_assusegrolat_ix ON mdl_assign_submission (assignment, userid, groupid, latest);
COMMENT ON COLUMN mdl_assign_submission.status IS 'new | draft | submitted | reopened';
COMMENT ON COLUMN mdl_assign_submission.userid IS '0 khi là bài nộp theo nhóm (teamsubmission=1), khi đó groupid = nhóm';

-- ---------------------------------------------------------------- mdl_page
CREATE TABLE mdl_page (
    id            BIGSERIAL    PRIMARY KEY,
    course        BIGINT       NOT NULL DEFAULT 0,
    name          VARCHAR(255) NOT NULL DEFAULT '',
    intro         TEXT,
    introformat   SMALLINT     NOT NULL DEFAULT 0,
    content       TEXT,
    contentformat SMALLINT     NOT NULL DEFAULT 0,
    display       SMALLINT     NOT NULL DEFAULT 0,
    revision      BIGINT       NOT NULL DEFAULT 0,
    timemodified  BIGINT       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_page_cou_ix ON mdl_page (course);

-- ---------------------------------------------------------------- mdl_forum
CREATE TABLE mdl_forum (
    id           BIGSERIAL    PRIMARY KEY,
    course       BIGINT       NOT NULL DEFAULT 0,
    type         VARCHAR(20)  NOT NULL DEFAULT 'general',
    name         VARCHAR(255) NOT NULL DEFAULT '',
    intro        TEXT,
    introformat  SMALLINT     NOT NULL DEFAULT 0,
    timemodified BIGINT       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_foru_cou_ix ON mdl_forum (course);
