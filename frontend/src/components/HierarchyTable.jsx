/** Admin 1.1 – Bảng phân cấp drill-down Khoa ▸ Môn ▸ Sinh viên, breadcrumb "Tất cả › CNTT › CT101" (SPEC 5.2). */
import { Breadcrumb, Button, Card, Input, Progress, Segmented, Table, Tag } from "antd";
import { useState } from "react";
import { useCourseStudents, useEnrollmentByFaculty, useFacultyCourses } from "../api/hooks.js";
import { RISK, SERIES } from "../theme/tokens.js";
import { fmtDaysSince, fmtInt, fmtPercent } from "../utils/format.js";
import { Rate, RiskBadge } from "./common.jsx";

const rateBar = (value) => (
  <div style={{ minWidth: 150 }}>
    <Progress percent={Number(value)} size="small" strokeColor={SERIES.blue} format={(p) => fmtPercent(p)}
      aria-label={`Tỷ lệ tương tác ${fmtPercent(value)}`} />
  </div>
);
const redCount = (value) => (
  <span className="tabular"><span style={{ color: RISK.RED.color }} aria-hidden>{RISK.RED.icon} </span>{fmtInt(value)}</span>
);
const COURSE_SORT = { shortname: "shortname", fullname: "fullname", enrolled: "enrolled", active: "active", active_rate: "active_rate", red_count: "red_count" };

function FacultyLevel({ term, onPick }) {
  const { data, isLoading, isFetching } = useEnrollmentByFaculty(term);
  return (
    <Table
      rowKey="faculty_id" size="middle" loading={isLoading || isFetching} pagination={false}
      dataSource={data?.items ?? []} scroll={{ x: "max-content" }}
      onRow={(row) => ({ onClick: () => onPick(row), style: { cursor: "pointer" } })}
      columns={[
        { title: "Khoa", dataIndex: "faculty_name", render: (v) => <b>▸ {v}</b> },
        { title: "Số môn", dataIndex: "course_count", align: "right" },
        { title: "SV đăng ký", dataIndex: "enrolled", align: "right", render: fmtInt },
        { title: "SV tương tác", dataIndex: "active", align: "right", render: fmtInt },
        { title: "Tỷ lệ tương tác", dataIndex: "active_rate", render: rateBar },
        { title: "Nguy cơ đỏ", dataIndex: "red_count", align: "right", render: redCount },
      ]}
    />
  );
}

function CourseLevel({ faculty, term, onPick }) {
  const [sort, setSort] = useState({ field: "active_rate", order: "desc" });
  const { data, isLoading, isFetching } = useFacultyCourses(faculty.faculty_id, term, sort.field, sort.order);
  const sortOrder = (key) => (sort.field === key ? (sort.order === "asc" ? "ascend" : "descend") : null);
  return (
    <Table
      rowKey="course_id" size="middle" loading={isLoading || isFetching} pagination={false}
      dataSource={data?.items ?? []} scroll={{ x: "max-content" }}
      onChange={(_, __, sorter) => setSort(sorter.order
        ? { field: COURSE_SORT[sorter.columnKey], order: sorter.order === "ascend" ? "asc" : "desc" }
        : { field: "active_rate", order: "desc" })}
      columns={[
        { title: "Mã môn", key: "shortname", dataIndex: "shortname", sorter: true, sortOrder: sortOrder("shortname") },
        { title: "Tên môn", key: "fullname", dataIndex: "fullname", sorter: true, sortOrder: sortOrder("fullname") },
        { title: "Bộ môn", dataIndex: "category_name", responsive: ["lg"] },
        { title: "Đăng ký", key: "enrolled", dataIndex: "enrolled", align: "right", render: fmtInt, sorter: true, sortOrder: sortOrder("enrolled") },
        { title: "Tương tác", key: "active", dataIndex: "active", align: "right", render: fmtInt, sorter: true, sortOrder: sortOrder("active") },
        { title: "Tỷ lệ tương tác", key: "active_rate", dataIndex: "active_rate", render: rateBar, sorter: true, sortOrder: sortOrder("active_rate") },
        { title: "Nộp bài", dataIndex: "assignment_submission_rate", align: "right", render: (v) => <Rate value={v} /> },
        { title: "Chuyên cần", dataIndex: "attendance_rate", align: "right", render: (v) => <Rate value={v} /> },
        { title: "Nguy cơ đỏ", key: "red_count", dataIndex: "red_count", align: "right", render: redCount, sorter: true, sortOrder: sortOrder("red_count") },
        { title: "", key: "action", render: (_, row) => <Button size="small" onClick={() => onPick(row)}>Xem SV</Button> },
      ]}
    />
  );
}

function StudentLevel({ course }) {
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState({ current: 1, pageSize: 20 });
  const params = { status: status === "all" ? undefined : status, search: search || undefined, page: page.current, page_size: page.pageSize };
  const { data, isLoading, isFetching } = useCourseStudents(course.course_id, params);
  return (
    <>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12, alignItems: "center" }}>
        <Segmented value={status} onChange={(v) => { setStatus(v); setPage((p) => ({ ...p, current: 1 })); }}
          options={[{ label: "Tất cả", value: "all" }, { label: "Có tương tác", value: "active" }, { label: "Không tương tác", value: "inactive" }]} />
        <Input.Search allowClear placeholder="Tìm MSSV, họ tên, email" style={{ width: 280 }}
          onSearch={(v) => { setSearch(v.trim()); setPage((p) => ({ ...p, current: 1 })); }} />
        <span className="muted">
          {data && `${fmtInt(data.course.enrolled)} SV đăng ký · ${fmtInt(data.course.active)} có tương tác · snapshot ${data.snapshot_date}`}
        </span>
      </div>
      <Table
        rowKey="user_id" size="small" loading={isLoading || isFetching} dataSource={data?.items ?? []} scroll={{ x: "max-content" }}
        pagination={{ ...page, total: data?.total ?? 0, showSizeChanger: true, pageSizeOptions: [20, 50, 100, 200], showTotal: (t) => `${fmtInt(t)} sinh viên` }}
        onChange={(pagination) => setPage({ current: pagination.current, pageSize: pagination.pageSize })}
        columns={[
          { title: "MSSV", dataIndex: "student_code" },
          { title: "Họ tên", dataIndex: "student_name" },
          { title: "Email", dataIndex: "email", responsive: ["md"] },
          { title: "Tương tác", dataIndex: "is_active", render: (v) => (v ? <Tag color="blue">✔ Có</Tag> : <Tag>✘ Chưa</Tag>) },
          { title: "Lượt truy cập", dataIndex: "total_access_count", align: "right", render: fmtInt },
          { title: "7 ngày", dataIndex: "access_count_7d", align: "right", render: fmtInt },
          { title: "Truy cập cuối", dataIndex: "days_since_last_access", render: fmtDaysSince },
          { title: "Mức rủi ro", dataIndex: "risk_level", render: (v) => <RiskBadge level={v} /> },
          { title: "Điểm", dataIndex: "risk_score", align: "right" },
        ]}
      />
    </>
  );
}

export default function HierarchyTable({ term, path, onPathChange }) {
  const crumbs = [{ title: <a onClick={() => onPathChange({})}>Tất cả khoa</a> }];
  if (path.faculty) crumbs.push({ title: path.course ? <a onClick={() => onPathChange({ faculty: path.faculty })}>{path.faculty.faculty_name}</a> : path.faculty.faculty_name });
  if (path.course) crumbs.push({ title: `${path.course.shortname} – ${path.course.fullname}` });

  let level;
  if (path.course) level = <StudentLevel course={path.course} />;
  else if (path.faculty) level = <CourseLevel faculty={path.faculty} term={term} onPick={(course) => onPathChange({ ...path, course })} />;
  else level = <FacultyLevel term={term} onPick={(faculty) => onPathChange({ faculty })} />;

  return (
    <Card title="Thống kê phân cấp: Khoa ▸ Môn ▸ Sinh viên" extra={<Breadcrumb items={crumbs} />}>
      {level}
    </Card>
  );
}
