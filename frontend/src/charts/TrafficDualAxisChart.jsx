/**
 * Admin 1.2 – Dual-axis Line (SPEC 5.2, 5.4): trục trái Requests/giờ, trục phải người dùng online.
 * Đề tài yêu cầu 2 trục; để không đọc nhầm thang: 2 đường khác kiểu nét (liền / đứt), tiêu đề trục ghi rõ đại lượng,
 * legend + tooltip liệt kê đủ cả hai giá trị. Vùng tô nền = giờ cao điểm (is_peak_hour: vượt P90 của 28 ngày).
 */
import dayjs from "dayjs";
import { useMemo } from "react";
import { Line } from "react-chartjs-2";
import { CHROME, SERIES } from "../theme/tokens.js";
import { fmtDecimal, fmtInt, peakRanges } from "../utils/format.js";
import { axis, crosshair, vnNumber } from "./setup.js";

export default function TrafficDualAxisChart({ items, labelFormat = "HH:mm" }) {
  const { data, options } = useMemo(() => {
    const annotations = Object.fromEntries(peakRanges(items).map((range, k) => [`peak${k}`, {
      type: "box", xMin: range.from - 0.5, xMax: range.to + 0.5, backgroundColor: CHROME.peakWash, borderWidth: 0,
      drawTime: "beforeDatasetsDraw",
    }]));
    return {
      data: {
        labels: items.map((i) => dayjs(i.stat_hour).format(labelFormat)),
        datasets: [
          {
            label: "Requests / giờ (trục trái, nét liền)", data: items.map((i) => i.total_requests), yAxisID: "y",
            borderColor: SERIES.blue, backgroundColor: "rgba(42, 120, 214, 0.10)", fill: "origin", tension: 0.3,
            pointStyle: "line",
          },
          {
            label: "Người dùng online TB (trục phải, nét đứt)", data: items.map((i) => Number(i.avg_online_users)),
            yAxisID: "y1", borderColor: SERIES.orange, backgroundColor: SERIES.orange, borderDash: [6, 4], tension: 0.3,
            fill: false, pointStyle: "line",
          },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", align: "start", labels: { pointStyle: "line", pointStyleWidth: 22 } },
          annotation: { annotations },
          tooltip: {
            callbacks: {
              title: (ctx) => dayjs(items[ctx[0].dataIndex].stat_hour).format("dddd, DD/MM/YYYY HH:mm"),
              label: (ctx) => (ctx.datasetIndex === 0
                ? ` Requests: ${fmtInt(ctx.parsed.y)}`
                : ` Online trung bình: ${fmtDecimal(ctx.parsed.y, 1)}`),
              afterBody: (ctx) => {
                const item = items[ctx[0].dataIndex];
                return [
                  `Online cao nhất: ${fmtInt(item.peak_online_users)}`,
                  `Người dùng hoạt động: ${fmtInt(item.unique_users)}`,
                  `Đăng nhập: ${fmtInt(item.login_count)} (lỗi ${fmtInt(item.failed_login_count)})`,
                  ...(item.is_peak_hour ? ["▲ Giờ cao điểm"] : []),
                ];
              },
            },
          },
        },
        scales: {
          x: axis({ grid: { display: false }, ticks: { maxTicksLimit: 12, maxRotation: 0, autoSkip: true } }),
          y: axis({
            position: "left", beginAtZero: true, ticks: { callback: vnNumber },
            title: { display: true, text: "Requests / giờ", color: CHROME.secondary },
          }),
          y1: axis({
            position: "right", beginAtZero: true, grid: { drawOnChartArea: false }, ticks: { callback: vnNumber },
            title: { display: true, text: "Người dùng online", color: CHROME.secondary },
          }),
        },
      },
    };
  }, [items, labelFormat]);

  return <Line data={data} options={options} plugins={[crosshair]} aria-label="Biểu đồ lưu lượng truy cập theo giờ" role="img" />;
}

/** Chú thích vùng tô nền giờ cao điểm (không phải một chuỗi dữ liệu nên nằm ngoài legend của Chart.js). */
export function PeakLegend({ inline = false }) {
  const key = <span className="legend-key" style={{ background: "rgba(214, 69, 69, 0.18)" }} />;
  if (inline) return <span style={{ whiteSpace: "nowrap" }}> · {key}vùng tô = giờ cao điểm (vượt P90 của 28 ngày)</span>;
  return (
    <div className="legend-row" style={{ marginTop: 8 }}>
      <span>{key}Giờ cao điểm (requests vượt P90 của 28 ngày)</span>
    </div>
  );
}

export const trafficTableColumns = [
  { title: "Giờ", dataIndex: "stat_hour", render: (v) => dayjs(v).format("DD/MM/YYYY HH:mm") },
  { title: "Requests", dataIndex: "total_requests", align: "right", render: fmtInt },
  { title: "Người dùng", dataIndex: "unique_users", align: "right", render: fmtInt },
  { title: "Online TB", dataIndex: "avg_online_users", align: "right", render: (v) => fmtDecimal(v, 1) },
  { title: "Online cao nhất", dataIndex: "peak_online_users", align: "right", render: fmtInt },
  { title: "Đăng nhập lỗi", dataIndex: "failed_login_count", align: "right", render: fmtInt },
  { title: "Giờ cao điểm", dataIndex: "is_peak_hour", render: (v) => (v ? "▲ Có" : "") },
];
