/** Admin 1.3 – Báo cáo: loại báo cáo + bộ lọc đa chiều → Data Preview Table (phân trang) → Xuất Excel / Xuất PDF (SPEC 5.2). */
import { App, Button, Card, DatePicker, Empty, Select, Space, Table, Typography } from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { downloadFile, errorMessage } from "../../api/client.js";
import { useFacultyCourses, useFilters, useReportPreview } from "../../api/hooks.js";
import { RiskBadge } from "../../components/common.jsx";
import TermFilterBar from "../../components/TermFilterBar.jsx";
import { RISK, RISK_LEVELS } from "../../theme/tokens.js";
import { fmtDate, fmtDateTime, fmtDaysSince, fmtDecimal, fmtInt, fmtPercent } from "../../utils/format.js";

const REPORT_TYPES = [
  { value: "enrollment", label: "Quy mô đào tạo & tương tác môn học" },
  { value: "risk", label: "Cảnh báo sinh viên nguy cơ" },
  { value: "traffic", label: "Lưu lượng truy cập theo giờ" },
];

const RENDERERS = {
  int: fmtInt,
  decimal: (v) => fmtDecimal(v, 2),
  percent: (v) => fmtPercent(v, 2, "–"),
  date: fmtDate,
  datetime: fmtDateTime,
  bool: (v) => (v ? "▲ Có" : ""),
  list: (v) => (v ?? []).join("; "),
  risk_level: (v) => <RiskBadge level={v} />,
  days: fmtDaysSince,
};
const NUMERIC = ["int", "decimal", "percent", "days"];

export default function AdminReports() {
  const { message } = App.useApp();
  const { data: filters } = useFilters();
  const asOf = filters ? dayjs(filters.as_of) : null;
  const [form, setForm] = useState({ report_type: "enrollment" });
  const [applied, setApplied] = useState(null);
  const [page, setPage] = useState({ current: 1, pageSize: 50 });
  const [exporting, setExporting] = useState(null);

  useEffect(() => {
    if (filters && !form.academic_year) setForm((f) => ({ ...f, ...filters.current }));
  }, [filters, form.academic_year]);

  const courses = useFacultyCourses(form.faculty_id, form.academic_year ? { academic_year: form.academic_year, semester: form.semester } : null, "shortname", "asc");
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const params = useMemo(() => {
    const base = { report_type: form.report_type };
    if (form.report_type === "traffic") {
      return { ...base, from: form.range?.[0]?.format("YYYY-MM-DD"), to: form.range?.[1]?.format("YYYY-MM-DD") };
    }
    return {
      ...base, academic_year: form.academic_year, semester: form.semester, faculty_id: form.faculty_id,
      course_id: form.course_id, to: form.to?.format("YYYY-MM-DD"),
      risk_level: form.report_type === "risk" ? form.risk_level : undefined,
    };
  }, [form]);

  const preview = useReportPreview(applied && { ...applied, page: page.current, page_size: page.pageSize }, !!applied);

  const columns = (preview.data?.columns ?? []).map((c) => ({
    title: c.title, dataIndex: c.key, key: c.key,
    align: NUMERIC.includes(c.kind) ? "right" : undefined,
    render: RENDERERS[c.kind] ?? ((v) => v),
    ellipsis: c.kind === "list" ? { showTitle: true } : undefined,
    width: c.kind === "list" ? 320 : undefined,
  }));

  async function onExport(format) {
    setExporting(format);
    try {
      const name = await downloadFile("/admin/reports/export", { ...params, format }, `bao_cao.${format}`);
      message.success(`Đã tải ${name}`);
    } catch (err) {
      message.error(await errorMessage(err));
    } finally {
      setExporting(null);
    }
  }

  return (
    <>
      <div className="filter-bar">
        <b>Loại báo cáo:</b>
        <Select aria-label="Loại báo cáo" style={{ width: 300 }} value={form.report_type} options={REPORT_TYPES}
          onChange={(report_type) => set({ report_type })} />
        {form.report_type !== "traffic" ? (
          <>
            <TermFilterBar filters={filters} term={form} onTermChange={(t) => set({ ...t, course_id: undefined })}
              facultyId={form.faculty_id} onFacultyChange={(faculty_id) => set({ faculty_id, course_id: undefined })} />
            <Select aria-label="Môn học" style={{ width: 240 }} allowClear placeholder={form.faculty_id ? "Tất cả môn" : "Chọn khoa để lọc môn"}
              disabled={!form.faculty_id} value={form.course_id} onChange={(course_id) => set({ course_id })}
              options={(courses.data?.items ?? []).map((c) => ({ value: c.course_id, label: `${c.shortname} – ${c.fullname}` }))}
              showSearch optionFilterProp="label" />
            {form.report_type === "risk" && (
              <Select aria-label="Mức rủi ro" style={{ width: 170 }} allowClear placeholder="Mọi mức rủi ro" value={form.risk_level}
                onChange={(risk_level) => set({ risk_level })}
                options={RISK_LEVELS.map((l) => ({ value: l, label: `${RISK[l].icon} ${RISK[l].label}` }))} />
            )}
            <DatePicker aria-label="Ngày số liệu" placeholder="Ngày số liệu (mới nhất)" format="DD/MM/YYYY" value={form.to} style={{ width: 210 }}
              onChange={(to) => set({ to })} disabledDate={(d) => asOf && d.isAfter(asOf, "day")} />
          </>
        ) : (
          <DatePicker.RangePicker aria-label="Khoảng thời gian" format="DD/MM/YYYY" value={form.range}
            onChange={(range) => set({ range })} disabledDate={(d) => asOf && d.isAfter(asOf, "day")}
            placeholder={["Từ ngày (mặc định 7 ngày)", "Đến ngày"]} />
        )}
        <span className="spacer" />
        <Button type="primary" onClick={() => { setPage((p) => ({ ...p, current: 1 })); setApplied(params); }}>Xem trước</Button>
        <Button onClick={() => onExport("xlsx")} loading={exporting === "xlsx"}>⬇ Xuất Excel</Button>
        <Button onClick={() => onExport("pdf")} loading={exporting === "pdf"}>⬇ Xuất PDF</Button>
      </div>

      <Card
        title={preview.data ? preview.data.title : "Xem trước dữ liệu"}
        extra={preview.data && <span className="muted">{fmtInt(preview.data.total)} dòng</span>}
      >
        {!applied ? (
          <Empty description="Chọn loại báo cáo, bộ lọc rồi nhấn “Xem trước”. Có thể xuất file ngay mà không cần xem trước." />
        ) : (
          <>
            {preview.error && <Typography.Text type="danger">{preview.error?.response?.data?.detail ?? "Không tải được dữ liệu"}</Typography.Text>}
            <Table
              size="small" rowKey="__row" columns={columns}
              dataSource={(preview.data?.items ?? []).map((row, i) => ({ ...row, __row: (page.current - 1) * page.pageSize + i }))}
              loading={preview.isFetching} scroll={{ x: "max-content" }}
              pagination={{ ...page, total: preview.data?.total ?? 0, showSizeChanger: true, pageSizeOptions: [20, 50, 100, 200], showTotal: (t) => `${fmtInt(t)} dòng` }}
              onChange={(p) => setPage({ current: p.current, pageSize: p.pageSize })}
            />
          </>
        )}
        <Space style={{ marginTop: 8 }} className="muted">
          PDF tối đa 5.000 dòng, Excel tối đa 200.000 dòng. Ô “–” là chưa có dữ liệu để tính (khác 0%).
        </Space>
      </Card>
    </>
  );
}
