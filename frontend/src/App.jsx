import { Spin } from "antd";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { homePath, useAuth } from "./auth/AuthContext.jsx";
import AdminLayout from "./layouts/AdminLayout.jsx";
import TeacherLayout from "./layouts/TeacherLayout.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ProtectedRoute from "./routes/ProtectedRoute.jsx";

const AdminOverview = lazy(() => import("./pages/admin/AdminOverview.jsx"));
const AdminTraffic = lazy(() => import("./pages/admin/AdminTraffic.jsx"));
const AdminReports = lazy(() => import("./pages/admin/AdminReports.jsx"));
const TeacherHome = lazy(() => import("./pages/teacher/TeacherHome.jsx"));
const TeacherRisk = lazy(() => import("./pages/teacher/TeacherRisk.jsx"));
const TeacherProgress = lazy(() => import("./pages/teacher/TeacherProgress.jsx"));

export function PageSpinner() {
  return <div style={{ display: "grid", placeItems: "center", minHeight: 320 }}><Spin size="large" /></div>;
}

function RootRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homePath(user) : "/login"} replace />;
}

const lazyPage = (Page) => <Suspense fallback={<PageSpinner />}><Page /></Suspense>;

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin" element={<ProtectedRoute role="ADMIN"><AdminLayout /></ProtectedRoute>}>
        <Route index element={lazyPage(AdminOverview)} />
        <Route path="traffic" element={lazyPage(AdminTraffic)} />
        <Route path="reports" element={lazyPage(AdminReports)} />
      </Route>
      <Route path="/teacher" element={<ProtectedRoute role="TEACHER"><TeacherLayout /></ProtectedRoute>}>
        <Route index element={lazyPage(TeacherHome)} />
        <Route path="courses/:courseId" element={<Navigate to="risk" replace />} />
        <Route path="courses/:courseId/risk" element={lazyPage(TeacherRisk)} />
        <Route path="courses/:courseId/progress" element={lazyPage(TeacherProgress)} />
      </Route>
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}
