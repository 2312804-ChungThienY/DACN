import { Button, Dropdown, Tooltip } from "antd";
import { NavLink } from "react-router-dom";
import { useEtlStatus, useFilters } from "../api/hooks.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { fmtDateTime } from "../utils/format.js";

const ROLE_LABEL = { ADMIN: "Quản trị viên", TEACHER: "Giảng viên" };
const JOB_LABEL = {
  traffic: "Lưu lượng (5 phút)", course_progress: "Tiến độ môn (mỗi giờ)", student_risk: "Cảnh báo (2 giờ)",
  nightly: "Chốt số liệu đêm", maintenance: "Bảo trì tuần", backfill: "Nạp lịch sử",
};

function DataFreshness() {
  const { data: filters } = useFilters();
  const { data: jobs } = useEtlStatus();
  const latest = (jobs ?? []).map((j) => j.last_success_at).filter(Boolean).sort().at(-1);
  const detail = (
    <div style={{ fontSize: 12 }}>
      <div>Thời điểm tham chiếu dữ liệu: <b>{fmtDateTime(filters?.as_of)}</b></div>
      {(jobs ?? []).map((j) => (
        <div key={j.job_name}>{JOB_LABEL[j.job_name] ?? j.job_name}: {j.last_success_at ? fmtDateTime(j.last_success_at) : "chưa chạy"}</div>
      ))}
    </div>
  );
  return (
    <Tooltip title={detail} placement="bottomRight">
      <span className="updated" style={{ cursor: "help" }}>
        Dữ liệu: {fmtDateTime(filters?.as_of)} · ETL cập nhật: {latest ? fmtDateTime(latest) : "–"}
      </span>
    </Tooltip>
  );
}

export default function AppHeader({ links, children }) {
  const { user, logout } = useAuth();
  const menu = {
    items: [
      { key: "who", label: `${user.full_name ?? user.username} – ${ROLE_LABEL[user.role]}`, disabled: true },
      { type: "divider" },
      { key: "logout", label: "Đăng xuất", danger: true },
    ],
    onClick: ({ key }) => key === "logout" && logout(),
  };
  return (
    <header className="app-header">
      <div className="app-logo"><span className="app-logo-mark" aria-hidden>📊</span>LMS Analytics</div>
      {children}
      <nav className="app-nav" aria-label="Điều hướng chính">
        {links.map((link) => <NavLink key={link.to} to={link.to} end={link.end}>{link.label}</NavLink>)}
      </nav>
      <div className="app-header-meta">
        <DataFreshness />
        <Dropdown menu={menu} trigger={["click"]}>
          <Button type="text" style={{ color: "#fff" }} aria-label="Tài khoản">👤 {user.full_name ?? user.username}</Button>
        </Dropdown>
      </div>
    </header>
  );
}
