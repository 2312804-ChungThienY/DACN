"""
Sinh HÀNH VI học tập giả lập tính tới thời điểm AS_OF (SPEC Phần 3.2, 3.3).

Tiền điều kiện: đã chạy seed_structure.py (có khóa học, ghi danh, bài tập, buổi học...).
Sinh ra:
    mdl_logstore_standard_log      đăng nhập, xem môn/bài giảng/bài tập/diễn đàn, đăng bài, nộp bài, đăng nhập lỗi
    mdl_assign_submission          bài nộp cá nhân + bài nộp nhóm (userid = 0) + dòng 'new' (mở nhưng chưa nộp)
    mdl_attendance_log             kết quả điểm danh; cập nhật lasttaken của buổi đã điểm danh
    mdl_course_modules_completion  hoàn thành khi xem bài giảng / nộp bài
    mdl_user_lastaccess, mdl_user (firstaccess, lastaccess, lastlogin...), mdl_sessions (online tại AS_OF)
    mockdata/output/ground_truth_profiles.csv  "đáp án" hồ sơ hành vi để đo độ chính xác luật rủi ro

Mọi sự kiện có thời điểm <= AS_OF và < timeend của ghi danh. Không sinh dữ liệu "tương lai".

Cách dùng:
    python -m mockdata.generate_activity           # chỉ chạy khi chưa có dữ liệu hành vi
    python -m mockdata.generate_activity --reset   # xóa dữ liệu hành vi cũ rồi sinh lại
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

from common.settings import resolve_as_of
from mockdata import config as cfg
from mockdata.db import ACTIVITY_TABLES, analyze_tables, connect, copy_frame, count_rows, fetch_frame, truncate

# MOCK_OUTPUT_DIR: bộ dữ liệu đo hiệu năng ghi ground truth ra chỗ khác, không ghi đè đáp án của bộ demo
OUTPUT_DIR = Path(os.getenv("MOCK_OUTPUT_DIR") or Path(__file__).resolve().parent / "output")
SYSTEM_CONTEXT_ID = 1
LEVEL_SYSTEM, LEVEL_COURSE, LEVEL_MODULE = 10, 50, 70

# kind -> (eventname, component, action, target, objecttable, crud, edulevel)
EVENT_TEMPLATES: dict[str, tuple] = {
    "login":        ("\\core\\event\\user_loggedin", "core", "loggedin", "user", "user", "r", 0),
    "course_view":  ("\\core\\event\\course_viewed", "core", "viewed", "course", None, "r", 2),
    "page_view":    ("\\mod_page\\event\\course_module_viewed", "mod_page", "viewed", "course_module", "page", "r", 2),
    "assign_view":  ("\\mod_assign\\event\\course_module_viewed", "mod_assign", "viewed", "course_module", "assign", "r", 2),
    "forum_view":   ("\\mod_forum\\event\\course_module_viewed", "mod_forum", "viewed", "course_module", "forum", "r", 2),
    "forum_post":   ("\\mod_forum\\event\\post_created", "mod_forum", "created", "post", "forum_posts", "c", 2),
    "submitted":    ("\\mod_assign\\event\\assessable_submitted", "mod_assign", "submitted", "assessable", "assign_submission", "u", 2),
    "login_failed": ("\\core\\event\\user_login_failed", "core", "failed", "user_login", None, "r", 0),
}
KINDS = list(EVENT_TEMPLATES)
KIND = {name: i for i, name in enumerate(KINDS)}
TEMPLATE_FIELDS = ("eventname", "component", "action", "target", "objecttable", "crud", "edulevel")
LOG_COLUMNS = ["id", "eventname", "component", "action", "target", "objecttable", "objectid", "crud", "edulevel",
               "contextid", "contextlevel", "contextinstanceid", "userid", "courseid", "relateduserid", "anonymous",
               "other", "timecreated", "origin", "ip", "realuserid"]
LOGIN_EVENT = EVENT_TEMPLATES["login"][0]


# ============================================================================= đọc cấu trúc nguồn
@dataclass
class Source:
    enrol: pd.DataFrame      # courseid, course_ctx, userid, idnumber, active_until (+ profile, never, dropout)
    pages: pd.DataFrame      # courseid, cmid, ctxid, instance, week
    assigns: pd.DataFrame    # courseid, assignid, cmid, ctxid, duedate, allowfrom, teamsubmission
    forums: pd.DataFrame     # courseid, cmid, ctxid, instance
    sessions: pd.DataFrame   # sessionid, courseid, attendanceid, sessdate, groupid
    statuses: pd.DataFrame   # id, attendanceid, acronym
    groups: pd.DataFrame     # courseid, groupid, userid
    teachers: pd.DataFrame   # courseid, teacherid (GV chính)


ENROL_SQL = """
SELECT c.id AS courseid, ctx.id AS course_ctx, ue.userid, u.idnumber, ue.timeend
FROM mdl_course c
JOIN mdl_context ctx          ON ctx.instanceid = c.id AND ctx.contextlevel = 50
JOIN mdl_enrol e              ON e.courseid = c.id AND e.status = 0
JOIN mdl_user_enrolments ue   ON ue.enrolid = e.id AND ue.status = 0
JOIN mdl_role_assignments ra  ON ra.contextid = ctx.id AND ra.userid = ue.userid
JOIN mdl_role r               ON r.id = ra.roleid AND r.shortname = 'student'
JOIN mdl_user u               ON u.id = ue.userid AND u.deleted = 0 AND u.suspended = 0
WHERE c.id <> 1
ORDER BY c.id, ue.userid
"""
MODULE_SQL = """
SELECT cm.course AS courseid, cm.id AS cmid, cx.id AS ctxid, cm.instance, cs.section AS week
FROM mdl_course_modules cm
JOIN mdl_modules m          ON m.id = cm.module AND m.name = %(module)s
JOIN mdl_course_sections cs ON cs.id = cm.section
JOIN mdl_context cx         ON cx.instanceid = cm.id AND cx.contextlevel = 70
WHERE cm.visible = 1 AND cm.deletioninprogress = 0
ORDER BY cm.course, cs.section, cm.id
"""
ASSIGN_SQL = """
SELECT a.course AS courseid, a.id AS assignid, cm.id AS cmid, cx.id AS ctxid, a.duedate,
       a.allowsubmissionsfromdate AS allowfrom, a.teamsubmission
FROM mdl_assign a
JOIN mdl_course_modules cm ON cm.instance = a.id AND cm.course = a.course
JOIN mdl_modules m         ON m.id = cm.module AND m.name = 'assign'
JOIN mdl_context cx        ON cx.instanceid = cm.id AND cx.contextlevel = 70
WHERE cm.visible = 1 AND cm.deletioninprogress = 0
ORDER BY a.course, a.duedate, a.id
"""
SESSION_SQL = """
SELECT s.id AS sessionid, a.course AS courseid, a.id AS attendanceid, s.sessdate, s.groupid
FROM mdl_attendance_sessions s
JOIN mdl_attendance a ON a.id = s.attendanceid
ORDER BY a.course, s.sessdate, s.id
"""
TEACHER_SQL = """
SELECT ctx.instanceid AS courseid, MIN(ra.userid) AS teacherid
FROM mdl_role_assignments ra
JOIN mdl_role r      ON r.id = ra.roleid AND r.shortname = 'editingteacher'
JOIN mdl_context ctx ON ctx.id = ra.contextid AND ctx.contextlevel = 50
GROUP BY ctx.instanceid
"""


def load_source(conn: psycopg.Connection, as_of_ts: int) -> Source:
    enrol = fetch_frame(conn, ENROL_SQL)
    # cận trên (không bao gồm) cho mọi sự kiện của cặp SV–môn: sau AS_OF hoặc hết hạn ghi danh
    enrol["active_until"] = np.minimum(enrol["timeend"].to_numpy(), as_of_ts + 1)
    return Source(
        enrol=enrol.drop(columns="timeend"),
        pages=fetch_frame(conn, MODULE_SQL, {"module": "page"}),
        assigns=fetch_frame(conn, ASSIGN_SQL),
        forums=fetch_frame(conn, MODULE_SQL, {"module": "forum"}),
        sessions=fetch_frame(conn, SESSION_SQL),
        statuses=fetch_frame(conn, "SELECT id, attendanceid, acronym FROM mdl_attendance_statuses WHERE deleted = 0"),
        groups=fetch_frame(conn, "SELECT g.courseid, gm.groupid, gm.userid FROM mdl_groups_members gm "
                                 "JOIN mdl_groups g ON g.id = gm.groupid ORDER BY g.courseid, gm.groupid, gm.userid"),
        teachers=fetch_frame(conn, TEACHER_SQL),
    )


# ============================================================================= hồ sơ hành vi
def assign_profiles(enrol: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Mỗi SV có hồ sơ chung; mỗi cặp SV–môn giữ hồ sơ đó với xác suất 80%, còn lại bốc thăm lại."""
    names, probs = list(cfg.PROFILES), list(cfg.PROFILES.values())
    users = enrol["userid"].unique()
    base = dict(zip(users, rng.choice(names, size=len(users), p=probs)))
    n = len(enrol)
    keep = rng.random(n) < cfg.PROFILE_CONSISTENCY
    redraw = rng.choice(names, size=n, p=probs)
    enrol = enrol.copy()
    enrol["profile"] = np.where(keep, enrol["userid"].map(base), redraw)
    behaviour = enrol["profile"].map(cfg.BEHAVIOR)
    enrol["never"] = rng.random(n) < behaviour.map(lambda b: b["never"]).to_numpy()
    enrol["dropout"] = rng.random(n) < behaviour.map(lambda b: b["dropout"]).to_numpy()
    return enrol


def _profile_param(enrol: pd.DataFrame, key: str, index: int | None = None) -> np.ndarray:
    values = enrol["profile"].map(lambda p: cfg.BEHAVIOR[p][key])
    return (values.map(lambda v: v[index]) if index is not None else values).to_numpy()


# ============================================================================= phiên truy cập
def build_sessions(src: Source, rng: np.random.Generator, as_of_ts: int) -> pd.DataFrame:
    """Phiên học (enrol_idx, t0): theo tuần + cao điểm giữa kỳ + tăng đột biến 48h trước hạn nộp."""
    enrol = src.enrol
    start = int(cfg.SEMESTER_START.timestamp())
    n = len(enrol)
    lo, hi = _profile_param(enrol, "sessions_per_week", 0), _profile_param(enrol, "sessions_per_week", 1)
    never, dropout = enrol["never"].to_numpy(), enrol["dropout"].to_numpy()
    courses = enrol["courseid"].to_numpy()

    idx_parts: list[np.ndarray] = []
    time_parts: list[np.ndarray] = []
    last_week = min(cfg.SEMESTER_WEEKS - 1, (as_of_ts - start) // cfg.WEEK)
    for week in range(int(last_week) + 1):
        hi_w = np.where(dropout & (week >= cfg.DROPOUT_FROM_WEEK_INDEX), hi // cfg.DROPOUT_ACTIVITY_DIVISOR, hi)
        lo_w = np.minimum(lo, hi_w)
        counts = rng.integers(lo_w, hi_w + 1)
        if week + 1 == cfg.MIDTERM_WEEK:
            counts = np.rint(counts * cfg.MIDTERM_FACTOR).astype(np.int64)
        counts[never] = 0
        idx = np.repeat(np.arange(n), counts)
        day = rng.choice(7, size=idx.size, p=cfg.DOW_P)
        hour = rng.choice(24, size=idx.size, p=cfg.HOUR_P)
        idx_parts.append(idx)
        time_parts.append(start + week * cfg.WEEK + day * cfg.DAY + hour * 3600 + rng.integers(0, 3600, size=idx.size))

    mean_weekly = (lo + hi) / 2
    for a in src.assigns.itertuples():
        members = np.flatnonzero((courses == a.courseid) & ~never)
        if members.size == 0:
            continue
        lam = mean_weekly[members] * (cfg.DEADLINE_WINDOW_DAYS / 7) * (cfg.DEADLINE_FACTOR - 1)
        if (a.duedate - start) // cfg.WEEK >= cfg.DROPOUT_FROM_WEEK_INDEX:
            lam = np.where(dropout[members], lam / cfg.DROPOUT_ACTIVITY_DIVISOR, lam)
        idx = np.repeat(members, rng.poisson(lam))
        due_midnight = start + ((a.duedate - start) // cfg.DAY) * cfg.DAY
        t0 = (due_midnight - rng.integers(0, cfg.DEADLINE_WINDOW_DAYS, size=idx.size) * cfg.DAY
              + rng.choice(24, size=idx.size, p=cfg.HOUR_P) * 3600 + rng.integers(0, 3600, size=idx.size))
        keep = t0 < a.duedate
        idx_parts.append(idx[keep])
        time_parts.append(t0[keep])

    idx = np.concatenate(idx_parts)
    t0 = np.concatenate(time_parts)
    keep = t0 < enrol["active_until"].to_numpy()[idx]
    return (pd.DataFrame({"enrol_idx": idx[keep], "t0": t0[keep]})
            .sort_values(["t0", "enrol_idx"], kind="stable").reset_index(drop=True))


# ============================================================================= sự kiện trong phiên
def _ips(rng: np.random.Generator, size: int) -> np.ndarray:
    a, b = rng.integers(0, 256, size=size), rng.integers(1, 255, size=size)
    return np.array([f"{cfg.MOCK_IP_PREFIX}{x}.{y}" for x, y in zip(a, b)], dtype=object)


def build_session_events(src: Source, sessions: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    enrol = src.enrol
    start = int(cfg.SEMESTER_START.timestamp())
    e_idx, t0 = sessions["enrol_idx"].to_numpy(), sessions["t0"].to_numpy()
    n_sessions = len(sessions)

    # mỗi phiên = 1 đăng nhập + n thao tác trong môn (thao tác đầu tiên là vào trang môn học)
    per_session = rng.integers(cfg.ACTIONS_PER_SESSION[0], cfg.ACTIONS_PER_SESSION[1] + 1, size=n_sessions) + 1
    sess = np.repeat(np.arange(n_sessions), per_session)
    offsets = np.cumsum(per_session) - per_session
    order = np.arange(sess.size) - offsets[sess]
    gaps = rng.integers(cfg.ACTION_GAP_SECONDS[0], cfg.ACTION_GAP_SECONDS[1] + 1, size=sess.size)
    gaps[order == 0] = 0
    cum = np.cumsum(gaps)
    t = t0[sess] + cum - cum[offsets][sess]

    row_enrol = e_idx[sess]
    post_rate = _profile_param(enrol, "post_rate")[row_enrol]
    u = rng.random(sess.size)
    page_cut = cfg.ACTION_MIX["page"]
    assign_cut = page_cut + cfg.ACTION_MIX["assign"]
    kind = np.select(
        [order == 0, order == 1, u < page_cut, u < assign_cut, u < 1 - post_rate],
        [KIND["login"], KIND["course_view"], KIND["page_view"], KIND["assign_view"], KIND["forum_view"]],
        default=KIND["forum_post"],
    )

    courseid = enrol["courseid"].to_numpy()[row_enrol]
    userid = enrol["userid"].to_numpy()[row_enrol]
    is_login = kind == KIND["login"]
    contextid = np.where(is_login, SYSTEM_CONTEXT_ID, enrol["course_ctx"].to_numpy()[row_enrol])
    contextlevel = np.where(is_login, LEVEL_SYSTEM, LEVEL_COURSE)
    instanceid = np.where(is_login, 0, courseid)
    objectid = np.where(is_login, userid, -1)
    week_idx = np.clip((t - start) // cfg.WEEK, 0, cfg.SEMESTER_WEEKS - 1)

    for cid in np.unique(courseid):
        in_course = courseid == cid
        # Bài tập: chỉ xem được bài đã mở nộp; nếu chưa bài nào mở thì chuyển sang xem bài giảng
        course_assigns = src.assigns[src.assigns["courseid"] == cid].sort_values("allowfrom")
        sel = np.flatnonzero(in_course & (kind == KIND["assign_view"]))
        available = np.searchsorted(course_assigns["allowfrom"].to_numpy(), t[sel], side="right")
        kind[sel[available == 0]] = KIND["page_view"]
        chosen, pick_from = sel[available > 0], available[available > 0]
        pick = (rng.random(chosen.size) * pick_from).astype(int)
        contextid[chosen] = course_assigns["ctxid"].to_numpy()[pick]
        instanceid[chosen] = course_assigns["cmid"].to_numpy()[pick]
        objectid[chosen] = course_assigns["assignid"].to_numpy()[pick]
        contextlevel[chosen] = LEVEL_MODULE

        # Bài giảng: 50% xem bài của tuần hiện tại, 50% xem lại một tuần đã qua
        course_pages = src.pages[src.pages["courseid"] == cid].sort_values("week")
        sel = np.flatnonzero(in_course & (kind == KIND["page_view"]))
        current = np.minimum(week_idx[sel], len(course_pages) - 1)
        pick = np.where(rng.random(sel.size) < 0.5, current, (rng.random(sel.size) * (current + 1)).astype(int))
        contextid[sel] = course_pages["ctxid"].to_numpy()[pick]
        instanceid[sel] = course_pages["cmid"].to_numpy()[pick]
        objectid[sel] = course_pages["instance"].to_numpy()[pick]
        contextlevel[sel] = LEVEL_MODULE

        # Diễn đàn
        forum = src.forums[src.forums["courseid"] == cid].iloc[0]
        sel = np.flatnonzero(in_course & np.isin(kind, [KIND["forum_view"], KIND["forum_post"]]))
        contextid[sel], instanceid[sel], contextlevel[sel] = forum["ctxid"], forum["cmid"], LEVEL_MODULE
        objectid[sel] = np.where(kind[sel] == KIND["forum_view"], forum["instance"], -1)

    session_origin = np.where(rng.random(n_sessions) < cfg.MOBILE_SESSION_RATE, "ws", "web")
    session_ip = _ips(rng, n_sessions)
    idnumber = enrol["idnumber"].to_numpy()[row_enrol]
    events = pd.DataFrame({
        "kind": kind, "objectid": objectid, "contextid": contextid, "contextlevel": contextlevel,
        "contextinstanceid": instanceid, "userid": userid, "courseid": np.where(is_login, 0, courseid),
        "timecreated": t, "origin": session_origin[sess], "ip": session_ip[sess],
        "other": np.where(is_login, pd.Series(idnumber).map(lambda s: f'{{"username":"{s}"}}').to_numpy(), "null"),
    })
    events = events[t < enrol["active_until"].to_numpy()[row_enrol]]

    # Đăng nhập lỗi (userid = 0) ngay trước một số phiên
    failed = np.flatnonzero(rng.random(n_sessions) < cfg.FAILED_LOGIN_RATE)
    failed_events = pd.DataFrame({
        "kind": KIND["login_failed"], "objectid": -1, "contextid": SYSTEM_CONTEXT_ID, "contextlevel": LEVEL_SYSTEM,
        "contextinstanceid": 0, "userid": 0, "courseid": 0,
        "timecreated": t0[failed] - rng.integers(5, 60, size=failed.size),
        "origin": session_origin[failed], "ip": session_ip[failed],
        "other": [f'{{"username":"{enrol["idnumber"].iat[i]}","reason":3}}' for i in e_idx[failed]],
    })
    return pd.concat([events, failed_events], ignore_index=True)


# ============================================================================= bài nộp
def _submission_time(duedate: int, allowfrom: int, late_prob: float, rng: np.random.Generator) -> int:
    if rng.random() < late_prob:
        t = duedate + int(rng.integers(3600, 3 * cfg.DAY))
    else:
        t = duedate - int(rng.integers(600, 3 * cfg.DAY))
    return max(t, allowfrom + 600)


def build_submissions(src: Source, rng: np.random.Generator, as_of_ts: int):
    """Trả về (submissions, completion, submit_events)."""
    enrol, start = src.enrol, int(cfg.SEMESTER_START.timestamp())
    subs: list[dict] = []
    completion: list[tuple[int, int, int]] = []           # (userid, cmid, time)
    events: list[dict] = []

    def add_submission(assign, userid: int, groupid: int, t: int, status: str, submitter: int | None = None,
                       submitter_ip: str | None = None) -> None:
        sub_id = len(subs) + 1
        created = t if status == "new" else max(t - 3600, int(assign.allowfrom))
        subs.append(dict(id=sub_id, assignment=int(assign.assignid), userid=userid, timecreated=created,
                         timemodified=t, status=status, groupid=groupid, attemptnumber=0, latest=1))
        if status == "submitted":
            events.append(dict(kind=KIND["submitted"], objectid=sub_id, contextid=int(assign.ctxid),
                               contextlevel=LEVEL_MODULE, contextinstanceid=int(assign.cmid), userid=submitter,
                               courseid=int(assign.courseid), timecreated=t, origin="web", ip=submitter_ip,
                               other='{"submission_editable":true}'))

    groups_by_course = {cid: g for cid, g in src.groups.groupby("courseid")}
    for cid, course_assigns in src.assigns.groupby("courseid"):
        members = enrol[enrol["courseid"] == cid]
        individual = course_assigns[course_assigns["teamsubmission"] == 0]
        due_ids = individual.loc[individual["duedate"] <= as_of_ts, "assignid"].tolist()

        for e in members.itertuples():
            if e.never:
                continue
            behaviour = cfg.BEHAVIOR[e.profile]
            red_keep: set[int] = set()
            if e.profile == "RED" and due_ids:
                size = int(len(due_ids) * cfg.RED_MAX_SUBMIT_RATIO)
                red_keep = set(int(x) for x in rng.choice(due_ids, size=size, replace=False))
            ip = _ips(rng, 1)[0]
            for a in individual.itertuples():
                if e.profile == "RED":
                    will_submit = (a.assignid in red_keep) if a.duedate <= as_of_ts else rng.random() < cfg.RED_FUTURE_SUBMIT_PROB
                else:
                    p = behaviour["submit"]
                    if e.dropout and (a.duedate - start) // cfg.WEEK >= cfg.DROPOUT_FROM_WEEK_INDEX:
                        p *= cfg.DROPOUT_SUBMIT_FACTOR
                    will_submit = rng.random() < p
                t = _submission_time(int(a.duedate), int(a.allowfrom), behaviour["late"], rng) if will_submit else None
                if t is not None and t < e.active_until:
                    add_submission(a, int(e.userid), 0, t, "submitted", int(e.userid), ip)
                    completion.append((int(e.userid), int(a.cmid), t))
                else:
                    open_until = min(int(e.active_until), int(a.duedate))
                    if a.allowfrom < open_until and rng.random() < cfg.NEW_SUBMISSION_ROW_RATE:
                        add_submission(a, int(e.userid), 0, int(rng.integers(a.allowfrom, open_until)), "new")

        team = course_assigns[course_assigns["teamsubmission"] == 1]
        course_groups = groups_by_course.get(cid)
        if team.empty or course_groups is None:
            continue
        for a in team.itertuples():
            for groupid, group in course_groups.groupby("groupid"):
                group_members = members[members["userid"].isin(group["userid"])]
                eligible = group_members[~group_members["never"]]
                if eligible.empty:
                    continue
                p = 0.9 if eligible["profile"].isin(["GREEN", "YELLOW"]).any() else 0.3
                if rng.random() >= p:
                    continue
                submitter = eligible.iloc[int(rng.integers(len(eligible)))]
                t = _submission_time(int(a.duedate), int(a.allowfrom), 0.10, rng)
                if t >= submitter["active_until"]:
                    continue
                add_submission(a, 0, int(groupid), t, "submitted", int(submitter["userid"]), _ips(rng, 1)[0])
                completion.extend((int(m.userid), int(a.cmid), t)
                                  for m in group_members.itertuples() if t < m.active_until)

    return (pd.DataFrame(subs), pd.DataFrame(completion, columns=["userid", "cmid", "time"]), pd.DataFrame(events))


# ============================================================================= điểm danh
def build_attendance(src: Source, rng: np.random.Generator, as_of_ts: int) -> pd.DataFrame:
    enrol, start = src.enrol, int(cfg.SEMESTER_START.timestamp())
    taken = src.sessions[src.sessions["sessdate"] + cfg.ATTENDANCE_TAKEN_DELAY <= as_of_ts]
    teacher_of = dict(zip(src.teachers["courseid"], src.teachers["teacherid"]))
    frames = []
    for cid, course_sessions in taken.groupby("courseid"):
        members = enrol.loc[enrol["courseid"] == cid, ["courseid", "userid", "profile", "dropout", "active_until"]]
        pairs = course_sessions.merge(members, on="courseid")
        pairs = pairs[pairs["sessdate"] < pairs["active_until"]]
        in_group = pairs[pairs["groupid"] != 0].merge(src.groups[["groupid", "userid"]], on=["groupid", "userid"])
        pairs = pd.concat([pairs[pairs["groupid"] == 0], in_group]).sort_values(["sessdate", "userid"], kind="stable")

        p = pairs["profile"].map(lambda x: cfg.BEHAVIOR[x]["attend"]).to_numpy()
        late_phase = pairs["dropout"].to_numpy() & (pairs["sessdate"].to_numpy() >= start + cfg.DROPOUT_FROM_WEEK_INDEX * cfg.WEEK)
        p = np.where(late_phase, p * cfg.DROPOUT_ATTEND_FACTOR, p)
        r = rng.random(len(pairs))
        acronym = np.select([r < p, r < p + 0.03, r < p + 0.05], ["P", "L", "E"], default="A")

        attendance_id = int(course_sessions["attendanceid"].iat[0])
        statuses = src.statuses[src.statuses["attendanceid"] == attendance_id]
        status_id = dict(zip(statuses["acronym"], statuses["id"]))
        keep = rng.random(len(pairs)) >= cfg.MISSING_ATTENDANCE_LOG_RATE
        frames.append(pd.DataFrame({
            "sessionid": pairs["sessionid"].to_numpy(), "studentid": pairs["userid"].to_numpy(),
            "statusid": [int(status_id[a]) for a in acronym],
            "statusset": ",".join(str(int(i)) for i in statuses["id"]),
            "timetaken": pairs["sessdate"].to_numpy() + cfg.ATTENDANCE_TAKEN_DELAY,
            "takenby": int(teacher_of[cid]), "remarks": "", "ipaddress": "",
        })[keep])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ============================================================================= ghép & nạp
def assemble_logs(parts: list[pd.DataFrame]) -> pd.DataFrame:
    logs = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    logs = logs.sort_values(["timecreated", "userid"], kind="stable").reset_index(drop=True)
    for i, name in enumerate(TEMPLATE_FIELDS):
        values = np.array([EVENT_TEMPLATES[k][i] for k in KINDS], dtype=object)
        logs[name] = values[logs["kind"].to_numpy()]
    logs["id"] = np.arange(1, len(logs) + 1)
    logs["objectid"] = logs["objectid"].astype("Int64").mask(logs["objectid"] < 0)
    logs["relateduserid"] = None
    logs["realuserid"] = None
    logs["anonymous"] = 0
    return logs[LOG_COLUMNS]


def build_completion(events: pd.DataFrame, assign_completion: pd.DataFrame) -> pd.DataFrame:
    page_views = events.loc[events["kind"] == KIND["page_view"], ["userid", "contextinstanceid", "timecreated"]]
    page_views = page_views.rename(columns={"contextinstanceid": "cmid", "timecreated": "time"})
    merged = pd.concat([page_views, assign_completion], ignore_index=True)
    first = merged.groupby(["userid", "cmid"], as_index=False)["time"].min().sort_values(["time", "userid"])
    return pd.DataFrame({
        "id": np.arange(1, len(first) + 1), "coursemoduleid": first["cmid"].to_numpy(),
        "userid": first["userid"].to_numpy(), "completionstate": 1, "viewed": 1,
        "overrideby": None, "timemodified": first["time"].to_numpy(),
    })


DERIVED_SQL = [
    # GV "điểm danh" các buổi đã diễn ra
    """
    UPDATE mdl_attendance_sessions s
    SET lasttaken = s.sessdate + %(delay)s, lasttakenby = tch.teacherid, timemodified = s.sessdate + %(delay)s
    FROM mdl_attendance a
    JOIN (""" + TEACHER_SQL + """) tch ON tch.courseid = a.course
    WHERE a.id = s.attendanceid AND s.sessdate + %(delay)s <= %(as_of)s
    """,
    # Lần truy cập môn gần nhất
    """
    INSERT INTO mdl_user_lastaccess (userid, courseid, timeaccess)
    SELECT userid, courseid, MAX(timecreated)
    FROM mdl_logstore_standard_log
    WHERE courseid > 1 AND userid > 0
    GROUP BY userid, courseid
    """,
    # Thông tin truy cập trên hồ sơ người dùng
    """
    WITH acc AS (
        SELECT userid, MIN(timecreated) AS firstaccess, MAX(timecreated) AS lastaccess
        FROM mdl_logstore_standard_log WHERE userid > 0 GROUP BY userid
    ), logins AS (
        SELECT userid, timecreated, ip,
               ROW_NUMBER() OVER (PARTITION BY userid ORDER BY timecreated DESC, id DESC) AS rn
        FROM mdl_logstore_standard_log WHERE eventname = %(login_event)s
    )
    UPDATE mdl_user u
    SET firstaccess = acc.firstaccess, lastaccess = acc.lastaccess,
        currentlogin = COALESCE(l1.timecreated, 0), lastlogin = COALESCE(l2.timecreated, 0),
        lastip = COALESCE(l1.ip, '')
    FROM acc
    LEFT JOIN logins l1 ON l1.userid = acc.userid AND l1.rn = 1
    LEFT JOIN logins l2 ON l2.userid = acc.userid AND l2.rn = 2
    WHERE u.id = acc.userid
    """,
    # Phiên còn hiệu lực tại AS_OF (dùng cho "người dùng online")
    """
    INSERT INTO mdl_sessions (state, sid, userid, sessdata, timecreated, timemodified, firstip, lastip)
    SELECT 0, md5(userid::text || '-' || %(as_of)s::text), userid, NULL, MIN(timecreated), MAX(timecreated),
           (array_agg(ip ORDER BY timecreated, id))[1], (array_agg(ip ORDER BY timecreated DESC, id DESC))[1]
    FROM mdl_logstore_standard_log
    WHERE userid > 0 AND timecreated > %(as_of)s - %(timeout)s AND timecreated <= %(as_of)s
    GROUP BY userid
    """,
]


def reset_activity(conn: psycopg.Connection) -> None:
    truncate(conn, ACTIVITY_TABLES)
    conn.execute("UPDATE mdl_attendance_sessions SET lasttaken = NULL, lasttakenby = 0")
    conn.execute("UPDATE mdl_user SET firstaccess = 0, lastaccess = 0, lastlogin = 0, currentlogin = 0, lastip = ''")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sinh hành vi học tập giả lập tới thời điểm AS_OF")
    parser.add_argument("--reset", action="store_true", help="xóa dữ liệu hành vi cũ trước khi sinh")
    args = parser.parse_args(argv)

    as_of = resolve_as_of()
    as_of_ts = int(as_of.timestamp())
    if as_of <= cfg.SEMESTER_START:
        print(f"AS_OF = {as_of.isoformat()} chưa tới ngày bắt đầu học kỳ {cfg.SEMESTER_START.date()} – "
              "không có hành vi nào để sinh. Kiểm tra LMS_AS_OF trong .env.", file=sys.stderr)
        return 1

    started = time.perf_counter()
    with connect() as conn:
        if count_rows(conn, "mdl_course") <= 1:
            print("moodle_src chưa có cấu trúc. Chạy trước: python -m mockdata.seed_structure", file=sys.stderr)
            return 1
        if count_rows(conn, "mdl_logstore_standard_log") and not args.reset:
            print("moodle_src đã có dữ liệu hành vi. Dùng --reset để sinh lại.", file=sys.stderr)
            return 1

        rng = np.random.default_rng(cfg.RANDOM_SEED + 1)
        src = load_source(conn, as_of_ts)
        src.enrol = assign_profiles(src.enrol, rng)

        sessions = build_sessions(src, rng, as_of_ts)
        events = build_session_events(src, sessions, rng)
        submissions, assign_completion, submit_events = build_submissions(src, rng, as_of_ts)
        attendance = build_attendance(src, rng, as_of_ts)
        completion = build_completion(events, assign_completion)
        logs = assemble_logs([events, submit_events])
        print(f"Đã sinh trong bộ nhớ sau {time.perf_counter() - started:.1f}s – bắt đầu nạp vào moodle_src...")

        if args.reset:
            reset_activity(conn)
        counts = {
            "mdl_logstore_standard_log": copy_frame(conn, "mdl_logstore_standard_log", logs),
            "mdl_assign_submission": copy_frame(conn, "mdl_assign_submission", submissions),
            "mdl_attendance_log": copy_frame(conn, "mdl_attendance_log", attendance),
            "mdl_course_modules_completion": copy_frame(conn, "mdl_course_modules_completion", completion),
        }
        params = {"as_of": as_of_ts, "delay": cfg.ATTENDANCE_TAKEN_DELAY, "timeout": cfg.ONLINE_SESSION_TIMEOUT,
                  "login_event": LOGIN_EVENT}
        for statement in DERIVED_SQL:
            conn.execute(statement, params)
        for table in ("mdl_logstore_standard_log", "mdl_assign_submission", "mdl_attendance_log",
                      "mdl_course_modules_completion"):
            conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                         f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
        for table in ("mdl_user_lastaccess", "mdl_sessions"):
            counts[table] = count_rows(conn, table)

    # Cập nhật thống kê ngay sau khi nạp hàng loạt để planner có số liệu đúng cho ETL chạy ngay sau đó,
    # không phụ thuộc thời điểm autovacuum/autoanalyze.
    analyze_tables(ACTIVITY_TABLES + ("mdl_attendance_sessions", "mdl_user"))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    truth = src.enrol[["courseid", "userid", "profile", "never", "dropout"]]
    truth.to_csv(OUTPUT_DIR / "ground_truth_profiles.csv", index=False)

    print(f"AS_OF = {as_of.isoformat()}")
    for table, n in counts.items():
        print(f"  {table:<32} {n:>10,}")
    share = truth["profile"].value_counts(normalize=True).mul(100).round(1).to_dict()
    print(f"  Hồ sơ SV–môn: {share}  | chưa từng truy cập: {int(truth['never'].sum())}")
    print(f"Hoàn tất sau {time.perf_counter() - started:.1f}s. Ground truth: {OUTPUT_DIR / 'ground_truth_profiles.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
