import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { updateProfile } from "../services/authService";
import { useAuth } from "../hooks/useAuth";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const LEVEL_ORDER = { A1: 0, A2: 1, B1: 2, B2: 3, C1: 4, C2: 5 };
const LEVEL_DESC = {
  A1: "Mới bắt đầu",
  A2: "Cơ bản",
  B1: "Trung cấp",
  B2: "Trung cấp khá",
  C1: "Nâng cao",
  C2: "Thành thạo",
};
const INTERESTS = [
  { value: "general", label: "General English" },
  { value: "technology", label: "IT & Technology" },
  { value: "business", label: "Business English" },
];
const GOAL_PRESETS = [5, 10, 20, 30];

export default function OnboardingSettingsPage() {
  const navigate = useNavigate();
  const user = useAuth();
  const currentLevel = user?.learning_level || "";
  const [level, setLevel] = useState(currentLevel);
  const [selected, setSelected] = useState(user?.interests || []);
  const [dailyGoal, setDailyGoal] = useState(user?.daily_goal || 10);
  const [dailyNewLimit, setDailyNewLimit] = useState(user?.daily_new_limit || 10);
  const [dailyReviewLimit, setDailyReviewLimit] = useState(user?.daily_review_limit || 30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  // Modal state for level-up confirmation
  const [showLevelUpModal, setShowLevelUpModal] = useState(false);
  const [pendingLevel, setPendingLevel] = useState(null);

  useEffect(() => {
    setLevel(user?.learning_level || "");
    setSelected(user?.interests || []);
    setDailyGoal(user?.daily_goal || 10);
    setDailyNewLimit(user?.daily_new_limit || 10);
    setDailyReviewLimit(user?.daily_review_limit || 30);
  }, [user]);

  const isHigherLevel = (targetLevel) => {
    if (!currentLevel || !targetLevel) return false;
    return (LEVEL_ORDER[targetLevel] ?? 0) > (LEVEL_ORDER[currentLevel] ?? 0);
  };

  const handleLevelClick = (l) => {
    setError("");
    setOk("");
    if (isHigherLevel(l)) {
      // Show confirmation modal instead of selecting directly
      setPendingLevel(l);
      setShowLevelUpModal(true);
    } else {
      // Same level or lower: allow direct selection
      setLevel(l);
    }
  };

  const confirmLevelUpTest = () => {
    setShowLevelUpModal(false);
    const interests = selected.length > 0 ? selected : (user?.interests || ["general"]);
    const testDomain = interests[0] || "general";
    const domainsParam = encodeURIComponent(interests.join(","));
    navigate(
      `/assessments/${testDomain}/${pendingLevel.toLowerCase()}?placement=1&skip=1&domains=${domainsParam}&return=/settings/learning`
    );
  };

  const cancelLevelUp = () => {
    setShowLevelUpModal(false);
    setPendingLevel(null);
  };

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
    const newLimit = Number(dailyNewLimit);
    const reviewLimit = Number(dailyReviewLimit);
    if (!Number.isInteger(goal) || goal < 5 || goal > 100) {
      setError("Mục tiêu học mỗi ngày phải từ 5 đến 100 từ.");
      return;
    }
    if (!Number.isInteger(newLimit) || newLimit < 1 || newLimit > 100) {
      setError("Số từ mới mỗi ngày phải từ 1 đến 100 từ.");
      return;
    }
    if (!Number.isInteger(reviewLimit) || reviewLimit < 1 || reviewLimit > 200) {
      setError("Số từ ôn mỗi ngày phải từ 1 đến 200 từ.");
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
        daily_new_limit: newLimit,
        daily_review_limit: reviewLimit,
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
          <p className="muted">
            Chọn trình độ phù hợp để SmartVOCAB đề xuất từ vựng đúng nhu cầu.
            {currentLevel && (
              <span className="level-current-hint">
                {" "}Trình độ hiện tại: <strong>{currentLevel}</strong>. Muốn nâng cấp lên trình độ cao hơn cần hoàn thành bài kiểm tra đánh giá (đạt 85%).
              </span>
            )}
          </p>
        </div>
        <div className="level-card-grid">
          {LEVELS.map((l) => {
            const active = level === l;
            const locked = isHigherLevel(l);
            return (
              <button
                key={l}
                type="button"
                onClick={() => handleLevelClick(l)}
                className={`level-card ${active ? "is-active" : ""} ${locked ? "is-locked" : ""}`}
                aria-pressed={active}
              >
                <div className="level-card-top">
                  <span className="level-code">{l}</span>
                  {active && <span className="level-check" aria-hidden="true">✓</span>}
                  {locked && !active && <span className="level-lock" aria-hidden="true">🔒</span>}
                </div>
                <p className="level-desc">{LEVEL_DESC[l]}</p>
                {locked && !active && (
                  <span className="level-test-hint">Cần thi để mở khóa</span>
                )}
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
          <div className="goal-input-group">
            <label htmlFor="settings-new-limit">Từ mới mỗi ngày</label>
            <div className="goal-input-wrap">
              <input
                id="settings-new-limit"
                type="number"
                min={1}
                max={100}
                value={dailyNewLimit}
                onChange={(e) => {
                  setDailyNewLimit(e.target.value);
                  setError("");
                  setOk("");
                }}
                inputMode="numeric"
              />
              <span className="goal-suffix">từ/ngày</span>
            </div>
          </div>
          <div className="goal-input-group">
            <label htmlFor="settings-review-limit">Từ ôn mỗi ngày</label>
            <div className="goal-input-wrap">
              <input
                id="settings-review-limit"
                type="number"
                min={1}
                max={200}
                value={dailyReviewLimit}
                onChange={(e) => {
                  setDailyReviewLimit(e.target.value);
                  setError("");
                  setOk("");
                }}
                inputMode="numeric"
              />
              <span className="goal-suffix">từ/ngày</span>
            </div>
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

      {/* Level-up Confirmation Modal */}
      {showLevelUpModal && (
        <div className="level-up-modal-overlay" onClick={cancelLevelUp}>
          <div className="level-up-modal" onClick={(e) => e.stopPropagation()}>
            <div className="level-up-modal-icon">📝</div>
            <h3>Bài kiểm tra thăng hạng</h3>
            <p>
              Để nâng trình độ lên <strong>{pendingLevel}</strong> ({LEVEL_DESC[pendingLevel]}),
              bạn cần hoàn thành bài kiểm tra đánh giá gồm <strong>20 câu hỏi</strong>.
            </p>
            <div className="level-up-modal-details">
              <div className="detail-row">
                <span>Số câu hỏi:</span>
                <strong>20 câu</strong>
              </div>
              <div className="detail-row">
                <span>Điểm cần đạt:</span>
                <strong>85% (17/20 câu đúng)</strong>
              </div>
              <div className="detail-row">
                <span>Thời gian làm bài:</span>
                <strong>20 phút</strong>
              </div>
              <div className="detail-row">
                <span>Thời gian chờ thi lại:</span>
                <strong>15 phút</strong>
              </div>
            </div>
            <p className="level-up-modal-note">
              Nếu không đạt, bạn có thể thi lại sau 15 phút. Bạn đã sẵn sàng chưa?
            </p>
            <div className="level-up-modal-actions">
              <button className="sv-btn sv-btn-outline" onClick={cancelLevelUp}>
                Hủy
              </button>
              <button className="sv-btn sv-btn-primary" onClick={confirmLevelUpTest}>
                Bắt đầu làm bài thi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
