/** GV 2.1 – Modal chi tiết sinh viên (SPEC 5.3) + nút hành động can thiệp. */
import { Alert, App, Button, Col, Divider, Empty, Form, Input, List, Modal, Row, Skeleton, Space, Tag, Tooltip } from "antd";
import { useState } from "react";
import { errorMessage, errorText } from "../api/client.js";
import { useCreateIntervention, useStudentCompare, useStudentDetail } from "../api/hooks.js";
import { StudentCompareChart, WeeklyActivityChart } from "../charts/StudentCharts.jsx";
import { ACTIONS, RISK } from "../theme/tokens.js";
import { fmtDate, fmtDateTime, fmtDaysSince, fmtShortDate, riskTransitions } from "../utils/format.js";
import { Rate, RiskBadge } from "./common.jsx";

// Nền nhạt + chữ đậm cùng tông (tag màu preset của Ant Design không đạt tương phản WCAG AA)
const ASSIGNMENT_TAG = {
  on_time: { tone: RISK.GREEN, icon: "✔", text: "đúng hạn" },
  late: { tone: RISK.YELLOW, icon: "✔", text: "trễ hạn" },
  missing: { tone: RISK.RED, icon: "✘", text: "thiếu" },
  not_due: { tone: null, icon: "…", text: "chưa tới hạn" },
};

function assignmentState(a) {
  if (a.status === "submitted") return a.late ? "late" : "on_time";
  return a.status === "missing" ? "missing" : "not_due";
}

function InterventionDialog({ action, student, courseId, onClose }) {
  const { message } = App.useApp();
  const mutation = useCreateIntervention(courseId, student.user_id);
  const [form] = Form.useForm();
  const meta = ACTIONS[action];

  async function submit({ content }) {
    try {
      await mutation.mutateAsync({ action_type: action, content });
      message.success(`Đã ghi nhận: ${meta.label}`);
      onClose();
    } catch (err) {
      message.error(await errorMessage(err));
    }
  }

  return (
    <Modal open title={`${meta.icon} ${meta.label} – ${student.student_name}`} onCancel={onClose} okText="Ghi nhận"
      cancelText="Hủy" onOk={() => form.submit()} confirmLoading={mutation.isPending} destroyOnHidden>
      {action === "MESSAGE" && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Hệ thống ghi nhật ký can thiệp. Việc gửi tin nhắn thật qua Moodle Web Service chưa được kết nối." />
      )}
      {action === "EMAIL" && student.email && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message={<>Soạn email tới <a href={`mailto:${student.email}?subject=${encodeURIComponent(`[${student.course_shortname}] Nhắc nhở học tập`)}`}>{student.email}</a>, sau đó ghi nhận tại đây.</>} />
      )}
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item name="content" label="Nội dung" rules={[{ max: 2000, message: "Tối đa 2.000 ký tự" }]}>
          <Input.TextArea rows={4} placeholder="vd: Đã nhắc nhở trên lớp, hẹn gặp thứ 5" showCount maxLength={2000} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default function StudentDetailModal({ courseId, userId, onClose }) {
  const detail = useStudentDetail(courseId, userId);
  const compare = useStudentCompare(courseId, userId);
  const [action, setAction] = useState(null);
  const s = detail.data;

  const title = s ? (
    <Space wrap size={[8, 4]}>
      <RiskBadge level={s.risk_level} />
      <span>{s.student_name}</span>
      <span className="muted" style={{ fontWeight: 400 }}>{s.student_code} · {s.email ?? "không có email"}</span>
      <Tag>Điểm rủi ro {s.risk_score}</Tag>
    </Space>
  ) : "Chi tiết sinh viên";

  return (
    <Modal open={!!userId} onCancel={onClose} title={title} width={1040} destroyOnHidden
      footer={(
        <Space wrap>
          {Object.entries(ACTIONS).map(([key, meta]) => (
            <Button key={key} onClick={() => setAction(key)} disabled={!s}>{meta.icon} {meta.label}</Button>
          ))}
          <Button type="primary" onClick={onClose}>Đóng</Button>
        </Space>
      )}>
      {detail.error && <Alert type="error" showIcon message={errorText(detail.error)} />}
      {detail.isLoading && <Skeleton active paragraph={{ rows: 10 }} />}
      {s && (
        <>
          <Alert
            type={s.risk_level === "GREEN" ? "success" : s.risk_level === "YELLOW" ? "warning" : "error"}
            showIcon
            message={s.risk_reasons.length ? <>Lý do: {s.risk_reasons.map((r) => <span key={r}> • {r}</span>)}</> : "Không có dấu hiệu bất thường"}
            description={(
              <Space wrap size={[16, 4]} className="muted" style={{ fontSize: 12 }}>
                <span>Vắng: <Rate value={s.absence_rate} /> ({s.absent_sessions}/{s.total_sessions} buổi)</span>
                <span>Bài tập: đã nộp {s.submitted_assignments}/{s.total_assignments} (trễ {s.late_submissions})</span>
                <span>Truy cập cuối: {fmtDaysSince(s.days_since_last_access)}</span>
                <span>Hoàn thành hoạt động: <Rate value={s.completion_rate} /></span>
                <span>Snapshot {fmtDate(s.snapshot_date)}</span>
              </Space>
            )}
          />
          <Row gutter={[24, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} md={11}>
              <b>So sánh với trung bình lớp</b>
              {compare.data ? <StudentCompareChart metrics={compare.data.metrics} /> : <Skeleton active />}
            </Col>
            <Col xs={24} md={13}>
              <b>Hoạt động {s.weekly_activity.length} tuần</b>
              <WeeklyActivityChart weeks={s.weekly_activity} />
            </Col>
          </Row>

          <Divider orientation="left" plain>Bài tập</Divider>
          {s.assignment_detail.length ? (
            <Space wrap size={[6, 6]}>
              {s.assignment_detail.map((a) => {
                const state = ASSIGNMENT_TAG[assignmentState(a)];
                return (
                  <Tooltip key={a.assign_id ?? a.name} title={`Hạn ${fmtDateTime(a.duedate)}${a.submitted_at ? ` · nộp ${fmtDateTime(a.submitted_at)}` : ""}`}>
                    <Tag style={state.tone ? { color: state.tone.ink, background: state.tone.tint, borderColor: state.tone.color } : undefined}>
                      {state.icon} {a.name} – {state.text}
                    </Tag>
                  </Tooltip>
                );
              })}
            </Space>
          ) : <span className="muted">Môn chưa có bài tập</span>}

          <Divider orientation="left" plain>Lịch sử cảnh báo</Divider>
          <Space wrap size={[4, 6]}>
            {riskTransitions(s.risk_history).map((p, i) => (
              <span key={p.date}>
                {i > 0 && <span className="muted"> → </span>}
                <span className="muted">{fmtShortDate(p.date)} </span><RiskBadge level={p.risk_level} iconOnly />
              </span>
            ))}
          </Space>

          <Divider orientation="left" plain>Can thiệp trước đây</Divider>
          {s.interventions.length ? (
            <List size="small" dataSource={s.interventions} renderItem={(i) => (
              <List.Item>
                <Space wrap size={[8, 2]}>
                  <span className="muted">{fmtDateTime(i.created_at)}</span>
                  <Tag>{ACTIONS[i.action_type]?.icon} {ACTIONS[i.action_type]?.label ?? i.action_type}</Tag>
                  <span>{i.content ?? <span className="muted">(không có nội dung)</span>}</span>
                  <span className="muted">– {i.teacher_name ?? `GV #${i.teacher_id}`}</span>
                  {i.risk_level_at_time && <RiskBadge level={i.risk_level_at_time} iconOnly />}
                </Space>
              </List.Item>
            )} />
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có can thiệp nào" />}

          {action && <InterventionDialog action={action} student={s} courseId={courseId} onClose={() => setAction(null)} />}
        </>
      )}
    </Modal>
  );
}
