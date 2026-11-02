import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMe, updateProfile, changePassword } from "../services/authService";
import { fetchProgress } from "../services/lessonService";
import { useAuth } from "../hooks/useAuth";

const LEVEL_DESC = {
  A1: "Mới bắt đầu",
  A2: "Cơ bản",
  B1: "Trung cấp",
  B2: "Trung cấp khá",
  C1: "Nâng cao",
  C2: "Thành thạo",
};

const INTEREST_LABELS = {
  technology: "Công nghệ thông tin",
  business: "Kinh doanh",
  travel: "Du lịch",
  science: "Khoa học",
  academic: "Tiếng Anh học thuật",
  "daily-life": "Giao tiếp hằng ngày",
  general: "Tổng quát",
};

function formatDate(value) {
  if (!value) return "—";
  try {
    const date = typeof value === "string" ? new Date(value) : value;
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleDateString("vi-VN");
  } catch {
    return "—";
  }
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const user = useAuth();
  const [profile, setProfile] = useState(user);
  const [progress, setProgress] = useState(null);
  const [username, setUsername] = useState(user?.username || "");
  const [dailyGoal, setDailyGoal] = useState(user?.daily_goal || 10);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPw, setChangingPw] = useState(false);
  const [pwError, setPwError] = useState("");
  const [pwOk, setPwOk] = useState("");

  useEffect(() => {
    setProfile(user);
    setUsername(user?.username || "");
    setDailyGoal(user?.daily_goal || 10);
  }, [user]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [me, pg] = await Promise.allSettled([fetchMe(), fetchProgress()]);
        if (!active) return;
        if (me.status === "fulfilled") {
          setProfile(me.value);
          setUsername(me.value?.username || "");
          setDailyGoal(me.value?.daily_goal || 10);
        }
        if (pg.status === "fulfilled") {
          setProgress(pg.value);
        }
      } catch {
        // ignore
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const save = async (event) => {
    event.preventDefault();
    if (saving) return;
    if (!username.trim()) {
      setError("Vui lòng nhập họ tên hiển thị.");
      return;
    }
    if (username.trim().length < 3) {
      setError("Họ tên hiển thị cần ít nhất 3 ký tự.");
      return;
    }
    const goal = Number(dailyGoal);
    if (!Number.isInteger(goal) || goal < 5 || goal > 100) {
      setError("Mục tiêu học mỗi ngày phải từ 5 đến 100 từ.");
      return;
    }
    setSaving(true);
    setError("");
    setOk("");
    try {
      await updateProfile({
        username: username.trim(),
        daily_goal: goal,
      });
      setOk("Đã cập nhật hồ sơ cá nhân.");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Không thể cập nhật hồ sơ. Vui lòng thử lại.");
    } finally {
      setSaving(false);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    if (changingPw) return;
    setPwError("");
    setPwOk("");
    if (!currentPassword) {
      setPwError("Vui lòng nhập mật khẩu hiện tại.");
      return;
    }
    if (!newPassword) {
      setPwError("Vui lòng nhập mật khẩu mới.");
      return;
    }
    if (newPassword.length < 6) {
      setPwError("Mật khẩu mới cần ít nhất 6 ký tự.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwError("Xác nhận mật khẩu mới không khớp.");
      return;
    }
    if (currentPassword === newPassword) {
      setPwError("Mật khẩu mới phải khác mật khẩu hiện tại.");
      return;
    }
    setChangingPw(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPwOk("Đổi mật khẩu thành công.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setPwError(typeof detail === "string" ? detail : "Không thể đổi mật khẩu. Vui lòng thử lại.");
    } finally {
      setChangingPw(false);
    }
  };

  const displayName = profile?.username || user?.username || "Người dùng";
  const email = profile?.email || user?.email || "";
  const initial = (displayName || email || "?").charAt(0).toUpperCase();
  const level = profile?.learning_level || user?.learning_level || progress?.level;
  const interests = Array.isArray(profile?.interests) ? profile.interests : user?.interests || [];

  return (
    <div className="profile-page">
      <div className="profile-top">
        <div className="profile-top-left">
          <div className="profile-avatar-large">{initial}</div>
          <div className="profile-top-info">
            <h2>{displayName}</h2>
            <p className="profile-top-meta">{email}</p>
            <p className="profile-top-meta">Ngày tham gia: {formatDate(profile?.created_at)}</p>
          </div>
        </div>
      </div>

      <div className="profile-stats-row">
        <div className="profile-stat-card">
          <span className="profile-stat-label">Level</span>
          <span className="profile-stat-value">{level ? `${level}` : "—"}</span>
        </div>
        <div className="profile-stat-card">
          <span className="profile-stat-label">XP</span>
          <span className="profile-stat-value">{progress?.xp ?? 0}</span>
        </div>
        <div className="profile-stat-card">
          <span className="profile-stat-label">Streak</span>
          <span className="profile-stat-value">{progress?.streak ?? 0} 🔥</span>
        </div>
      </div>

      <div className="profile-main-grid">
        <div className="card profile-edit-card">
          <div className="profile-card-header">
            <h3>Chỉnh sửa hồ sơ</h3>
          </div>
          <form onSubmit={save} className="profile-form">
            <div className="form-group">
              <label htmlFor="profile-username">Họ tên</label>
              <input
                id="profile-username"
                name="username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  setError("");
                  setOk("");
                }}
                minLength={3}
                maxLength={30}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="profile-email">Email</label>
              <input id="profile-email" value={email} readOnly />
            </div>

            <div className="form-group">
              <label htmlFor="profile-goal">Mục tiêu học mỗi ngày</label>
              <div className="profile-input-suffix">
                <input
                  id="profile-goal"
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
                <span className="profile-suffix-text">từ/ngày</span>
              </div>
            </div>

            {error && <p className="auth-error" role="alert">{error}</p>}
            {ok && <p className="profile-success">{ok}</p>}

            <div className="profile-form-actions">
              <button className="profile-btn-primary" type="submit" disabled={saving}>
                {saving ? (
                  <>
                    <span className="btn-spinner" aria-hidden="true" />
                    Đang lưu...
                  </>
                ) : (
                  "Lưu thay đổi"
                )}
              </button>
            </div>
          </form>
          {loading && <p className="muted" style={{ marginTop: "0.8rem" }}>Đang đồng bộ dữ liệu...</p>}
        </div>

        <div className="card profile-summary-info-card">
          <div className="profile-card-header">
            <h3>Tóm tắt trình độ</h3>
          </div>
          <div className="profile-summary-block">
            <div className="profile-summary-row">
              <span className="profile-summary-label">Trình độ</span>
              <span className="profile-pill">{level ? `${level}${LEVEL_DESC[level] ? ` · ${LEVEL_DESC[level]}` : ""}` : "Chưa thiết lập"}</span>
            </div>
            <div className="profile-summary-row">
              <span className="profile-summary-label">Lĩnh vực</span>
              <div className="profile-chip-list">
                {interests.length === 0 && <span className="muted">Chưa thiết lập</span>}
                {interests.map((item) => (
                  <span key={item} className="profile-chip">
                    {INTEREST_LABELS[item] || item}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="profile-summary-footer">
            <button className="profile-btn-secondary" type="button" onClick={() => navigate("/settings/learning")}>
              Cài đặt học tập
            </button>
          </div>
        </div>
      </div>

      <div className="card profile-password-card">
        <div className="profile-card-header">
          <h3>Đổi mật khẩu</h3>
        </div>
        <form onSubmit={savePassword} className="profile-password-form">
          <div className="profile-password-grid">
            <div className="form-group">
              <label htmlFor="current-password">Mật khẩu hiện tại</label>
              <input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => {
                  setCurrentPassword(e.target.value);
                  setPwError("");
                  setPwOk("");
                }}
                autoComplete="current-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="new-password">Mật khẩu mới</label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value);
                  setPwError("");
                  setPwOk("");
                }}
                minLength={6}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="confirm-password">Xác nhận mật khẩu mới</label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  setPwError("");
                  setPwOk("");
                }}
                minLength={6}
                autoComplete="new-password"
              />
            </div>
          </div>
          {pwError && <p className="auth-error" role="alert">{pwError}</p>}
          {pwOk && <p className="profile-success">{pwOk}</p>}
          <div className="profile-form-actions">
            <button className="profile-btn-primary" type="submit" disabled={changingPw}>
              {changingPw ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  Đang đổi...
                </>
              ) : (
                "Đổi mật khẩu"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
