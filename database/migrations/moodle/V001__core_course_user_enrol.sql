-- =============================================================================
-- MOODLE_SRC V001 – Bảng lõi: danh mục, khóa học, người dùng, ghi danh, vai trò, nhóm
-- Nguồn cấu trúc: Moodle 3.9 (lib/db/install.xml) – https://moodleschema.zoola.io/
--
-- "Rút gọn" nghĩa là: chỉ tạo các bảng mà ETL/mock data dùng (SPEC Phần 1.1) và
-- chỉ giữ các cột cần thiết + cột NOT NULL quan trọng. Tên bảng, tên cột, kiểu dữ liệu,
-- giá trị mặc định và index giữ ĐÚNG như Moodle 3.9 trên PostgreSQL để câu SQL
-- trích xuất chạy được nguyên vẹn trên Moodle thật.
-- Giống Moodle: KHÔNG có khóa ngoại vật lý (Moodle quản lý quan hệ ở tầng ứng dụng).
-- Quy ước kiểu XMLDB -> PostgreSQL: int(1..4)=SMALLINT, int(5..9)=INTEGER, int(10)=BIGINT.
-- =============================================================================

-- ---------------------------------------------------------------- mdl_course_categories
CREATE TABLE mdl_course_categories (
    id                BIGSERIAL    PRIMARY KEY,
    name              VARCHAR(255) NOT NULL DEFAULT '',
    idnumber          VARCHAR(100),
    description       TEXT,
    descriptionformat SMALLINT     NOT NULL DEFAULT 0,
    parent            BIGINT       NOT NULL DEFAULT 0,
    sortorder         BIGINT       NOT NULL DEFAULT 0,
    coursecount       BIGINT       NOT NULL DEFAULT 0,
    visible           SMALLINT     NOT NULL DEFAULT 1,
    visibleold        SMALLINT     NOT NULL DEFAULT 1,
    timemodified      BIGINT       NOT NULL DEFAULT 0,
    depth             BIGINT       NOT NULL DEFAULT 0,
    path              VARCHAR(255) NOT NULL DEFAULT '',
    theme             VARCHAR(50)
);
CREATE INDEX mdl_courcate_par_ix ON mdl_course_categories (parent);
COMMENT ON TABLE mdl_course_categories IS 'Danh mục khóa học. depth=1: Khoa; path dạng /<khoa>/<bo_mon>';

-- ---------------------------------------------------------------- mdl_course
CREATE TABLE mdl_course (
    id                BIGSERIAL    PRIMARY KEY,
    category          BIGINT       NOT NULL DEFAULT 0,
    sortorder         BIGINT       NOT NULL DEFAULT 0,
    fullname          VARCHAR(254) NOT NULL DEFAULT '',
    shortname         VARCHAR(255) NOT NULL DEFAULT '',
    idnumber          VARCHAR(100) NOT NULL DEFAULT '',
    summary           TEXT,
    summaryformat     SMALLINT     NOT NULL DEFAULT 0,
    format            VARCHAR(21)  NOT NULL DEFAULT 'topics',
    showgrades        SMALLINT     NOT NULL DEFAULT 1,
    newsitems         INTEGER      NOT NULL DEFAULT 1,
    startdate         BIGINT       NOT NULL DEFAULT 0,
    enddate           BIGINT       NOT NULL DEFAULT 0,
    relativedatesmode SMALLINT     NOT NULL DEFAULT 0,
    marker            BIGINT       NOT NULL DEFAULT 0,
    maxbytes          BIGINT       NOT NULL DEFAULT 0,
    showreports       SMALLINT     NOT NULL DEFAULT 0,
    visible           SMALLINT     NOT NULL DEFAULT 1,
    visibleold        SMALLINT     NOT NULL DEFAULT 1,
    groupmode         SMALLINT     NOT NULL DEFAULT 0,
    groupmodeforce    SMALLINT     NOT NULL DEFAULT 0,
    defaultgroupingid BIGINT       NOT NULL DEFAULT 0,
    lang              VARCHAR(30)  NOT NULL DEFAULT '',
    timecreated       BIGINT       NOT NULL DEFAULT 0,
    timemodified      BIGINT       NOT NULL DEFAULT 0,
    enablecompletion  SMALLINT     NOT NULL DEFAULT 0,
    completionnotify  SMALLINT     NOT NULL DEFAULT 0,
    cacherev          BIGINT       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_cour_cat_ix ON mdl_course (category);
CREATE INDEX mdl_cour_idn_ix ON mdl_course (idnumber);
CREATE INDEX mdl_cour_sho_ix ON mdl_course (shortname);
CREATE INDEX mdl_cour_sor_ix ON mdl_course (sortorder);
COMMENT ON TABLE mdl_course IS 'Khóa học (môn học). id=1 là site course (trang chủ), không phải môn học';

-- ---------------------------------------------------------------- mdl_user
CREATE TABLE mdl_user (
    id                BIGSERIAL    PRIMARY KEY,
    auth              VARCHAR(20)  NOT NULL DEFAULT 'manual',
    confirmed         SMALLINT     NOT NULL DEFAULT 0,
    policyagreed      SMALLINT     NOT NULL DEFAULT 0,
    deleted           SMALLINT     NOT NULL DEFAULT 0,
    suspended         SMALLINT     NOT NULL DEFAULT 0,
    mnethostid        BIGINT       NOT NULL DEFAULT 0,
    username          VARCHAR(100) NOT NULL DEFAULT '',
    password          VARCHAR(255) NOT NULL DEFAULT '',
    idnumber          VARCHAR(255) NOT NULL DEFAULT '',
    firstname         VARCHAR(100) NOT NULL DEFAULT '',
    lastname          VARCHAR(100) NOT NULL DEFAULT '',
    email             VARCHAR(100) NOT NULL DEFAULT '',
    phone1            VARCHAR(20)  NOT NULL DEFAULT '',
    institution       VARCHAR(255) NOT NULL DEFAULT '',
    department        VARCHAR(255) NOT NULL DEFAULT '',
    city              VARCHAR(120) NOT NULL DEFAULT '',
    country           VARCHAR(2)   NOT NULL DEFAULT '',
    lang              VARCHAR(30)  NOT NULL DEFAULT 'en',
    timezone          VARCHAR(100) NOT NULL DEFAULT '99',
    firstaccess       BIGINT       NOT NULL DEFAULT 0,
    lastaccess        BIGINT       NOT NULL DEFAULT 0,
    lastlogin         BIGINT       NOT NULL DEFAULT 0,
    currentlogin      BIGINT       NOT NULL DEFAULT 0,
    lastip            VARCHAR(45)  NOT NULL DEFAULT '',
    timecreated       BIGINT       NOT NULL DEFAULT 0,
    timemodified      BIGINT       NOT NULL DEFAULT 0,
    CONSTRAINT mdl_user_mneuse_uix UNIQUE (mnethostid, username)
);
CREATE INDEX mdl_user_del_ix ON mdl_user (deleted);
CREATE INDEX mdl_user_con_ix ON mdl_user (confirmed);
CREATE INDEX mdl_user_fir_ix ON mdl_user (firstname);
CREATE INDEX mdl_user_las_ix ON mdl_user (lastname);
CREATE INDEX mdl_user_lasacc_ix ON mdl_user (lastaccess);
CREATE INDEX mdl_user_ema_ix ON mdl_user (email);
CREATE INDEX mdl_user_aut_ix ON mdl_user (auth);
CREATE INDEX mdl_user_idn_ix ON mdl_user (idnumber);
COMMENT ON COLUMN mdl_user.idnumber IS 'Mã số sinh viên (MSSV) / mã cán bộ';

-- ---------------------------------------------------------------- mdl_role
CREATE TABLE mdl_role (
    id          BIGSERIAL    PRIMARY KEY,
    name        VARCHAR(255) NOT NULL DEFAULT '',
    shortname   VARCHAR(100) NOT NULL DEFAULT '',
    description TEXT         NOT NULL DEFAULT '',
    sortorder   BIGINT       NOT NULL DEFAULT 0,
    archetype   VARCHAR(30)  NOT NULL DEFAULT '',
    CONSTRAINT mdl_role_sor_uix UNIQUE (sortorder),
    CONSTRAINT mdl_role_sho_uix UNIQUE (shortname)
);

-- ---------------------------------------------------------------- mdl_context
CREATE TABLE mdl_context (
    id           BIGSERIAL    PRIMARY KEY,
    contextlevel BIGINT       NOT NULL DEFAULT 0,
    instanceid   BIGINT       NOT NULL DEFAULT 0,
    path         VARCHAR(255),
    depth        SMALLINT     NOT NULL DEFAULT 0,
    locked       SMALLINT     NOT NULL DEFAULT 0,
    CONSTRAINT mdl_cont_conins_uix UNIQUE (contextlevel, instanceid)
);
CREATE INDEX mdl_cont_ins_ix ON mdl_context (instanceid);
CREATE INDEX mdl_cont_pat_ix ON mdl_context (path);
COMMENT ON COLUMN mdl_context.contextlevel IS '10=system, 40=category, 50=course, 70=module';

-- ---------------------------------------------------------------- mdl_role_assignments
CREATE TABLE mdl_role_assignments (
    id           BIGSERIAL    PRIMARY KEY,
    roleid       BIGINT       NOT NULL DEFAULT 0,
    contextid    BIGINT       NOT NULL DEFAULT 0,
    userid       BIGINT       NOT NULL DEFAULT 0,
    timemodified BIGINT       NOT NULL DEFAULT 0,
    modifierid   BIGINT       NOT NULL DEFAULT 0,
    component    VARCHAR(100) NOT NULL DEFAULT '',
    itemid       BIGINT       NOT NULL DEFAULT 0,
    sortorder    BIGINT       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_roleassi_sor_ix ON mdl_role_assignments (sortorder);
CREATE INDEX mdl_roleassi_rol_ix ON mdl_role_assignments (roleid);
CREATE INDEX mdl_roleassi_con_ix ON mdl_role_assignments (contextid);
CREATE INDEX mdl_roleassi_use_ix ON mdl_role_assignments (userid);
CREATE INDEX mdl_roleassi_rolcon_ix ON mdl_role_assignments (roleid, contextid);
CREATE INDEX mdl_roleassi_useconrol_ix ON mdl_role_assignments (userid, contextid, roleid);
CREATE INDEX mdl_roleassi_comiteuse_ix ON mdl_role_assignments (component, itemid, userid);

-- ---------------------------------------------------------------- mdl_enrol
CREATE TABLE mdl_enrol (
    id             BIGSERIAL    PRIMARY KEY,
    enrol          VARCHAR(20)  NOT NULL DEFAULT '',
    status         BIGINT       NOT NULL DEFAULT 0,
    courseid       BIGINT       NOT NULL,
    sortorder      BIGINT       NOT NULL DEFAULT 0,
    name           VARCHAR(255),
    enrolperiod    BIGINT                DEFAULT 0,
    enrolstartdate BIGINT                DEFAULT 0,
    enrolenddate   BIGINT                DEFAULT 0,
    roleid         BIGINT                DEFAULT 0,
    timecreated    BIGINT       NOT NULL DEFAULT 0,
    timemodified   BIGINT       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_enro_enr_ix ON mdl_enrol (enrol);
CREATE INDEX mdl_enro_cou_ix ON mdl_enrol (courseid);
COMMENT ON COLUMN mdl_enrol.status IS '0 = phương thức ghi danh đang bật';

-- ---------------------------------------------------------------- mdl_user_enrolments
CREATE TABLE mdl_user_enrolments (
    id           BIGSERIAL PRIMARY KEY,
    status       BIGINT    NOT NULL DEFAULT 0,
    enrolid      BIGINT    NOT NULL,
    userid       BIGINT    NOT NULL,
    timestart    BIGINT    NOT NULL DEFAULT 0,
    timeend      BIGINT    NOT NULL DEFAULT 2147483647,
    modifierid   BIGINT    NOT NULL DEFAULT 0,
    timecreated  BIGINT    NOT NULL DEFAULT 0,
    timemodified BIGINT    NOT NULL DEFAULT 0,
    CONSTRAINT mdl_userenro_enruse_uix UNIQUE (enrolid, userid)
);
CREATE INDEX mdl_userenro_enr_ix ON mdl_user_enrolments (enrolid);
CREATE INDEX mdl_userenro_use_ix ON mdl_user_enrolments (userid);
CREATE INDEX mdl_userenro_mod_ix ON mdl_user_enrolments (modifierid);
COMMENT ON COLUMN mdl_user_enrolments.status IS '0 = ghi danh hiệu lực, 1 = bị tạm dừng';

-- ---------------------------------------------------------------- mdl_groups / mdl_groups_members
CREATE TABLE mdl_groups (
    id                BIGSERIAL    PRIMARY KEY,
    courseid          BIGINT       NOT NULL,
    idnumber          VARCHAR(100) NOT NULL DEFAULT '',
    name              VARCHAR(254) NOT NULL DEFAULT '',
    description       TEXT,
    descriptionformat SMALLINT     NOT NULL DEFAULT 0,
    enrolmentkey      VARCHAR(50),
    picture           BIGINT       NOT NULL DEFAULT 0,
    hidepicture       SMALLINT     NOT NULL DEFAULT 0,
    timecreated       BIGINT       NOT NULL DEFAULT 0,
    timemodified      BIGINT       NOT NULL DEFAULT 0
);
CREATE INDEX mdl_grou_cou_ix ON mdl_groups (courseid);
CREATE INDEX mdl_grou_idn_ix ON mdl_groups (idnumber);

CREATE TABLE mdl_groups_members (
    id        BIGSERIAL    PRIMARY KEY,
    groupid   BIGINT       NOT NULL DEFAULT 0,
    userid    BIGINT       NOT NULL DEFAULT 0,
    timeadded BIGINT       NOT NULL DEFAULT 0,
    component VARCHAR(100) NOT NULL DEFAULT '',
    itemid    BIGINT       NOT NULL DEFAULT 0,
    CONSTRAINT mdl_groumemb_usegro_uix UNIQUE (userid, groupid)
);
CREATE INDEX mdl_groumemb_gro_ix ON mdl_groups_members (groupid);
CREATE INDEX mdl_groumemb_use_ix ON mdl_groups_members (userid);
