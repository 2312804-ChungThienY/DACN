/** GV 2.2 – Tiến độ lớp: progress bar hoàn thành / nộp bài / chuyên cần · tiến độ theo chương · line SV hoạt động (SPEC 5.3). */
import { Alert, Card, Col, Progress, Row, Segmented } from "antd";
import dayjs from "dayjs";
import { useMemo, useState } from "react";
import { Line } from "react-chartjs-2";
import { useParams } from "react-router-dom";
import { errorText } from "../../api/client.js";
import { useCourseProgress } from "../../api/hooks.js";
import { axis, crosshair } from "../../charts/setup.js";
import { ChartCard, KpiCard, Rate } from "../../components/common.jsx";
import { CHROME, SERIES } from "../../theme/tokens.js";
import { NO_DATA, fmtDate, fmtDecimal, fmtInt, fmtPercent } from "../../utils/format.js";

function RateBar({ label, value, hint }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <span>{label}</span>
        <b className="tabular"><Rate value={value} /></b>
      </div>
      {value == null
        ? <div className="no-data" style={{ fontSize: 12 }}>{hint}</div>
        : <Progress percent={Number(value)} showInfo={false} strokeColor={SERIES.blue} trailColor="#e8eef8" aria-label={`${label} ${fmtPercent(value)}`} />}
    </div>
  );
}

const periodLabel = (p, granularity) => (granularity === "week" ? `${dayjs(p.period_start).format("DD/MM")}` : dayjs(p.period_start).format("DD/MM"));

export default function TeacherProgress() {
  const { courseId } = useParams();
  const [granularity, setGranularity] = useState("week");
  const progress = useCourseProgress(courseId, granularity);
  const d = progress.data;
  const s = d?.summary;

  const activeChart = useMemo(() => {
    if (!d) return null;
    const key = granularity === "week" ? "active_students_7d" : "active_students_day";
    return {
      data: {
        labels: d.series.map((p) => periodLabel(p, granularity)),
        datasets: [{
          label: granularity === "week" ? "SV hoạt động trong tuần" : "SV hoạt động trong ngày",
          data: d.series.map((p) => p[key]), borderColor: SERIES.blue, backgroundColor: "rgba(42, 120, 214, 0.10)", fill: "origin", tension: 0.3,
          pointRadius: granularity === "week" ? 4 : 0, pointBackgroundColor: SERIES.blue, pointBorderColor: "#fff", pointBorderWidth: 2,
        }],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (ctx) => {
                const p = d.series[ctx[0].dataIndex];
                return granularity === "week" ? `Tuần ${p.period} (${fmtDate(p.period_start)} – ${fmtDate(p.period_end)})` : fmtDate(p.period_start);
              },
              label: (ctx) => ` ${fmtInt(ctx.parsed.y)} / ${fmtInt(d.series[ctx.dataIndex].enrolled)} SV hoạt động`,
            },
          },
        },
        scales: { x: axis({ grid: { display: false }, ticks: { maxTicksLimit: 16, maxRotation: 0 } }), y: axis({ beginAtZero: true, ticks: { precision: 0 } }) },
      },
    };
  }, [d, granularity]);

  const ratesChart = useMemo(() => {
    if (!d) return null;
    const series = [
      ["Hoàn thành hoạt động", "avg_completion_rate", SERIES.blue, []],
      ["Nộp bài", "assignment_submission_rate", SERIES.orange, [6, 4]],
      ["Chuyên cần", "attendance_rate", SERIES.aqua, [2, 3]],
    ];
    return {
      data: {
        labels: d.series.map((p) => periodLabel(p, granularity)),
        datasets: series.map(([label, key, color, dash]) => ({
          label, data: d.series.map((p) => (p[key] == null ? null : Number(p[key]))), borderColor: color, backgroundColor: color,
          borderDash: dash, tension: 0.3, spanGaps: false, pointStyle: "line",
        })),
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", align: "start", labels: { pointStyle: "line", pointStyleWidth: 22 } },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.raw == null ? NO_DATA.toLowerCase() : `${fmtDecimal(ctx.raw, 1)}%`}` } },
        },
        scales: {
          x: axis({ grid: { display: false }, ticks: { maxTicksLimit: 16, maxRotation: 0 } }),
          y: axis({ min: 0, max: 100, ticks: { callback: (v) => `${v}%` } }),
        },
      },
    };
  }, [d, granularity]);

  const tableColumns = [
    { title: granularity === "week" ? "Tuần" : "Ngày", dataIndex: "period" },
    { title: "SV hoạt động", dataIndex: granularity === "week" ? "active_students_7d" : "active_students_day", align: "right", render: fmtInt },
    { title: "Hoàn thành", dataIndex: "avg_completion_rate", align: "right", render: (v) => fmtPercent(v, 1, "–") },
    { title: "Nộp bài", dataIndex: "assignment_submission_rate", align: "right", render: (v) => fmtPercent(v, 1, "–") },
    { title: "Chuyên cần", dataIndex: "attendance_rate", align: "right", render: (v) => fmtPercent(v, 1, "–") },
    { title: "Lượt xem", dataIndex: "total_views_day", align: "right", render: fmtInt },
    { title: "Bài nộp", dataIndex: "submissions_day", align: "right", render: fmtInt },
  ];
  if (progress.error && !d) {
    return <Alert type="error" showIcon message="Không mở được môn học" description={errorText(progress.error)} />;
  }

  const granularityControl = (
    <Segmented size="small" value={granularity} onChange={setGranularity} options={[{ label: "Theo tuần", value: "week" }, { label: "Theo ngày", value: "day" }]} />
  );

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={8}><KpiCard label="SV đang học" loading={!s} value={fmtInt(s?.enrolled)} hint={s && `Số liệu ngày ${fmtDate(s.stat_date)}`} /></Col>
      <Col xs={24} sm={8}><KpiCard label="SV hoạt động 7 ngày qua" loading={!s} value={fmtInt(s?.active_students_7d)} hint={s && `${fmtPercent(s.enrolled ? (100 * s.active_students_7d) / s.enrolled : null)} lớp`} /></Col>
      <Col xs={24} sm={8}><KpiCard label="Bài tập đã tới hạn" loading={!s} value={fmtInt(s?.total_assignments)} hint={s && `TB ${fmtDecimal(s.avg_access_per_student, 1)} lượt truy cập/SV`} /></Col>

      <Col xs={24} lg={10}>
        <Card title="Tiến độ lớp" loading={!s} style={{ height: "100%" }}>
          {s && (
            <>
              <RateBar label="Hoàn thành hoạt động bắt buộc" value={s.avg_completion_rate} hint="Chưa có hoạt động theo dõi hoàn thành nào tới hạn" />
              <RateBar label="Nộp bài" value={s.submission_rate} hint="Chưa có bài tập nào tới hạn" />
              <RateBar label="Chuyên cần" value={s.attendance_rate} hint="Môn chưa có buổi điểm danh" />
            </>
          )}
        </Card>
      </Col>
      <Col xs={24} lg={14}>
        <Card title="Tiến độ theo chương / tuần" loading={!d} style={{ height: "100%" }}>
          {d && (d.sections.length ? d.sections.map((sec) => (
            <div key={sec.section} style={{ display: "grid", gridTemplateColumns: "minmax(90px, 160px) 1fr 64px", gap: 12, alignItems: "center", marginBottom: 6 }}>
              <span title={sec.name} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sec.name}</span>
              <Progress percent={Number(sec.completion_rate)} showInfo={false} strokeColor={SERIES.blue} trailColor="#e8eef8" size="small"
                aria-label={`${sec.name}: hoàn thành ${fmtPercent(sec.completion_rate, 0)}`} />
              <span className="tabular" style={{ textAlign: "right" }}>{fmtPercent(sec.completion_rate, 0)}</span>
            </div>
          )) : <span className="muted">Chưa có hoạt động theo dõi hoàn thành nào tới hạn</span>)}
        </Card>
      </Col>

      <Col xs={24} xl={12}>
        <ChartCard title="Sinh viên hoạt động" subtitle={granularity === "week" ? "Số SV có truy cập trong mỗi tuần" : "Số SV có truy cập trong mỗi ngày"}
          extra={granularityControl} loading={progress.isLoading} error={progress.error} fetching={progress.isFetching}
          table={{ rowKey: "period", dataSource: d?.series ?? [], columns: tableColumns }}>
          {activeChart && <Line data={activeChart.data} options={activeChart.options} plugins={[crosshair]} role="img" aria-label="Sinh viên hoạt động theo thời gian" />}
        </ChartCard>
      </Col>
      <Col xs={24} xl={12}>
        <ChartCard title="Tỷ lệ tiến độ theo thời gian" subtitle="Khoảng trống trên đường = chưa có dữ liệu để tính"
          extra={granularityControl} loading={progress.isLoading} error={progress.error} fetching={progress.isFetching}
          table={{ rowKey: "period", dataSource: d?.series ?? [], columns: tableColumns }}>
          {ratesChart && <Line data={ratesChart.data} options={ratesChart.options} plugins={[crosshair]} role="img" aria-label="Tỷ lệ tiến độ theo thời gian" />}
        </ChartCard>
      </Col>
      <Col span={24}><span className="muted" style={{ color: CHROME.muted }}>Theo tuần: tỷ lệ và số SV hoạt động lấy tại ngày cuối mỗi tuần; tuần hiện tại tính tới hôm nay.</span></Col>
    </Row>
  );
}
