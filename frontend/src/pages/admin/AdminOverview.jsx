/** Trang Tổng quan Admin (SPEC 5.2): bộ lọc · 6 thẻ KPI · Dual-axis lưu lượng · Stacked bar theo khoa · Bảng drill-down · Heatmap. */
import { useQueryClient } from "@tanstack/react-query";
import { App, Button, Col, Dropdown, Row, Segmented } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { downloadFile, errorMessage } from "../../api/client.js";
import {
  useEnrollmentByFaculty, useFilters, useKpis, useTrafficHeatmap, useTrafficHourly, useTrafficRealtime,
} from "../../api/hooks.js";
import EnrollmentStackedBar from "../../charts/EnrollmentStackedBar.jsx";
import TrafficDualAxisChart, { PeakLegend, trafficTableColumns } from "../../charts/TrafficDualAxisChart.jsx";
import TrafficHeatmap, { heatmapTableColumns } from "../../charts/TrafficHeatmap.jsx";
import { ChartCard, KpiCard } from "../../components/common.jsx";
import HierarchyTable from "../../components/HierarchyTable.jsx";
import TermFilterBar from "../../components/TermFilterBar.jsx";
import { RISK } from "../../theme/tokens.js";
import { fmtDecimal, fmtHour, fmtInt, fmtPercent } from "../../utils/format.js";

const EXPORTS = [
  { key: "enrollment:xlsx", label: "Báo cáo quy mô & tương tác – Excel" },
  { key: "enrollment:pdf", label: "Báo cáo quy mô & tương tác – PDF" },
  { key: "risk:xlsx", label: "Báo cáo cảnh báo sinh viên – Excel" },
  { key: "risk:pdf", label: "Báo cáo cảnh báo sinh viên – PDF" },
];

export default function AdminOverview() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const { data: filters } = useFilters();
  const [term, setTerm] = useState(null);
  const [facultyId, setFacultyId] = useState();
  const [range, setRange] = useState("24h");
  const [path, setPath] = useState({});
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (filters && !term) setTerm(filters.current);
  }, [filters, term]);

  const kpis = useKpis(term, facultyId);
  const byFaculty = useEnrollmentByFaculty(term);
  const realtime = useTrafficRealtime();
  const asOf = filters ? dayjs(filters.as_of) : null;
  const week = useTrafficHourly(asOf?.subtract(6, "day").format("YYYY-MM-DD"), asOf?.format("YYYY-MM-DD"));
  const heatmap = useTrafficHeatmap(4);

  const k = kpis.data;
  const trafficItems = range === "24h" ? realtime.data?.series_24h : week.data?.items;
  const trafficQuery = range === "24h" ? realtime : week;
  const facultyItems = (byFaculty.data?.items ?? []).filter((f) => !facultyId || f.faculty_id === facultyId);

  async function onExport({ key }) {
    const [reportType, format] = key.split(":");
    setExporting(true);
    try {
      const name = await downloadFile("/admin/reports/export", { report_type: reportType, format, ...term, faculty_id: facultyId }, `bao_cao.${format}`);
      message.success(`Đã tải ${name}`);
    } catch (err) {
      message.error(await errorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <div className="filter-bar">
        <b>Bộ lọc:</b>
        <TermFilterBar filters={filters} term={term} onTermChange={setTerm} facultyId={facultyId}
          onFacultyChange={(id) => { setFacultyId(id); setPath({}); }} />
        <span className="spacer" />
        <Button onClick={() => queryClient.invalidateQueries()}>⟳ Làm mới</Button>
        <Dropdown menu={{ items: EXPORTS, onClick: onExport }} disabled={!term}>
          <Button type="primary" loading={exporting}>⬇ Export</Button>
        </Dropdown>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8} xxl={4}>
          <KpiCard label="Tổng môn học" loading={!k} value={fmtInt(k?.total_courses)} hint={`${term?.academic_year ?? ""} · HK${term?.semester ?? ""}`} />
        </Col>
        <Col xs={24} sm={12} lg={8} xxl={4}>
          <KpiCard label="SV đăng ký" loading={!k} value={fmtInt(k?.total_enrolled)} hint="Lượt ghi danh đang hiệu lực" />
        </Col>
        <Col xs={24} sm={12} lg={8} xxl={4}>
          <KpiCard label="SV tương tác" loading={!k} value={fmtInt(k?.total_active)} hint={`${fmtPercent(k?.active_rate)} số SV đăng ký`} />
        </Col>
        <Col xs={24} sm={12} lg={8} xxl={4}>
          <KpiCard label={<>Online hiện tại<span className="live-dot" aria-hidden /></>} loading={!k}
            value={fmtInt(k?.current_online)} hint={k?.current_online_at ? `Lúc ${fmtHour(k.current_online_at)} · TB hôm nay ${fmtDecimal(k.avg_online_users_today, 0)}` : "Chưa có mẫu"} />
        </Col>
        <Col xs={24} sm={12} lg={8} xxl={4}>
          <KpiCard label="Peak hôm nay" loading={!k}
            value={k?.peak_requests_today ? `${fmtInt(k.peak_requests_today.value)} req` : "–"}
            hint={k?.peak_requests_today ? `▲ lúc ${k.peak_requests_today.hour}` : "Chưa có dữ liệu hôm nay"} />
        </Col>
        <Col xs={24} sm={12} lg={8} xxl={4}>
          <KpiCard label={<><span style={{ color: RISK.RED.color }} aria-hidden>{RISK.RED.icon}</span> SV nguy cơ cao</>} loading={!k}
            accent={RISK.RED.color} value={fmtInt(k?.red_students)} hint={`${fmtPercent(k?.red_rate)} lượt ghi danh`} />
        </Col>

        <Col xs={24} xl={14}>
          <ChartCard
            title="Lưu lượng truy cập"
            subtitle={<>Requests (sự kiện logstore) theo giờ và người dùng online trung bình <PeakLegend inline /></>}
            extra={<Segmented size="small" value={range} onChange={setRange} options={[{ label: "24 giờ", value: "24h" }, { label: "7 ngày", value: "7d" }]} />}
            loading={!trafficItems && trafficQuery.isLoading} error={trafficQuery.error} fetching={trafficQuery.isFetching}
            table={{ rowKey: "stat_hour", dataSource: trafficItems ?? [], columns: trafficTableColumns }}
          >
            {trafficItems && <TrafficDualAxisChart items={trafficItems} labelFormat={range === "24h" ? "HH:mm" : "DD/MM HH:mm"} />}
          </ChartCard>
        </Col>
        <Col xs={24} xl={10}>
          <ChartCard
            title="SV đăng ký và tương tác theo khoa"
            subtitle="Nhấn vào cột để xem các môn của khoa"
            loading={byFaculty.isLoading} error={byFaculty.error} fetching={byFaculty.isFetching}
            height={Math.max(220, facultyItems.length * 56 + 90)}
            table={{
              rowKey: "faculty_id", dataSource: facultyItems,
              columns: [
                { title: "Khoa", dataIndex: "faculty_name" },
                { title: "Đăng ký", dataIndex: "enrolled", align: "right", render: fmtInt },
                { title: "Tương tác", dataIndex: "active", align: "right", render: fmtInt },
                { title: "Không tương tác", dataIndex: "inactive", align: "right", render: fmtInt },
                { title: "Tỷ lệ", dataIndex: "active_rate", align: "right", render: (v) => fmtPercent(v) },
              ],
            }}
          >
            <EnrollmentStackedBar items={facultyItems} onSelect={(faculty) => setPath({ faculty })} />
          </ChartCard>
        </Col>

        <Col span={24}>
          {term && <HierarchyTable term={term} path={path} onPathChange={setPath} />}
        </Col>

        <Col span={24}>
          <ChartCard
            title="Heatmap giờ × thứ (4 tuần gần nhất)"
            subtitle={heatmap.data ? `Trung bình từ ${dayjs(heatmap.data.from_date).format("DD/MM")} đến ${dayjs(heatmap.data.to_date).format("DD/MM/YYYY")} – hỗ trợ dự báo giờ cao điểm` : undefined}
            loading={heatmap.isLoading} error={heatmap.error} fetching={heatmap.isFetching} bare
            table={{ rowKey: (r) => `${r.day_of_week}-${r.hour_of_day}`, dataSource: heatmap.data?.matrix ?? [], columns: heatmapTableColumns }}
          >
            {heatmap.data && <TrafficHeatmap matrix={heatmap.data.matrix} />}
          </ChartCard>
        </Col>
      </Row>
    </>
  );
}
