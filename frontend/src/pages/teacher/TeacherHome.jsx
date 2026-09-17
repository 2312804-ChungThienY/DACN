import { Alert, Result, Spin } from "antd";
import { Navigate } from "react-router-dom";
import { errorText } from "../../api/client.js";
import { useTeacherCourses } from "../../api/hooks.js";

/** Vào trang giảng viên -> mở môn đầu tiên. */
export default function TeacherHome() {
  const { data, isLoading, error } = useTeacherCourses();
  if (isLoading) return <div style={{ display: "grid", placeItems: "center", minHeight: 320 }}><Spin size="large" /></div>;
  if (error) return <Alert type="error" showIcon message={errorText(error)} />;
  if (!data.items.length) return <Result status="info" title="Bạn chưa được phân công môn học nào" subTitle="Liên hệ quản trị viên nếu thông tin chưa đúng." />;
  return <Navigate to={`/teacher/courses/${data.items[0].course_id}/risk`} replace />;
}
