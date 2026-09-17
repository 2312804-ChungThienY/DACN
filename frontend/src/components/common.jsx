/** Thành phần giao diện nhỏ dùng chung: huy hiệu rủi ro, thẻ KPI, khung biểu đồ có chế độ xem bảng. */
import { Alert, Card, Segmented, Skeleton, Table } from "antd";
import { useState } from "react";
import { errorText } from "../api/client.js";
import { RISK } from "../theme/tokens.js";
import { NO_DATA, fmtPercent } from "../utils/format.js";

/** Đèn giao thông: biểu tượng + chữ, không bao giờ chỉ có màu (SPEC 5.4). */
export function RiskBadge({ level, iconOnly = false }) {
  const risk = RISK[level];
  if (!risk) return null;
  return (
    <span className="risk-badge" style={{ background: risk.tint, color: risk.ink }} title={risk.label}>
      <span aria-hidden style={{ color: risk.color }}>{risk.icon}</span>
      {iconOnly ? <span className="sr-only" style={{ position: "absolute", left: -9999 }}>{risk.label}</span> : risk.label}
    </span>
  );
}

export function KpiCard({ label, value, hint, loading, accent, children }) {
  return (
    <Card size="small" style={{ height: "100%", borderTop: accent ? `3px solid ${accent}` : undefined }}>
      <div className="kpi-label">{label}</div>
      {loading ? <Skeleton.Input active size="small" style={{ marginTop: 8 }} /> : <div className="kpi-value">{value}</div>}
      {hint && <div className="kpi-hint">{hint}</div>}
      {children}
    </Card>
  );
}

/** Tỷ lệ %: null hiển thị "Chưa có dữ liệu" (khác 0%). */
export function Rate({ value, digits = 1 }) {
  return value == null ? <span className="no-data">{NO_DATA}</span> : <span className="tabular">{fmtPercent(value, digits)}</span>;
}

/**
 * Khung biểu đồ: tiêu đề, phụ đề, nút chuyển "Biểu đồ | Bảng" (mọi giá trị trên biểu đồ đều xem được dạng bảng),
 * giữ khung cũ mờ đi khi đang tải lại.
 */
export function ChartCard({ title, subtitle, extra, table, loading, error, fetching, height, bare = false, children }) {
  const [view, setView] = useState("chart");
  let body;
  if (error) body = <Alert type="error" showIcon message={errorText(error)} />;
  else if (loading) body = <Skeleton active paragraph={{ rows: 6 }} />;
  else if (view === "table" && table) body = <Table size="small" scroll={{ x: "max-content" }} pagination={{ pageSize: 10, showSizeChanger: false }} {...table} />;
  else if (bare) body = <div className={fetching ? "is-fetching" : undefined}>{children}</div>;
  else body = <div className={`chart-box${fetching ? " is-fetching" : ""}`} style={height ? { height } : undefined}>{children}</div>;
  return (
    <Card
      title={title}
      extra={(
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {extra}
          {table && (
            <Segmented size="small" value={view} onChange={setView}
              options={[{ label: "Biểu đồ", value: "chart" }, { label: "Bảng", value: "table" }]} />
          )}
        </div>
      )}
      style={{ height: "100%" }}
    >
      {subtitle && <div className="card-subtitle" style={{ marginTop: -8, marginBottom: 12 }}>{subtitle}</div>}
      {body}
    </Card>
  );
}
