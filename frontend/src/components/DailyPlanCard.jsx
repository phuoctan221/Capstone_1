import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { canNotify, disableReminder, enableReminder, isReminderEnabled, useDailyReminder } from "../hooks/useDailyReminder";

const WEEKDAYS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

function formatToday(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit" }).format(date);
}

export default function DailyPlanCard({ plan }) {
  const [enabled, setEnabled] = useState(isReminderEnabled);
  const [permission, setPermission] = useState(() => (canNotify() ? Notification.permission : "unsupported"));
  useDailyReminder(plan);

  const weekMax = useMemo(
    () => Math.max(1, ...((plan?.week || []).map((day) => day.studied || 0))),
    [plan]
  );

  if (!plan) return null;

  const percent = Math.min(100, Math.round((plan.studied_today / Math.max(plan.goal, 1)) * 100));
  const hasWork = plan.due_count > 0 || plan.remaining > 0;

  async function toggleReminder() {
    if (enabled) {
      disableReminder();
      setEnabled(false);
      return;
    }
    const ok = await enableReminder();
    setEnabled(ok);
    setPermission(canNotify() ? Notification.permission : "unsupported");
  }

  return (
    <section className="sv-panel sv-daily" aria-labelledby="sv-daily-title">
      <div className="sv-daily-head">
        <div>
          <span className="sv-eyebrow">KẾ HOẠCH HÔM NAY</span>
          <h2 id="sv-daily-title">{plan.goal_met ? "Bạn đã đạt mục tiêu hôm nay" : "Học đúng thứ cần học"}</h2>
          <p className="sv-daily-sub">{formatToday(plan.date)} · {plan.studied_today}/{plan.goal} từ · chuỗi {plan.streak} ngày</p>
        </div>
        <div className={`sv-daily-score${plan.goal_met ? " is-done" : ""}`}>
          <b>{percent}%</b>
          <span>mục tiêu</span>
        </div>
      </div>

      <div className="sv-daily-progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div style={{ width: `${percent}%` }} />
      </div>

      <div className="sv-daily-metrics">
        <span><b>{plan.due_count}</b> cần ôn</span>
        <span><b>{plan.new_count}</b> từ mới</span>
        <span><b>{plan.answered_today}</b> câu đã làm</span>
        <span><b>{plan.xp_today}</b> XP hôm nay</span>
      </div>

      {!plan.goal_met && hasWork && (
        <div className="sv-daily-banner" role="status">
          <span>{plan.due_count > 0 ? `Còn ${plan.due_count} từ đến hạn ôn` : `Còn ${plan.remaining} từ để đạt mục tiêu`}</span>
          <Link to={plan.due_count > 0 ? "/flashcards" : (plan.next_lesson?.href || "/learn")}>Học ngay →</Link>
        </div>
      )}

      <div className="sv-daily-tasks">
        {plan.tasks.map((task) => (
          <Link key={task.id} to={task.href} className={`sv-daily-task${task.done ? " is-done" : ""}`}>
            <span className="sv-daily-task-check" aria-hidden="true">{task.done ? "✓" : "○"}</span>
            <strong>{task.title}</strong>
            <span className="sv-daily-task-arrow" aria-hidden="true">→</span>
          </Link>
        ))}
      </div>

      <div className="sv-daily-week">
        <div className="sv-daily-week-head"><span>7 ngày qua</span><span className="sv-muted-small">Số từ đã học mỗi ngày</span></div>
        <div className="sv-daily-bars">
          {plan.week.map((day) => {
            const height = Math.max(6, Math.round(((day.studied || 0) / weekMax) * 100));
            const isToday = day.date === plan.date;
            return (
              <div key={day.date} className={`sv-daily-bar-item${isToday ? " is-today" : ""}`} title={`${day.date}: ${day.studied} từ`}>
                <span className="sv-daily-bar-value">{day.studied}</span>
                <span className="sv-daily-bar" style={{ height: `${height}%` }} />
                <small>{WEEKDAYS[new Date(`${day.date}T00:00:00`).getDay()]}</small>
              </div>
            );
          })}
        </div>
      </div>

      {(plan.due_preview.length > 0 || plan.new_preview.length > 0) && (
        <div className="sv-daily-preview">
          {plan.due_preview.length > 0 && (
            <div>
              <span className="sv-daily-preview-label">Ôn lại</span>
              {plan.due_preview.map((word) => <span key={word.vocabulary_id} className="sv-daily-chip">{word.word}</span>)}
            </div>
          )}
          {plan.new_preview.length > 0 && (
            <div>
              <span className="sv-daily-preview-label">Từ mới</span>
              {plan.new_preview.map((word) => <span key={word.vocabulary_id} className="sv-daily-chip is-new">{word.word}</span>)}
            </div>
          )}
        </div>
      )}

      <div className="sv-daily-reminder">
        {canNotify() ? (
          <>
            <button type="button" className="sv-btn sv-btn-outline sv-daily-reminder-btn" onClick={toggleReminder}>
              {enabled ? "Tắt nhắc nhở" : "Bật nhắc nhở"}
            </button>
            <span className="sv-muted-small">
              {enabled
                ? "Sẽ nhắc một lần mỗi ngày khi bạn mở ứng dụng."
                : permission === "denied"
                  ? "Trình duyệt đang chặn thông báo cho trang này."
                  : "Nhắc bạn khi còn từ cần học."}
            </span>
          </>
        ) : (
          <span className="sv-muted-small">Trình duyệt không hỗ trợ thông báo; kế hoạch vẫn hiển thị tại đây.</span>
        )}
      </div>
    </section>
  );
}
