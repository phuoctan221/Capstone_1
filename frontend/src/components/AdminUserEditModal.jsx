import { useEffect, useState } from "react";
import { DOMAINS } from "../constants/domains";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

export default function AdminUserEditModal({ user, busy, error, onSave, onClose }) {
  const [username, setUsername] = useState(user.username || "");
  const [email, setEmail] = useState(user.email || "");
  const [learningLevel, setLearningLevel] = useState(user.learning_level || "");
  const [dailyGoal, setDailyGoal] = useState(Number(user.daily_goal) || 10);
  const [interests, setInterests] = useState(user.interests || []);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const options = [
    ...DOMAINS.map((domain) => ({ id: domain.id, label: domain.label })),
    ...[...new Set(user.interests || [])]
      .filter((value) => !DOMAINS.some((domain) => domain.id === value))
      .map((value) => ({ id: value, label: value })),
  ];

  function toggleInterest(id) {
    setLocalError("");
    setInterests((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }

  function submit(event) {
    event.preventDefault();
    const trimmedName = username.trim();
    const trimmedEmail = email.trim().toLowerCase();
    if (trimmedName.length < 3 || trimmedName.length > 30) {
      setLocalError("Tên hiển thị phải từ 3 đến 30 ký tự.");
      return;
    }
    if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(trimmedEmail)) {
      setLocalError("Email không hợp lệ.");
      return;
    }
    if (!interests.length) {
      setLocalError("Vui lòng chọn ít nhất một lĩnh vực quan tâm.");
      return;
    }
    const goal = Number(dailyGoal);
    if (!Number.isFinite(goal) || goal < 5 || goal > 100) {
      setLocalError("Mục tiêu ngày phải từ 5 đến 100 từ.");
      return;
    }
    onSave({
      username: trimmedName,
      email: trimmedEmail,
      learning_level: learningLevel || undefined,
      interests,
      daily_goal: goal,
    });
  }

  const message = localError || error;

  return (
    <div className="sv-modal-overlay" onClick={onClose} role="presentation">
      <div
        className="sv-modal-card"
        role="dialog"
        aria-modal="true"
        aria-label="Sửa thông tin người dùng"
        onClick={(event) => event.stopPropagation()}
      >
        <span className="sv-modal-eyebrow">ADMIN / TÀI KHOẢN</span>
        <h2>Sửa thông tin người dùng</h2>
        <p className="sv-modal-sub">{user.email}</p>
        <form onSubmit={submit} className="sv-admin-form-modal">
          <label className="sv-form-label" htmlFor="sv-edit-username">Tên hiển thị</label>
          <input
            id="sv-edit-username"
            className="sv-answer-field"
            value={username}
            maxLength={30}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="off"
          />
          <label className="sv-form-label" htmlFor="sv-edit-email">Email</label>
          <input
            id="sv-edit-email"
            className="sv-answer-field"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="off"
          />
          <div className="sv-admin-form-grid">
            <div>
              <label className="sv-form-label" htmlFor="sv-edit-level">Trình độ</label>
              <select
                id="sv-edit-level"
                className="sv-answer-field"
                value={learningLevel}
                onChange={(event) => setLearningLevel(event.target.value)}
              >
                <option value="">Chưa chọn</option>
                {LEVELS.map((level) => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="sv-form-label" htmlFor="sv-edit-goal">Mục tiêu ngày (từ)</label>
              <input
                id="sv-edit-goal"
                className="sv-answer-field"
                type="number"
                min={5}
                max={100}
                value={dailyGoal}
                onChange={(event) => setDailyGoal(event.target.value)}
              />
            </div>
          </div>
          <span className="sv-form-label">Lĩnh vực quan tâm</span>
          <div className="sv-interest-options">
            {options.map((option) => (
              <label key={option.id} className={`sv-interest-chip${interests.includes(option.id) ? " on" : ""}`}>
                <input
                  type="checkbox"
                  checked={interests.includes(option.id)}
                  onChange={() => toggleInterest(option.id)}
                />
                {option.label}
              </label>
            ))}
          </div>
          {message && <div className="sv-admin-error" role="alert">{message}</div>}
          <div className="sv-admin-form-actions">
            <button type="button" className="sv-btn sv-btn-outline" onClick={onClose} disabled={busy}>
              Hủy
            </button>
            <button type="submit" className="sv-modal-submit" disabled={busy}>
              {busy ? "Đang lưu..." : "Lưu thay đổi"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
