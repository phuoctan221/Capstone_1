import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { completeOnboarding } from "../services/authService";

const INTERESTS = [
  { value: "technology", label: "Công nghệ thông tin" },
  { value: "business", label: "Kinh doanh" },
  { value: "travel", label: "Du lịch" },
  { value: "science", label: "Khoa học" },
  { value: "academic", label: "Tiếng Anh học thuật" },
  { value: "daily-life", label: "Giao tiếp hằng ngày" },
  { value: "general", label: "Tổng quát" },
];

export default function OnboardingInterestsPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggle = (value) => {
    setSelected((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
    setError("");
  };

  const submit = async () => {
    const level = sessionStorage.getItem("onb_level");
    if (!level) {
      navigate("/onboarding/level");
      return;
    }
    if (selected.length === 0) {
      setError("Vui lòng chọn ít nhất một lĩnh vực quan tâm.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await completeOnboarding({ learning_level: level, interests: selected });
      sessionStorage.removeItem("onb_level");
      navigate("/learn");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Không thể lưu hồ sơ. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-shell" style={{ gridTemplateColumns: "1fr" }}>
        <div className="auth-panel" style={{ margin: "0 auto", maxWidth: 720 }}>
          <div className="auth-panel-head">
            <span className="auth-kicker">BƯỚC 2/2</span>
            <h2>Chọn lĩnh vực quan tâm</h2>
            <p>Chọn một hoặc nhiều lĩnh vực để nhận lộ trình học phù hợp.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem" }}>
            {INTERESTS.map((i) => {
              const active = selected.includes(i.value);
              return (
                <button
                  key={i.value}
                  type="button"
                  onClick={() => toggle(i.value)}
                  className={active ? "auth-submit" : "btn btn-outline"}
                  style={{ justifyContent: "center" }}
                >
                  {i.label}
                </button>
              );
            })}
          </div>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
            <button className="btn btn-outline" type="button" onClick={() => navigate("/onboarding/level")}>
              Quay lại
            </button>
            <button className="auth-submit" type="button" onClick={submit} disabled={loading} style={{ flex: 1 }}>
              {loading ? "Đang lưu..." : "Hoàn tất"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
