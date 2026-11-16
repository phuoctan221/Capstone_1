import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { clearSession } from "../services/authService";
import { useAuth } from "../hooks/useAuth";
import ConfirmDialog from "./ConfirmDialog";

const linkClass = ({ isActive }) => `sv-nav-link${isActive ? " active" : ""}`;

export default function Navbar() {
  const user = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [askLogout, setAskLogout] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const logout = () => {
    setAskLogout(false);
    clearSession();
    navigate("/login", { replace: true });
  };

  return (
    <>
      <header className="sv-navbar">
      <div className="sv-navbar-inner">
        <Link className="sv-brand" to="/dashboard" aria-label="SmartVocab AI - Dashboard">
          <span className="sv-brand-mark">S<span>✦</span></span>
          <span className="sv-brand-name">Smart<span>Vocab</span><em> AI</em></span>
        </Link>
        <button
          className="sv-mobile-menu"
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-label={open ? "Đóng menu" : "Mở menu"}
        >
          {open ? "✕" : "☰"}
        </button>
        <nav className={`sv-main-nav${open ? " is-open" : ""}`} aria-label="Điều hướng học tập">
          <NavLink to="/dashboard" className={linkClass}>Tổng quan</NavLink>
          <NavLink to="/learn" className={linkClass}>Lộ trình học</NavLink>
          <NavLink to="/flashcards" className={linkClass}>Ôn tập FSRS</NavLink>
          <NavLink to="/progress" className={linkClass}>Tiến độ</NavLink>
          <NavLink to="/vocabulary" className={linkClass}>Từ vựng</NavLink>
        </nav>
        <div className="sv-navbar-right">
          <Link className="sv-user-chip" to="/profile" title={user?.email || "Hồ sơ"}>
            <span>{String(user?.username || user?.email || "?").charAt(0).toUpperCase()}</span>
            <b>{user?.username || "Tài khoản"}</b>
          </Link>
          <button type="button" className="sv-logout" onClick={() => setAskLogout(true)} title="Đăng xuất" aria-label="Đăng xuất">↪</button>
        </div>
      </div>
    </header>
    <ConfirmDialog
      open={askLogout}
      title="Đăng xuất?"
      message="Bạn có muốn đăng xuất không? Toàn bộ tiến độ học tập của bạn vẫn được lưu an toàn."
      confirmText="Đăng xuất"
      cancelText="Ở lại"
      danger
      onConfirm={logout}
      onCancel={() => setAskLogout(false)}
    />
    </>
  );
}
