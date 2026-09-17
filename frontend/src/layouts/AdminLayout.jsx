import { Outlet } from "react-router-dom";
import AppHeader from "../components/AppHeader.jsx";

const LINKS = [
  { to: "/admin", label: "Tổng quan", end: true },
  { to: "/admin/traffic", label: "Lưu lượng" },
  { to: "/admin/reports", label: "Báo cáo" },
];

/** SPEC 5.2: LOGO · [Tổng quan] [Lưu lượng] [Báo cáo] · Cập nhật · 👤 Admin */
export default function AdminLayout() {
  return (
    <>
      <AppHeader links={LINKS} />
      <main className="page"><Outlet /></main>
    </>
  );
}
