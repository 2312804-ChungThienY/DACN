import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import dayjs from "dayjs";
import "dayjs/locale/vi";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./auth/AuthContext.jsx";
import "./charts/setup.js";
import "./styles.css";
import { FONT_FAMILY, UI_PRIMARY } from "./theme/tokens.js";

dayjs.locale("vi");

const NO_RETRY_STATUSES = [400, 401, 403, 404, 422, 429];
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => count < 1 && !NO_RETRY_STATUSES.includes(error?.response?.status),
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

// Màu giao diện đạt tương phản WCAG AA (>= 4,5:1 cho chữ thường) – kiểm tra bằng axe-core trong e2e/tests/a11y.spec.js.
// Nút chính dùng xanh đậm hơn một bậc so với màu chuỗi dữ liệu (#2a78d6 + chữ trắng chỉ đạt 4,47:1).
const theme = {
  token: {
    colorPrimary: UI_PRIMARY, fontFamily: FONT_FAMILY, colorBgLayout: "#f5f7fb", borderRadius: 8, colorText: "#1f2937",
    colorTextSecondary: "#52514e", colorTextDescription: "#5c5b57", colorTextPlaceholder: "#6f6e69",
    colorTextDisabled: "#8a8984",
  },
  components: { Card: { headerFontSize: 15 }, Table: { headerBg: "#f7f7f5" } },
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={viVN} theme={theme}>
        <AntApp>
          <BrowserRouter>
            <AuthProvider>
              <App />
            </AuthProvider>
          </BrowserRouter>
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
