/** GV 2.1 – Cảnh báo: 3 thẻ đèn giao thông · doughnut · bảng cảnh báo lọc/sắp xếp · Modal chi tiết (SPEC 5.3). */
import { Alert, App, Button, Card, Col, Dropdown, Input, Row, Select, Space, Table, Tag } from "antd";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { downloadFile, errorMessage, errorText } from "../../api/client.js";
import { useRiskStudents, useRiskSummary } from "../../api/hooks.js";
import RiskDoughnut from "../../charts/RiskDoughnut.jsx";
import { KpiCard, Rate, RiskBadge } from "../../components/common.jsx";
import StudentDetailModal from "../../components/StudentDetailModal.jsx";
import { CRITERIA, RISK, RISK_LEVELS } from "../../theme/tokens.js";
import { fmtDate, fmtDaysSince, fmtInt, fmtPercent, share } from "../../utils/format.js";

const SORT_FIELDS = {
  risk_score: "risk_score", student_code: "student_code", student_name: "student_name", absence_rate: "absence_rate",
  days_since_last_access: "days_since_last_access", assignments: "missing_assignments",
};

export default function TeacherRisk() {
  const { courseId } = useParams();
  const { message } = App.useApp();
  const [levels, setLevels] = useState([]);
  const [criterion, setCriterion] = useState();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: null, order: "desc" });
  const [page, setPage] = useState({ current: 1, pageSize: 50 });
  const [openUser, setOpenUser] = useState(null);
  const [exporting, setExporting] = useState(false);

  const summary = useRiskSummary(courseId);
  const students = useRiskStudents(courseId, {
    risk_level: levels, criterion, search: search || undefined,
    sort: sort.key ? SORT_FIELDS[sort.key] : "risk", order: sort.order, page: page.current, page_size: page.pageSize,
  });
  const resetPage = () => setPage((p) => ({ ...p, current: 1 }));
  const toggleLevel = (level) => { setLevels((ls) => (ls.includes(level) ? ls.filter((l) => l !== level) : [...ls, level])); resetPage(); };
  const sum = summary.data;

  async function onExport({ key }) {
    setExporting(true);
    try {
      const riskLevel = levels.length === 1 ? levels[0] : undefined;
      const name = await downloadFile(`/teacher/courses/${courseId}/export`, { format: key, risk_level: riskLevel }, `canh_bao.${key}`);
      message.success(`Đã tải ${name}`);
    } catch (err) {
      message.error(await errorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  if (summary.error) {
    return <Alert type="error" showIcon message="Không mở được môn học" description={errorText(summary.error)} />;
  }

  const sortOrder = (key) => (sort.key === key ? (sort.order === "asc" ? "ascend" : "descend") : null);
  const columns = [
    { title: "Mức", dataIndex: "risk_level", render: (v) => <RiskBadge level={v} />, width: 130 },
    { title: "MSSV", key: "student_code", dataIndex: "student_code", sorter: true, sortOrder: sortOrder("student_code") },
    { title: "Họ tên", key: "student_name", dataIndex: "student_name", sorter: true, sortOrder: sortOrder("student_name") },
    {
      title: "Vắng", key: "absence_rate", sorter: true, sortOrder: sortOrder("absence_rate"), align: "right",
      render: (_, r) => (r.total_sessions ? <span className="tabular">{fmtPercent(r.absence_rate, 0)} <span className="muted">({r.absent_sessions}/{r.total_sessions})</span></span> : <Rate value={null} />),
    },
    {
      title: "Truy cập cuối", key: "days_since_last_access", dataIndex: "days_since_last_access", sorter: true,
      sortOrder: sortOrder("days_since_last_access"), render: fmtDaysSince,
    },
    {
      title: "Bài tập (đã nộp)", key: "assignments", sorter: true, sortOrder: sortOrder("assignments"), align: "right",
      render: (_, r) => (r.total_assignments ? <span className="tabular">{r.submitted_assignments}/{r.total_assignments}</span> : <span className="muted">chưa tới hạn</span>),
    },
    { title: "Điểm", key: "risk_score", dataIndex: "risk_score", sorter: true, sortOrder: sortOrder("risk_score"), align: "right" },
    {
      title: "Lý do", dataIndex: "risk_reasons", width: 300,
      render: (reasons) => (reasons.length
        ? <Space size={[4, 4]} wrap>{reasons.map((r) => <Tag key={r} style={{ marginInlineEnd: 0 }}>{r}</Tag>)}</Space>
        : <span className="muted">–</span>),
    },
    { title: "", key: "action", render: (_, r) => <Button size="small" onClick={(e) => { e.stopPropagation(); setOpenUser(r.user_id); }}>Chi tiết</Button> },
  ];

  return (
    <>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Row gutter={[12, 12]} style={{ height: "100%" }}>
            {RISK_LEVELS.map((level) => {
              const count = sum?.[level.toLowerCase()];
              const selected = levels.includes(level);
              return (
                <Col xs={24} sm={8} key={level}>
                  <div role="button" tabIndex={0} aria-pressed={selected} className={`risk-card${selected ? " selected" : ""}`}
                    style={{ height: "100%", borderRadius: 8, borderTopColor: RISK[level].color }}
                    onClick={() => toggleLevel(level)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && toggleLevel(level)}>
                    <KpiCard
                      label={<><span style={{ color: RISK[level].color }} aria-hidden>{RISK[level].icon}</span> {RISK[level].label}</>}
                      loading={!sum} accent={RISK[level].color}
                      value={<>{fmtInt(count)} SV <span className="muted" style={{ fontSize: 14, fontWeight: 400 }}>({fmtPercent(share(count, sum?.total), 0)})</span></>}
                      hint={selected ? "Đang lọc bảng · nhấn để bỏ" : "Nhấn để lọc bảng"}
                    />
                  </div>
                </Col>
              );
            })}
            <Col span={24}>
              <Card size="small">
                <span className="muted">
                  {sum ? <>Snapshot {fmtDate(sum.snapshot_date)} · {fmtInt(sum.total)} sinh viên đang học
                    {sum.attendance_no_data === sum.total && sum.total > 0 && " · Môn chưa có buổi điểm danh (tiêu chí vắng học chưa áp dụng)"}</> : "Đang tải…"}
                </span>
              </Card>
            </Col>
          </Row>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="Tỷ lệ rủi ro" size="small" style={{ height: "100%" }} loading={!sum}>
            {sum && (
              <RiskDoughnut summary={sum} selectedLevels={levels} onToggleLevel={toggleLevel}
                criterion={criterion} onCriterion={(c) => { setCriterion(c); resetPage(); }} />
            )}
          </Card>
        </Col>

        <Col span={24}>
          <Card title="Bảng cảnh báo sinh viên">
            {/* Thanh công cụ nằm trong thân thẻ (không đặt ở `extra`) để trên điện thoại không đè mất tiêu đề */}
            <Space wrap style={{ marginBottom: 12 }}>
              <Input.Search allowClear placeholder="🔍 Tìm MSSV / tên" style={{ width: 220 }} onSearch={(v) => { setSearch(v.trim()); resetPage(); }} />
              <Select mode="multiple" allowClear placeholder="Mức" style={{ minWidth: 150 }} value={levels} aria-label="Lọc mức rủi ro"
                onChange={(v) => { setLevels(v); resetPage(); }} maxTagCount="responsive"
                options={RISK_LEVELS.map((l) => ({ value: l, label: `${RISK[l].icon} ${RISK[l].label}` }))} />
              <Select allowClear placeholder="Tiêu chí" style={{ width: 160 }} value={criterion} aria-label="Lọc tiêu chí"
                onChange={(v) => { setCriterion(v); resetPage(); }}
                options={Object.entries(CRITERIA).map(([value, label]) => ({ value, label }))} />
              <Dropdown menu={{ items: [{ key: "xlsx", label: "Excel (.xlsx)" }, { key: "pdf", label: "PDF" }], onClick: onExport }}>
                <Button loading={exporting}>⬇ Xuất danh sách</Button>
              </Dropdown>
            </Space>
            <Table
              rowKey="user_id" size="middle" columns={columns} dataSource={students.data?.items ?? []}
              loading={students.isFetching} scroll={{ x: "max-content" }}
              rowClassName={() => "clickable-row"}
              onRow={(r) => ({ onClick: () => setOpenUser(r.user_id), style: { cursor: "pointer" } })}
              pagination={{ ...page, total: students.data?.total ?? 0, showSizeChanger: true, pageSizeOptions: [20, 50, 100, 200], showTotal: (t) => `${fmtInt(t)} sinh viên` }}
              onChange={(pagination, _, sorter) => {
                setPage({ current: pagination.current, pageSize: pagination.pageSize });
                setSort(sorter.order ? { key: sorter.columnKey, order: sorter.order === "ascend" ? "asc" : "desc" } : { key: null, order: "desc" });
              }}
            />
          </Card>
        </Col>
      </Row>
      {openUser && <StudentDetailModal courseId={courseId} userId={openUser} onClose={() => setOpenUser(null)} />}
    </>
  );
}
