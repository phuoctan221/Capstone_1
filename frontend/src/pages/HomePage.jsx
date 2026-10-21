import { Link } from "react-router-dom";
import { getUser } from "../services/authService";

export default function HomePage() {
  const user = getUser();

  return (
    <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
      <h1 style={{ color: "var(--primary)" }}>SmartVOCAB AI</h1>
      <p className="muted" style={{ margin: "1rem 0 2rem", fontSize: "1.1rem" }}>
        Học từ vựng tiếng Anh theo lộ trình — 4 chế độ luyện tập, tích XP, giữ
        chuỗi ngày học, ôn tập thông minh theo phương pháp Leitner.
      </p>
      {user ? (
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <Link to="/learn" className="btn">
            Bắt đầu học
          </Link>
          <Link to="/flashcards" className="btn btn-outline">
            Ôn tập hôm nay
          </Link>
        </div>
      ) : (
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <Link to="/register" className="btn">
            Bắt đầu miễn phí
          </Link>
          <Link to="/login" className="btn btn-outline">
            Đăng nhập
          </Link>
        </div>
      )}

      <div className="home-features">
        <div className="feature">
          <div className="feature-icon">🎯</div>
          <h3>4 chế độ học</h3>
          <p className="muted">Trắc nghiệm, gõ từ, nghe, thẻ ghi nhớ</p>
        </div>
        <div className="feature">
          <div className="feature-icon">📈</div>
          <h3>Lộ trình rõ ràng</h3>
          <p className="muted">Học theo chủ đề, mở khóa dần theo tiến độ</p>
        </div>
        <div className="feature">
          <div className="feature-icon">🔥</div>
          <h3>Tích XP & chuỗi ngày</h3>
          <p className="muted">Lên cấp, duy trì thói quen học mỗi ngày</p>
        </div>
        <div className="feature">
          <div className="feature-icon">🧠</div>
          <h3>Ôn tập thông minh</h3>
          <p className="muted">Leitner 5 hộp, nhắc đúng lúc bạn sắp quên</p>
        </div>
      </div>
    </div>
  );
}
