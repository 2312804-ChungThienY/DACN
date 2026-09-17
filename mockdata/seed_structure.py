"""
Dựng CẤU TRÚC Moodle giả lập trong moodle_src (SPEC Phần 3.1 – dòng "Cây Khoa → Môn", "Người dùng, ghi danh").

Tạo: vai trò, loại hoạt động, Khoa CNTT + 4 bộ môn, 15 môn học, 8 giảng viên, 500 sinh viên,
ghi danh, phân vai trò, chương/tuần, trang bài giảng, diễn đàn, bài tập, hoạt động điểm danh,
buổi học, trạng thái điểm danh, nhóm – kèm các ca biên (SV bị khóa/xóa, ghi danh bị dừng/hết hạn,
bài nộp nhóm, buổi học theo nhóm, môn chưa có buổi điểm danh).

Hành vi (log, bài nộp, điểm danh...) do generate_activity.py sinh ở bước sau.

Cách dùng:
    python -m mockdata.seed_structure            # chỉ chạy khi moodle_src còn trống
    python -m mockdata.seed_structure --reset    # xóa toàn bộ dữ liệu mdl_* rồi dựng lại
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np

from mockdata import config as cfg
from mockdata.db import (ACTIVITY_TABLES, STRUCTURE_TABLES, analyze_tables, connect, copy_rows, count_rows,
                         sync_sequence, truncate)
from mockdata.names import vietnamese_names

CONTEXT_SYSTEM, CONTEXT_CATEGORY, CONTEXT_COURSE, CONTEXT_MODULE = 10, 40, 50, 70
ROLES = [  # (id, shortname, name, archetype) – đúng thứ tự vai trò mặc định của Moodle
    (1, "manager", "Quản lý", "manager"), (2, "coursecreator", "Người tạo khóa học", "coursecreator"),
    (3, "editingteacher", "Giảng viên", "editingteacher"), (4, "teacher", "Trợ giảng", "teacher"),
    (5, "student", "Sinh viên", "student"), (6, "guest", "Khách", "guest"),
    (7, "user", "Người dùng đã xác thực", "user"), (8, "frontpage", "Người dùng trang chủ", "frontpage"),
]
ROLE_ID = {shortname: rid for rid, shortname, _, _ in ROLES}
MODULES = ["assign", "attendance", "forum", "page"]
MODULE_ID = {name: i + 1 for i, name in enumerate(MODULES)}


def ts(dt) -> int:
    return int(dt.timestamp())


@dataclass
class Tables:
    """Gom các dòng của từng bảng; id được cấp tường minh để liên kết giữa các bảng trước khi COPY."""
    rows: dict[str, list[dict]] = field(default_factory=dict)

    def add(self, table: str, **values) -> int:
        bucket = self.rows.setdefault(table, [])
        values.setdefault("id", len(bucket) + 1)
        bucket.append(values)
        return values["id"]


def build_structure(rng: np.random.Generator) -> Tables:
    t = Tables()
    created = ts(cfg.STRUCTURE_CREATED_AT)

    # ------------------------------------------------------------------ vai trò, loại hoạt động
    for rid, shortname, name, archetype in ROLES:
        t.add("mdl_role", id=rid, shortname=shortname, name=name, description="", sortorder=rid, archetype=archetype)
    for name in MODULES:
        t.add("mdl_modules", id=MODULE_ID[name], name=name, visible=1)

    # ------------------------------------------------------------------ context hệ thống
    t.add("mdl_context", contextlevel=CONTEXT_SYSTEM, instanceid=0, path="/1", depth=1)

    def add_context(level: int, instance: int, parent_path: str) -> tuple[int, str]:
        ctx_id = len(t.rows["mdl_context"]) + 1
        path = f"{parent_path}/{ctx_id}"
        t.add("mdl_context", id=ctx_id, contextlevel=level, instanceid=instance, path=path, depth=path.count("/"))
        return ctx_id, path

    # ------------------------------------------------------------------ người dùng
    def add_user(username, lastname, firstname, email, idnumber="", suspended=0, deleted=0) -> int:
        return t.add("mdl_user", auth="manual", confirmed=1, mnethostid=1, username=username,
                     password="!mock-not-a-hash!", idnumber=idnumber, firstname=firstname, lastname=lastname,
                     email=email, lang="vi", timezone="Asia/Ho_Chi_Minh", city="Đà Lạt", country="VN",
                     suspended=suspended, deleted=deleted, timecreated=created, timemodified=created)

    add_user("guest", "Khách", "Người dùng", "")
    add_user("admin", "Quản trị", "Hệ thống", f"admin@{cfg.STAFF_EMAIL_DOMAIN}")
    teacher_ids = [add_user(u, last, first, f"{u.removeprefix('gv.')}@{cfg.STAFF_EMAIL_DOMAIN}", idnumber=f"CB{i + 1:04d}")
                   for i, (u, last, first) in enumerate(cfg.TEACHERS)]

    student_names = vietnamese_names(rng, cfg.N_STUDENTS)
    special = rng.choice(cfg.N_STUDENTS, size=cfg.SUSPENDED_STUDENTS + cfg.DELETED_STUDENTS, replace=False)
    suspended_idx = set(special[:cfg.SUSPENDED_STUDENTS].tolist())
    deleted_idx = set(special[cfg.SUSPENDED_STUDENTS:].tolist())
    student_ids = []
    for i, (lastname, firstname) in enumerate(student_names):
        code = str(cfg.STUDENT_CODE_START + i)
        student_ids.append(add_user(code, lastname, firstname, f"{code}@{cfg.STUDENT_EMAIL_DOMAIN}", idnumber=code,
                                    suspended=int(i in suspended_idx), deleted=int(i in deleted_idx)))

    # ------------------------------------------------------------------ danh mục: Khoa (cấp 1) > Bộ môn (cấp 2)
    fac_code, fac_name = cfg.FACULTY
    faculty_id = len(t.rows.get("mdl_course_categories", [])) + 1
    t.add("mdl_course_categories", id=faculty_id, name=fac_name, idnumber=fac_code, parent=0, sortorder=10000,
          depth=1, path=f"/{faculty_id}", timemodified=created)
    _, faculty_ctx_path = add_context(CONTEXT_CATEGORY, faculty_id, "/1")

    # site course (id = 1) như Moodle thật
    t.add("mdl_course", id=1, category=0, fullname="Hệ thống LMS – Trường Đại học Đà Lạt", shortname="DLU-LMS",
          format="site", startdate=0, enddate=0, visible=1, timecreated=created, timemodified=created)
    add_context(CONTEXT_COURSE, 1, "/1")

    start, end = ts(cfg.SEMESTER_START), ts(cfg.SEMESTER_END)
    courses: list[dict] = []
    for d_order, (dept_code, dept_name, dept_courses) in enumerate(cfg.DEPARTMENTS, start=1):
        dept_id = len(t.rows["mdl_course_categories"]) + 1
        t.add("mdl_course_categories", id=dept_id, name=dept_name, idnumber=f"{fac_code}-{dept_code}",
              parent=faculty_id, sortorder=10000 + d_order * 10, depth=2, path=f"/{faculty_id}/{dept_id}",
              coursecount=len(dept_courses), timemodified=created)
        _, dept_ctx_path = add_context(CONTEXT_CATEGORY, dept_id, faculty_ctx_path)
        for shortname, fullname in dept_courses:
            course_id = t.add("mdl_course", category=dept_id, sortorder=len(t.rows["mdl_course"]) * 10,
                              fullname=fullname, shortname=shortname, idnumber=f"{shortname}_{cfg.ACADEMIC_TERM_TAG}",
                              summary=f"Học phần {fullname} – {cfg.ACADEMIC_TERM_TAG}", format="weeks",
                              startdate=start, enddate=end, visible=1, enablecompletion=1, lang="vi",
                              timecreated=created, timemodified=created)
            ctx_id, ctx_path = add_context(CONTEXT_COURSE, course_id, dept_ctx_path)
            courses.append(dict(id=course_id, shortname=shortname, fullname=fullname, ctx_id=ctx_id, ctx_path=ctx_path))

    # ------------------------------------------------------------------ ghi danh & vai trò
    enrol_start = ts(cfg.ENROL_START)
    expired_end = start + cfg.EXPIRED_AFTER_WEEKS * cfg.WEEK
    manual_enrol: dict[int, int] = {}
    for c in courses:
        manual_enrol[c["id"]] = t.add("mdl_enrol", enrol="manual", status=0, courseid=c["id"], sortorder=0,
                                      roleid=ROLE_ID["student"], timecreated=created, timemodified=created)
        # phương thức tự ghi danh đang TẮT (status = 1) – ETL phải bỏ qua
        t.add("mdl_enrol", enrol="self", status=1, courseid=c["id"], sortorder=1, roleid=ROLE_ID["student"],
              timecreated=created, timemodified=created)

    def enrol_user(course: dict, user_id: int, role: str, status: int = 0, timeend: int = 2147483647) -> None:
        t.add("mdl_user_enrolments", status=status, enrolid=manual_enrol[course["id"]], userid=user_id,
              timestart=enrol_start, timeend=timeend, modifierid=2, timecreated=enrol_start, timemodified=enrol_start)
        t.add("mdl_role_assignments", roleid=ROLE_ID[role], contextid=course["ctx_id"], userid=user_id,
              timemodified=enrol_start, modifierid=2)

    by_shortname = {c["shortname"]: c for c in courses}
    for shortname, (main_idx, assistant_idxs) in cfg.COURSE_TEACHERS.items():
        enrol_user(by_shortname[shortname], teacher_ids[main_idx], "editingteacher")
        for idx in assistant_idxs:
            enrol_user(by_shortname[shortname], teacher_ids[idx], "teacher")

    popularity = rng.uniform(0.6, 1.4, size=len(courses))
    popularity /= popularity.sum()
    course_students: dict[int, list[int]] = {c["id"]: [] for c in courses}   # SV có ghi danh hiệu lực
    lo, hi = cfg.COURSES_PER_STUDENT
    for user_id in student_ids:
        picks = rng.choice(len(courses), size=int(rng.integers(lo, hi + 1)), replace=False, p=popularity)
        for course_idx in sorted(picks):
            course = courses[course_idx]
            r = rng.random()
            if r < cfg.SUSPENDED_ENROLMENT_RATE:
                enrol_user(course, user_id, "student", status=1)
            elif r < cfg.SUSPENDED_ENROLMENT_RATE + cfg.EXPIRED_ENROLMENT_RATE:
                enrol_user(course, user_id, "student", timeend=expired_end)
            else:
                enrol_user(course, user_id, "student")
                course_students[course["id"]].append(user_id)

    inactive_users = {student_ids[i] for i in suspended_idx | deleted_idx}

    # ------------------------------------------------------------------ nội dung từng môn
    for c in courses:
        _build_course_content(t, rng, c, [u for u in course_students[c["id"]] if u not in inactive_users],
                              add_context, created)

    return t


def _build_course_content(t: Tables, rng: np.random.Generator, course: dict, active_students: list[int],
                          add_context, created: int) -> None:
    course_id, shortname = course["id"], course["shortname"]
    start = cfg.SEMESTER_START

    section_ids = {}
    for number in range(cfg.SEMESTER_WEEKS + 1):
        name = "Thông tin chung" if number == 0 else f"Tuần {number}"
        section_ids[number] = t.add("mdl_course_sections", course=course_id, section=number, name=name,
                                    summary="", visible=1, timemodified=created)
    sequences: dict[int, list[int]] = {n: [] for n in section_ids}

    def add_cm(module: str, instance: int, section_no: int, completion: int = 0, completionview: int = 0,
               completionexpected: int = 0) -> int:
        cm_id = t.add("mdl_course_modules", course=course_id, module=MODULE_ID[module], instance=instance,
                      section=section_ids[section_no], added=created, visible=1, completion=completion,
                      completionview=completionview, completionexpected=completionexpected)
        add_context(CONTEXT_MODULE, cm_id, course["ctx_path"])
        sequences[section_no].append(cm_id)
        return cm_id

    # Diễn đàn trao đổi (không theo dõi hoàn thành)
    forum_id = t.add("mdl_forum", course=course_id, type="general", name="Diễn đàn trao đổi", intro="", timemodified=created)
    add_cm("forum", forum_id, 0)

    # Hoạt động điểm danh
    attendance_id = t.add("mdl_attendance", course=course_id, name="Điểm danh", grade=100, intro="", timemodified=created)
    add_cm("attendance", attendance_id, 0)
    status_ids = {}
    for acronym, description, grade in (("P", "Có mặt", 2), ("A", "Vắng", 0), ("L", "Đi trễ", 1), ("E", "Vắng có phép", 1)):
        status_ids[acronym] = t.add("mdl_attendance_statuses", attendanceid=attendance_id, acronym=acronym,
                                    description=description, grade=grade, visible=1, deleted=0, setnumber=0)

    # Trang bài giảng mỗi tuần – theo dõi hoàn thành khi xem (completion=2, completionview=1)
    for week in range(1, cfg.SEMESTER_WEEKS + 1):
        week_end = ts(start + timedelta(weeks=week)) - 1
        page_id = t.add("mdl_page", course=course_id, name=f"Bài giảng tuần {week}", intro="",
                        content=f"Nội dung bài giảng tuần {week} – {course['fullname']}", revision=1, timemodified=created)
        add_cm("page", page_id, week, completion=2, completionview=1, completionexpected=week_end)

    # Nhóm (ca biên): bài nộp nhóm hoặc buổi học theo nhóm
    group_members: dict[int, list[int]] = {}
    shuffled = list(rng.permutation(active_students)) if active_students else []
    if shortname in cfg.TEAM_SUBMISSION_COURSES:
        chunks = [shuffled[i:i + cfg.TEAM_SIZE] for i in range(0, len(shuffled), cfg.TEAM_SIZE)]
    elif shortname in cfg.LAB_GROUP_COURSES:
        chunks = [shuffled[i::cfg.LAB_GROUPS] for i in range(cfg.LAB_GROUPS)]
    else:
        chunks = []
    label = "Nhóm đồ án" if shortname in cfg.TEAM_SUBMISSION_COURSES else "Nhóm thực hành"
    for number, members in enumerate(chunks, start=1):
        group_id = t.add("mdl_groups", courseid=course_id, idnumber=f"{shortname}-G{number:02d}",
                         name=f"{label} {number:02d}", timecreated=created, timemodified=created)
        group_members[group_id] = [int(u) for u in members]
        for user_id in members:
            t.add("mdl_groups_members", groupid=group_id, userid=int(user_id), timeadded=ts(cfg.ENROL_START))

    # Bài tập: 5–8 bài, hạn nộp rải đều tuần 3–14 (Chủ nhật 23:59)
    n_assign = int(rng.integers(cfg.ASSIGNMENTS_PER_COURSE[0], cfg.ASSIGNMENTS_PER_COURSE[1] + 1))
    due_weeks = np.rint(np.linspace(*cfg.ASSIGNMENT_DUE_WEEKS, n_assign)).astype(int)
    team_index = n_assign // 2 if shortname in cfg.TEAM_SUBMISSION_COURSES else -1
    for k, week in enumerate(due_weeks, start=1):
        due = start + timedelta(weeks=int(week) - 1, days=6, hours=23, minutes=59)
        team = int(k - 1 == team_index)
        assign_id = t.add("mdl_assign", course=course_id, name="Đồ án nhóm" if team else f"Bài tập {k}", intro="",
                          duedate=ts(due), allowsubmissionsfromdate=ts(due - timedelta(days=cfg.ASSIGNMENT_OPEN_DAYS)),
                          cutoffdate=ts(due + timedelta(days=7)), grade=100, completionsubmit=1, submissiondrafts=0,
                          teamsubmission=team, preventsubmissionnotingroup=team, timemodified=created)
        add_cm("assign", assign_id, int(week), completion=2, completionexpected=ts(due))

    # Buổi học (điểm danh). lasttaken để NULL – generate_activity cập nhật khi "GV điểm danh".
    if shortname not in cfg.NO_ATTENDANCE_SESSION_COURSES:
        if shortname in cfg.LAB_GROUP_COURSES:
            # 1 buổi lý thuyết cả lớp + 1 buổi thực hành riêng cho mỗi nhóm, mỗi buổi một ngày khác nhau
            days = sorted(int(d) for d in rng.choice(5, size=1 + len(group_members), replace=False))
            weekly_slots = [(days[0], 0)] + [(days[i + 1], gid) for i, gid in enumerate(group_members)]
        else:
            per_week = int(rng.integers(cfg.ATTENDANCE_SESSIONS_PER_WEEK[0], cfg.ATTENDANCE_SESSIONS_PER_WEEK[1] + 1))
            weekly_slots = [(int(d), 0) for d in sorted(rng.choice(5, size=per_week, replace=False))]
        hour = int(rng.choice(cfg.ATTENDANCE_SLOT_HOURS))
        number = 0
        for week in range(cfg.SEMESTER_WEEKS):
            slots = weekly_slots
            for day, group_id in slots:
                number += 1
                sessdate = ts(start + timedelta(weeks=week, days=int(day), hours=hour))
                t.add("mdl_attendance_sessions", attendanceid=attendance_id, groupid=group_id, sessdate=sessdate,
                      duration=3 * 3600, lasttaken=None, lasttakenby=0, timemodified=created,
                      description=f"Buổi {number}" + (" (thực hành theo nhóm)" if group_id else ""),
                      statusset=0, calendarevent=1)

    for number, cm_ids in sequences.items():
        t.rows["mdl_course_sections"][section_ids[number] - 1]["sequence"] = ",".join(map(str, cm_ids))


def load(tables: Tables) -> dict[str, int]:
    """
    COPY theo từng nhóm dòng có CÙNG tập cột: cột nào dòng không khai báo sẽ nhận DEFAULT của Moodle
    (nếu gộp vào một DataFrame, ô thiếu thành NULL -> vi phạm NOT NULL hoặc biến cột số nguyên thành float).
    """
    counts = {}
    with connect() as conn:
        for table in STRUCTURE_TABLES:
            groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
            for row in tables.rows.get(table, []):
                groups[tuple(row)].append(row)
            counts[table] = sum(
                copy_rows(conn, table, columns, (tuple(r[c] for c in columns) for r in rows))
                for columns, rows in groups.items()
            )
            sync_sequence(conn, table)
    return counts


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Dựng cấu trúc Moodle giả lập trong moodle_src")
    parser.add_argument("--reset", action="store_true", help="xóa toàn bộ dữ liệu mdl_* trước khi dựng")
    args = parser.parse_args(argv)

    with connect() as conn:
        existing = count_rows(conn, "mdl_course")
        if existing and not args.reset:
            print(f"moodle_src đã có {existing} khóa học. Dùng --reset để dựng lại từ đầu.", file=sys.stderr)
            return 1
        if args.reset:
            truncate(conn, STRUCTURE_TABLES + ACTIVITY_TABLES)
            print("Đã xóa dữ liệu cũ trong moodle_src.")

    tables = build_structure(np.random.default_rng(cfg.RANDOM_SEED))
    counts = load(tables)
    analyze_tables(STRUCTURE_TABLES)
    for table, n in counts.items():
        print(f"  {table:<28} {n:>7,}")
    print("Hoàn tất dựng cấu trúc. Bước tiếp theo: python -m mockdata.generate_activity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
