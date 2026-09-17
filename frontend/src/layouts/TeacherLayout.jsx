import { Select } from "antd";
import { Outlet, useMatch, useNavigate } from "react-router-dom";
import { useTeacherCourses } from "../api/hooks.js";
import AppHeader from "../components/AppHeader.jsx";

/** SPEC 5.3: LOGO · Môn: [CT101 – Cơ sở dữ liệu ▼] · [Cảnh báo] [Tiến độ lớp] · 👤 GV */
export default function TeacherLayout() {
  const match = useMatch("/teacher/courses/:courseId/:tab");
  const courseId = match?.params.courseId;
  const tab = match?.params.tab ?? "risk";
  const navigate = useNavigate();
  const { data, isLoading } = useTeacherCourses();

  const links = courseId
    ? [{ to: `/teacher/courses/${courseId}/risk`, label: "Cảnh báo" },
      { to: `/teacher/courses/${courseId}/progress`, label: "Tiến độ lớp" }]
    : [];

  return (
    <>
      <AppHeader links={links}>
        <Select
          aria-label="Chọn môn học"
          style={{ width: 320, maxWidth: "40vw" }}
          loading={isLoading}
          value={courseId ? Number(courseId) : undefined}
          placeholder="Chọn môn học"
          onChange={(id) => navigate(`/teacher/courses/${id}/${tab}`)}
          options={(data?.items ?? []).map((c) => ({
            value: c.course_id,
            label: `${c.shortname} – ${c.fullname}`,
          }))}
          showSearch
          optionFilterProp="label"
          popupMatchSelectWidth={false}
        />
      </AppHeader>
      <main className="page"><Outlet /></main>
    </>
  );
}
