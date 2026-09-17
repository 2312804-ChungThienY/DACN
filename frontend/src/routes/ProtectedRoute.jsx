import { Navigate, useLocation } from "react-router-dom";
import { homePath, useAuth } from "../auth/AuthContext.jsx";

/** Chặn trang theo vai trò (SPEC 5.5 "routes/ProtectedRoute.jsx"). API vẫn kiểm tra quyền độc lập. */
export default function ProtectedRoute({ role, children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (role && user.role !== role) return <Navigate to={homePath(user)} replace />;
  return children;
}
