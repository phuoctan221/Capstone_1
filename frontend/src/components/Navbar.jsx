import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { clearSession } from "../services/authService";
import { useAuth } from "../hooks/useAuth";
import { fetchProgress } from "../services/lessonService";

export default function Navbar() {
  const user = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [progress, setProgress] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!user) {
      setProgress(null);
      return undefined;
    }
    let active = true;
    fetchProgress()
      .then((data) => {
        if (active) setProgress(data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [user?.id]);

  const handleLogout = () => {
    clearSession();
    navigate("/login");
  };

  const linkClass = ({ isActive }) =>
    isActive ? "nav-link is-active" : "nav-link";

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="logo">
          <span className="logo-mark">SV</span>
          <span className="logo-text">
            SmartVOCAB <em>AI</em>
          </span>
        </Link>

        <button
          type="button"
          className={`nav-toggle${menuOpen ? " is-open" : ""}`}
          aria-label="Mở menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav className={`nav-links${menuOpen ? " is-open" : ""}`}>
          {user ? (
            <>
              <NavLink to="/learn" className={linkClass}>
                Học
              </NavLink>
              <NavLink to="/flashcards" className={linkClass}>
                Ôn tập
              </NavLink>
              <NavLink to="/vocabulary" className={linkClass}>
                Từ vựng
              </NavLink>

              {progress && (
                <span className="nav-xp" title="XP / Chuỗi ngày / Cấp độ">
                  <span className="xp-item">
                    Lv <b>{progress.level}</b>
                  </span>
                  <span className="xp-dot" />
                  <span className="xp-item">
                    <b>{progress.xp}</b> XP
                  </span>
                  <span className="xp-dot" />
                  <span className="xp-item">{progress.streak}🔥</span>
                </span>
              )}

              <span className="nav-user" title={user.email}>
                <span className="avatar">
                  {(user.username || user.email || "?").charAt(0).toUpperCase()}
                </span>
                <span className="nav-user-name">{user.username}</span>
              </span>

              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={handleLogout}
              >
                Đăng xuất
              </button>
            </>
          ) : (
            <>
              <NavLink to="/" end className={linkClass}>
                Trang chủ
              </NavLink>
              <NavLink to="/login" className={linkClass}>
                Đăng nhập
              </NavLink>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
