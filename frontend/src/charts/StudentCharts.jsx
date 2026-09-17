/** Biểu đồ trong Modal chi tiết sinh viên (SPEC 5.3): bar so sánh SV vs TB lớp, line hoạt động theo tuần. */
import { useMemo } from "react";
import { Bar, Line } from "react-chartjs-2";
import { CHROME, SERIES } from "../theme/tokens.js";
import { fmtDecimal, fmtInt } from "../utils/format.js";
import { axis, crosshair } from "./setup.js";

function CompareBars({ metrics, unit, max }) {
  const { data, options } = useMemo(() => ({
    data: {
      labels: metrics.map((m) => m.label),
      datasets: [
        { label: "Sinh viên", data: metrics.map((m) => m.student), backgroundColor: SERIES.blue, borderRadius: 4, borderSkipped: "start", maxBarThickness: 14 },
        { label: "Trung bình lớp", data: metrics.map((m) => m.class_avg), backgroundColor: CHROME.neutral, borderRadius: 4, borderSkipped: "start", maxBarThickness: 14 },
      ],
    },
    options: {
      indexAxis: "y",
      interaction: { mode: "index", axis: "y", intersect: false },
      plugins: {
        legend: { position: "top", align: "start", labels: { pointStyle: "rect" } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.raw == null ? "chưa có dữ liệu" : unit === "%" ? `${fmtDecimal(ctx.raw, 1)}%` : fmtDecimal(ctx.raw, 1)}`,
          },
        },
      },
      scales: {
        x: axis({ beginAtZero: true, max, ticks: { callback: (v) => (unit === "%" ? `${v}%` : fmtInt(v)) } }),
        y: axis({ grid: { display: false }, ticks: { color: CHROME.ink } }),
      },
    },
  }), [metrics, unit, max]);
  return <Bar data={data} options={options} role="img" aria-label="So sánh sinh viên với trung bình lớp" />;
}

/** Tách chỉ số % và chỉ số lượt thành 2 biểu đồ để không trộn 2 đơn vị trên một trục. */
export function StudentCompareChart({ metrics }) {
  const percent = metrics.filter((m) => m.unit === "%");
  const counts = metrics.filter((m) => m.unit !== "%");
  const missing = metrics.filter((m) => m.student == null).map((m) => m.label);
  return (
    <>
      <div className="chart-box" style={{ height: 170 }}><CompareBars metrics={percent} unit="%" max={100} /></div>
      <div className="chart-box" style={{ height: 130 }}><CompareBars metrics={counts} unit="lượt" /></div>
      {missing.length > 0 && <div className="muted" style={{ fontSize: 12 }}>Chưa có dữ liệu: {missing.join(", ")}</div>}
    </>
  );
}

/** Lượt xem & thao tác theo tuần; điểm trên đường: ● có mặt đủ các buổi trong tuần, ○ có buổi vắng, không điểm = tuần không điểm danh. */
export function WeeklyActivityChart({ weeks }) {
  const { data, options } = useMemo(() => ({
    data: {
      labels: weeks.map((w) => `T${w.week}`),
      datasets: [
        {
          label: "Lượt xem", data: weeks.map((w) => w.views), borderColor: SERIES.blue, backgroundColor: SERIES.blue, tension: 0.3,
          pointRadius: weeks.map((w) => (w.attended == null ? 0 : 5)),
          pointBackgroundColor: weeks.map((w) => (w.attended ? SERIES.blue : "#ffffff")),
          pointBorderColor: SERIES.blue, pointBorderWidth: 2, pointStyle: "circle",
        },
        {
          label: "Thao tác (nộp bài, đăng bài)", data: weeks.map((w) => w.actions), borderColor: SERIES.aqua,
          backgroundColor: SERIES.aqua, tension: 0.3, pointStyle: "line",
        },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", align: "start" },
        tooltip: {
          callbacks: {
            title: (ctx) => `Tuần ${weeks[ctx[0].dataIndex].week}`,
            afterBody: (ctx) => {
              const w = weeks[ctx[0].dataIndex];
              return w.sessions ? `Điểm danh: có mặt ${w.present}/${w.sessions} buổi` : "Tuần không có buổi điểm danh";
            },
          },
        },
      },
      scales: { x: axis({ grid: { display: false } }), y: axis({ beginAtZero: true, ticks: { precision: 0 } }) },
    },
  }), [weeks]);
  return (
    <>
      <div className="chart-box" style={{ height: 250 }}>
        <Line data={data} options={options} plugins={[crosshair]} role="img" aria-label="Hoạt động theo tuần" />
      </div>
      <div className="legend-row" style={{ marginTop: 6 }}>
        <span><span aria-hidden style={{ color: SERIES.blue }}>●</span> có mặt đủ buổi học trong tuần</span>
        <span><span aria-hidden style={{ color: SERIES.blue }}>○</span> có buổi vắng</span>
      </div>
    </>
  );
}
