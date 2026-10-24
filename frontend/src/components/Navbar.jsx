import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { clearSession } from "../services/authService";
import { useAuth } from "../hooks/useAuth";
import { fetchProgress } from "../services/lessonService";

export default function Navbar() {
  const user = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [progress, setProgress] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef(null);

  useEffect(() => {
    setMenuOpen(false);
    setAccountOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (accountRef.current && !accountRef.current.contains(event.target)) {
        setAccountOpen(false);
      }
    }
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setAccountOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

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
    setAccountOpen(false);
    clearSession();
    navigate("/login");
  };

  const goToProfile = () => {
    setAccountOpen(false);
    navigate("/profile");
  };

  const goToSettings = () => {
    setAccountOpen(false);
    navigate("/settings/learning");
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

              <div className="nav-account" ref={accountRef}>
                <button
                  type="button"
                  className="nav-user nav-user-button"
                  title={user.email}
                  aria-haspopup="menu"
                  aria-expanded={accountOpen}
                  onClick={() => setAccountOpen((v) => !v)}
                >
                  <span className="avatar">
                    {(user.username || user.email || "?").charAt(0).toUpperCase()}
                  </span>
                  <span className="nav-user-name">{user.username}</span>
                  <span className="nav-caret">▾</span>
                </button>
                {accountOpen && (
                  <div className="nav-dropdown" role="menu">
                    <button type="button" className="nav-dropdown-item" onClick={goToProfile} role="menuitem">
                      Hồ sơ cá nhân
                    </button>
                    <button type="button" className="nav-dropdown-item" onClick={goToSettings} role="menuitem">
                      Cài đặt học tập
                    </button>
                    <div className="nav-dropdown-divider" />
                    <button type="button" className="nav-dropdown-item nav-dropdown-logout" onClick={handleLogout} role="menuitem">
                      Đăng xuất
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
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
