import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { updateProfile } from "../services/authService";
import { useAuth } from "../hooks/useAuth";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const LEVEL_DESC = {
  A1: "Mới bắt đầu",
  A2: "Cơ bản",
  B1: "Trung cấp",
  B2: "Trung cấp khá",
  C1: "Nâng cao",
  C2: "Thành thạo",
};
const INTERESTS = [
  { value: "technology", label: "Công nghệ thông tin" },
  { value: "business", label: "Kinh doanh" },
  { value: "travel", label: "Du lịch" },
  { value: "science", label: "Khoa học" },
  { value: "academic", label: "Tiếng Anh học thuật" },
  { value: "daily-life", label: "Giao tiếp hằng ngày" },
  { value: "general", label: "Tổng quát" },
];
const GOAL_PRESETS = [5, 10, 20, 30];

export default function OnboardingSettingsPage() {
  const navigate = useNavigate();
  const user = useAuth();
  const [level, setLevel] = useState(user?.learning_level || "");
  const [selected, setSelected] = useState(user?.interests || []);
  const [dailyGoal, setDailyGoal] = useState(user?.daily_goal || 10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    setLevel(user?.learning_level || "");
    setSelected(user?.interests || []);
    setDailyGoal(user?.daily_goal || 10);
  }, [user]);

  const toggle = (value) => {
    setSelected((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
    setError("");
    setOk("");
  };

  const applyPreset = (value) => {
    setDailyGoal(value);
    setError("");
    setOk("");
  };

  const save = async () => {
    if (!level) {
      setError("Vui lòng chọn trình độ tiếng Anh.");
      return;
    }
    if (selected.length === 0) {
      setError("Vui lòng chọn ít nhất một lĩnh vực quan tâm.");
      return;
    }
    const goal = Number(dailyGoal);
    if (!Number.isInteger(goal) || goal < 5 || goal > 100) {
      setError("Mục tiêu học mỗi ngày phải từ 5 đến 100 từ.");
      return;
    }
    setLoading(true);
    setError("");
    setOk("");
    try {
      await updateProfile({
        learning_level: level,
        interests: selected,
        daily_goal: goal,
        onboarded: true,
      });
      setOk("Đã lưu cài đặt học tập.");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Không thể lưu. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <div>
          <h2>Cài đặt học tập</h2>
          <p className="muted">Thay đổi trình độ, lĩnh vực quan tâm và mục tiêu học tập để cập nhật lộ trình đề xuất.</p>
        </div>
        <div className="settings-header-actions">
          <button className="btn btn-outline" type="button" onClick={() => navigate("/profile")}>
            Xem hồ sơ
          </button>
          <button className="btn btn-outline" type="button" onClick={() => navigate("/learn")}>
            Về trang học
          </button>
        </div>
      </div>

      <div className="card settings-card">
        <div className="settings-card-head">
          <h3>Trình độ tiếng Anh</h3>
          <p className="muted">Chọn trình độ phù hợp để SmartVOCAB đề xuất từ vựng đúng nhu cầu.</p>
        </div>
        <div className="level-card-grid">
          {LEVELS.map((l) => {
            const active = level === l;
            return (
              <button
                key={l}
                type="button"
                onClick={() => {
                  setLevel(l);
                  setError("");
                  setOk("");
                }}
                className={active ? "level-card is-active" : "level-card"}
                aria-pressed={active}
              >
                <div className="level-card-top">
                  <span className="level-code">{l}</span>
                  {active && <span className="level-check" aria-hidden="true">✓</span>}
                </div>
                <p className="level-desc">{LEVEL_DESC[l]}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div className="card settings-card">
        <div className="settings-card-head">
          <h3>Lĩnh vực quan tâm</h3>
          <p className="muted">Có thể chọn nhiều lĩnh vực để đa dạng hóa lộ trình học.</p>
        </div>
        <div className="interest-card-grid">
          {INTERESTS.map((i) => {
            const active = selected.includes(i.value);
            return (
              <button
                key={i.value}
                type="button"
                onClick={() => toggle(i.value)}
                className={active ? "interest-card is-active" : "interest-card"}
                aria-pressed={active}
              >
                <span className="interest-icon" aria-hidden="true">
                  {i.icon}
                </span>
                <span className="interest-label">{i.label}</span>
                {active && <span className="interest-check" aria-hidden="true">✓</span>}
              </button>
            );
          })}
        </div>
      </div>

      <div className="card settings-card">
        <div className="settings-card-head">
          <h3>Mục tiêu học tập</h3>
          <p className="muted">Đặt mục tiêu từ vựng mỗi ngày để duy trì thói quen học đều đặn.</p>
        </div>
        <div className="goal-section">
          <div className="goal-presets">
            {GOAL_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => applyPreset(preset)}
                className={Number(dailyGoal) === preset ? "goal-preset is-active" : "goal-preset"}
                aria-pressed={Number(dailyGoal) === preset}
              >
                {preset} từ
              </button>
            ))}
          </div>
          <div className="goal-input-group">
            <label htmlFor="settings-daily-goal">Tùy chỉnh</label>
            <div className="goal-input-wrap">
              <input
                id="settings-daily-goal"
                type="number"
                min={5}
                max={100}
                value={dailyGoal}
                onChange={(e) => {
                  setDailyGoal(e.target.value);
                  setError("");
                  setOk("");
                }}
                inputMode="numeric"
              />
              <span className="goal-suffix">từ/ngày</span>
            </div>
            <small className="muted">Giới hạn từ 5 đến 100 từ mỗi ngày.</small>
          </div>
        </div>
      </div>

      <div className="settings-actions">
        {error && <p className="auth-error" role="alert">{error}</p>}
        {ok && <p className="profile-success">{ok}</p>}
        <div className="settings-action-buttons">
          <button className="btn btn-outline settings-btn" type="button" onClick={() => navigate("/profile")}>
            Xem hồ sơ
          </button>
          <button className="settings-btn-primary" type="button" onClick={save} disabled={loading}>
            {loading ? (
              <>
                <span className="btn-spinner" aria-hidden="true" />
                Đang lưu...
              </>
            ) : (
              "Lưu thay đổi"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
