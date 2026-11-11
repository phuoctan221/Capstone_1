import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { completeOnboarding } from "../services/authService";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const LEVEL_DESC = {
  A1: "Mới bắt đầu",
  A2: "Cơ bản",
  B1: "Trung cấp",
  B2: "Trung cấp khá",
  C1: "Nâng cao",
  C2: "Thành thạo",
};

export default function OnboardingLevelPage() {
  const navigate = useNavigate();
  const [level, setLevel] = useState("");
  const [error, setError] = useState("");

  const next = () => {
    if (!level) {
      setError("Vui lòng chọn trình độ tiếng Anh của bạn.");
      return;
    }
    sessionStorage.setItem("onb_level", level);
    navigate("/onboarding/interests");
  };

  return (
    <main className="auth-page">
      <section className="auth-shell" style={{ gridTemplateColumns: "1fr" }}>
        <div className="auth-panel" style={{ margin: "0 auto", maxWidth: 720 }}>
          <div className="auth-panel-head">
            <span className="auth-kicker">BƯỚC 1/2</span>
            <h2>Chọn trình độ tiếng Anh hiện tại</h2>
            <p>Chúng tôi sẽ đề xuất từ vựng phù hợp với trình độ của bạn.</p>
          </div>
          <div className="onb-grid">
            {LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => {
                  setLevel(l);
                  setError("");
                }}
                className={`onb-choice${level === l ? " is-active" : ""}`}
              >
                <strong>{l}</strong>
                <span>{LEVEL_DESC[l]}</span>
              </button>
            ))}
          </div>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit onb-submit" type="button" onClick={next}>
            Tiếp tục
          </button>
        </div>
      </section>
    </main>
  );
}
