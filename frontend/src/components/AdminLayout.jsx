import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearSession } from "../services/authService";
import { useAuth } from "../hooks/useAuth";
import ConfirmDialog from "./ConfirmDialog";
import "./AdminLayout.css";
import "../pages/AdminPages.css";

const NAV_ITEMS = [
  { to: "/admin", end: true, icon: "◫", label: "Tổng quan", hint: "Số liệu hệ thống" },
  { to: "/admin/users", icon: "♙", label: "Người dùng", hint: "Vai trò & quyền" },
  { to: "/admin/vocabulary", icon: "Aa", label: "Từ vựng", hint: "Kho từ dùng chung" },
  { to: "/admin/domains", icon: "◈", label: "Lĩnh vực", hint: "General / IT / Business" },
  { to: "/admin/lessons", icon: "▤", label: "Bài học", hint: "Theo lĩnh vực & cấp độ" },
  { to: "/admin/exercises", icon: "✎", label: "Câu hỏi", hint: "Meaning / Spelling / Context" },
];

export default function AdminLayout() {
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
    <div className="sv-admin-shell">
      <aside className={`sv-admin-sidebar${open ? " is-open" : ""}`}>
        <div className="sv-admin-sidebar-head">
          <Link className="sv-admin-brand" to="/admin" aria-label="SmartVocab AI Admin">
            <span className="sv-admin-brand-mark">S<span>✦</span></span>
            <span className="sv-admin-brand-name">Smart<span>Vocab</span><em> AI</em></span>
            <span className="sv-admin-role-chip">ADMIN</span>
          </Link>
          <button
            type="button"
            className="sv-admin-menu"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-label={open ? "Đóng menu quản trị" : "Mở menu quản trị"}
          >
            {open ? "✕" : "☰"}
          </button>
        </div>

        <div className="sv-admin-sidebar-user">
          <span className="sv-admin-avatar">{String(user?.username || user?.email || "A").charAt(0).toUpperCase()}</span>
          <div>
            <strong>{user?.username || "Quản trị viên"}</strong>
            <small>{user?.email}</small>
          </div>
        </div>

        <nav className="sv-admin-nav" aria-label="Điều hướng quản trị">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `sv-admin-nav-link${isActive ? " active" : ""}`}
            >
              <span className="sv-admin-nav-icon" aria-hidden="true">{item.icon}</span>
              <span><b>{item.label}</b><small>{item.hint}</small></span>
            </NavLink>
          ))}
        </nav>

        <div className="sv-admin-sidebar-foot">
          <p>Khu vực quản trị tách biệt. Mọi API đều được backend xác thực quyền Admin.</p>
          <button type="button" className="sv-admin-logout" onClick={() => setAskLogout(true)}>
            <span aria-hidden="true">↪</span> Đăng xuất
          </button>
        </div>
      </aside>
      <ConfirmDialog
        open={askLogout}
        title="Đăng xuất khỏi khu vực quản trị?"
        message="Bạn có muốn đăng xuất không? Session quản trị sẽ kết thúc ngay lập tức."
        confirmText="Đăng xuất"
        cancelText="Ở lại"
        danger
        onConfirm={logout}
        onCancel={() => setAskLogout(false)}
      />
      <main className="sv-admin-main">
        <div className="sv-admin-container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
