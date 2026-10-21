import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getUser, clearSession } from "../services/authService";
import { fetchProgress } from "../services/lessonService";

export default function Navbar() {
  const user = getUser();
  const navigate = useNavigate();
  const [progress, setProgress] = useState(null);

  useEffect(() => {
    if (user) {
      fetchProgress().then(setProgress).catch(() => {});
    }
  }, []);

  const handleLogout = () => {
    clearSession();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <Link to="/" className="logo">
        SmartVOCAB AI
      </Link>
      <nav>
        {user ? (
          <>
            <Link to="/learn">Học</Link>
            <Link to="/flashcards">Ôn tập</Link>
            <Link to="/vocabulary">Từ vựng</Link>
            {progress && (
              <span className="nav-xp" title="XP / Chuỗi ngày / Cấp độ">
                <span>Lv {progress.level}</span>
                <span>{progress.xp} XP</span>
                <span>{progress.streak}🔥</span>
              </span>
            )}
            <button className="btn btn-outline" onClick={handleLogout}>
              Đăng xuất
            </button>
          </>
        ) : (
          <>
            <Link to="/login">Đăng nhập</Link>
            <Link to="/register" className="btn">
              Đăng ký
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
