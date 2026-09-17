/** Admin 1.2 – Lưu lượng: khoảng ngày có sẵn mốc · thẻ thời gian thực (tự làm mới 60s) · dual-axis · top giờ cao điểm · heatmap. */
import { Card, Col, DatePicker, Row, Select, Table } from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { useFilters, useTrafficHeatmap, useTrafficHourly, useTrafficRealtime } from "../../api/hooks.js";
import TrafficDualAxisChart, { PeakLegend, trafficTableColumns } from "../../charts/TrafficDualAxisChart.jsx";
import TrafficHeatmap, { heatmapTableColumns } from "../../charts/TrafficHeatmap.jsx";
import { ChartCard, KpiCard } from "../../components/common.jsx";
import { fmtDateTime, fmtDecimal, fmtHour, fmtInt } from "../../utils/format.js";

const MAX_DAYS = 92;

export default function AdminTraffic() {
  const { data: filters } = useFilters();
  const asOf = filters ? dayjs(filters.as_of) : null;
  const [range, setRange] = useState(null);
  const [weeks, setWeeks] = useState(4);

  useEffect(() => {
    if (asOf && !range) setRange([asOf.subtract(6, "day").startOf("day"), asOf.startOf("day")]);
  }, [asOf, range]);

  const from = range?.[0]?.format("YYYY-MM-DD");
  const to = range?.[1]?.format("YYYY-MM-DD");
  const hourly = useTrafficHourly(from, to);
  const realtime = useTrafficRealtime();
  const heatmap = useTrafficHeatmap(weeks);
  const items = hourly.data?.items;

  const stats = useMemo(() => {
    if (!items?.length) return null;
    const peak = items.reduce((best, i) => (i.total_requests > best.total_requests ? i : best), items[0]);
    const total = items.reduce((s, i) => s + i.total_requests, 0);
    return { peak, total, avgOnline: items.reduce((s, i) => s + Number(i.avg_online_users), 0) / items.length,
      top: [...items].sort((a, b) => b.total_requests - a.total_requests).slice(0, 10) };
  }, [items]);

  const presets = asOf ? [
    { label: "Hôm nay", value: [asOf.startOf("day"), asOf.startOf("day")] },
    { label: "7 ngày gần nhất", value: [asOf.subtract(6, "day").startOf("day"), asOf.startOf("day")] },
    { label: "30 ngày gần nhất", value: [asOf.subtract(29, "day").startOf("day"), asOf.startOf("day")] },
    { label: "90 ngày gần nhất", value: [asOf.subtract(89, "day").startOf("day"), asOf.startOf("day")] },
  ] : [];
  const days = range ? range[1].diff(range[0], "day") + 1 : 0;
  const rt = realtime.data;

  return (
    <>
      <div className="filter-bar">
        <b>Khoảng thời gian:</b>
        <DatePicker.RangePicker
          aria-label="Khoảng thời gian" value={range} format="DD/MM/YYYY" presets={presets} allowClear={false}
          onChange={(value) => value && setRange(value)}
          disabledDate={(d) => !!asOf && d.isAfter(asOf, "day")}
        />
        <span className="muted">{days > MAX_DAYS ? `Tối đa ${MAX_DAYS} ngày` : `${days} ngày · ${items ? fmtInt(items.length) : "–"} giờ`}</span>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard label={<>Online hiện tại<span className="live-dot" aria-hidden /></>} loading={!rt} value={fmtInt(rt?.current_online)}
            hint={rt?.current_online_at ? `Mẫu lúc ${fmtHour(rt.current_online_at)} · tự làm mới mỗi 60 giây` : "Chưa có mẫu"} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard label="Requests hôm nay" loading={!rt} value={fmtInt(rt?.requests_so_far)} hint={rt ? `Giờ hiện tại (${fmtHour(rt.current_hour)}): ${fmtInt(rt.requests_current_hour)}` : undefined} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard label="Giờ đông nhất trong khoảng" loading={!stats && hourly.isLoading}
            value={stats ? `${fmtInt(stats.peak.total_requests)} req` : "–"} hint={stats ? `▲ ${fmtDateTime(stats.peak.stat_hour)}` : undefined} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <KpiCard label="Online trung bình trong khoảng" loading={!stats && hourly.isLoading}
            value={stats ? fmtDecimal(stats.avgOnline, 1) : "–"} hint={stats ? `Tổng ${fmtInt(stats.total)} requests` : undefined} />
        </Col>

        <Col span={24}>
          <ChartCard
            title="Lưu lượng truy cập theo giờ"
            subtitle={<>Requests là số sự kiện ghi trong logstore (chỉ số gần đúng của HTTP request) <PeakLegend inline /></>}
            loading={hourly.isLoading} error={hourly.error} fetching={hourly.isFetching} height={360}
            table={{ rowKey: "stat_hour", dataSource: items ?? [], columns: trafficTableColumns }}
          >
            {items && <TrafficDualAxisChart items={items} labelFormat={days <= 1 ? "HH:mm" : "DD/MM HH:mm"} />}
          </ChartCard>
        </Col>

        <Col xs={24} xl={9}>
          <Card title="Top 10 giờ đông nhất" style={{ height: "100%" }}>
            <Table
              size="small" rowKey="stat_hour" pagination={false} dataSource={stats?.top ?? []} loading={hourly.isLoading}
              columns={[
                { title: "#", render: (_, __, i) => i + 1, width: 40 },
                { title: "Giờ", dataIndex: "stat_hour", render: fmtDateTime },
                { title: "Requests", dataIndex: "total_requests", align: "right", render: fmtInt },
                { title: "Online cao nhất", dataIndex: "peak_online_users", align: "right", render: fmtInt },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <ChartCard
            title="Heatmap giờ × thứ"
            extra={(
              <Select size="small" value={weeks} onChange={setWeeks} aria-label="Số tuần" style={{ width: 120 }}
                options={[1, 2, 4, 8, 12].map((w) => ({ value: w, label: `${w} tuần` }))} />
            )}
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
