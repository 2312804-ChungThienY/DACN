import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client.js";
import { homePath, useAuth } from "../auth/AuthContext.jsx";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={homePath(user)} replace />;

  async function onFinish({ username, password }) {
    setSubmitting(true);
    setError(null);
    try {
      const signedIn = await login(username.trim(), password);
      const from = location.state?.from;
      const allowed = from && from.startsWith(signedIn.role === "ADMIN" ? "/admin" : "/teacher");
      navigate(allowed ? from : homePath(signedIn), { replace: true });
    } catch (err) {
      setError(await errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <Card className="login-card" variant="borderless">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <span className="app-logo-mark" style={{ color: "#fff" }} aria-hidden>📊</span>
          <Typography.Title level={3} style={{ margin: 0 }}>LMS Analytics</Typography.Title>
        </div>
        <Typography.Paragraph type="secondary">
          Trực quan hóa dữ liệu Moodle – Khoa Công nghệ Thông tin, Trường Đại học Đà Lạt
        </Typography.Paragraph>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
        <Form layout="vertical" onFinish={onFinish} requiredMark={false} disabled={submitting}>
          <Form.Item label="Tên đăng nhập" name="username" rules={[{ required: true, message: "Nhập tên đăng nhập" }]}>
            <Input autoComplete="username" autoFocus placeholder="vd: gv.tranminhhung" />
          </Form.Item>
          <Form.Item label="Mật khẩu" name="password" rules={[{ required: true, message: "Nhập mật khẩu" }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>Đăng nhập</Button>
        </Form>
      </Card>
    </div>
  );
}
