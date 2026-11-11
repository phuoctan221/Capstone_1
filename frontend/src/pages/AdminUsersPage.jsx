import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteAdminUser,
  fetchAdminUsers,
  resetAdminUserPassword,
  setAdminUserStatus,
  setUserRole,
  updateAdminUser,
} from "../services/adminService";
import { formatApiError, formatDate } from "../constants/domains";
import { useAuth } from "../hooks/useAuth";
import ConfirmDialog from "../components/ConfirmDialog";
import AdminUserEditModal from "../components/AdminUserEditModal";
import { EmptyState, PageError, PageLoading } from "../components/PageState";

const PAGE_SIZE = 50;

const CONFIRM_TEXT = {
  delete: {
    title: "Xóa tài khoản?",
    message: (user) =>
      `Xóa vĩnh viễn ${user.email} cùng toàn bộ dữ liệu học (tiến độ, phiên học, bài ôn tập)? Không thể hoàn tác.`,
    confirmText: "Xóa vĩnh viễn",
    danger: true,
    notice: (user) => `Đã xóa tài khoản ${user.email}.`,
  },
  lock: {
    title: "Khóa tài khoản?",
    message: (user) =>
      `${user.email} sẽ không thể đăng nhập cho tới khi được mở khóa.`,
    confirmText: "Khóa tài khoản",
    danger: true,
    notice: (user) => `Đã khóa tài khoản ${user.email}.`,
  },
  unlock: {
    title: "Mở khóa tài khoản?",
    message: (user) => `${user.email} có thể đăng nhập lại bình thường.`,
    confirmText: "Mở khóa",
    danger: false,
    notice: (user) => `Đã mở khóa tài khoản ${user.email}.`,
  },
  role: {
    title: (user) =>
      user.role === "admin" ? "Thu quyền Admin?" : "Cấp quyền Admin?",
    message: (user) =>
      user.role === "admin"
        ? `Thu quyền Admin của ${user.email}?`
        : `Cấp toàn quyền Admin cho ${user.email}?`,
    confirmText: (user) => (user.role === "admin" ? "Thu quyền" : "Cấp quyền"),
    danger: false,
    notice: (user) => `Đã cập nhật vai trò của ${user.email}.`,
  },
  reset: {
    title: "Đặt lại mật khẩu?",
    message: (user) =>
      `Mật khẩu hiện tại của ${user.email} sẽ mất hiệu lực. Hệ thống sẽ tạo mật khẩu mới và chỉ hiển thị một lần.`,
    confirmText: "Đặt lại mật khẩu",
    danger: false,
  },
};

export default function AdminUsersPage() {
  const me = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState("");
  const [resetResult, setResetResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminUsers({
        page,
        page_size: PAGE_SIZE,
        search: search.trim() || undefined,
        role: role || undefined,
      });
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotal(Number(data.total) || 0);
    } catch (err) {
      setError(formatApiError(err, "Không thể tải danh sách tài khoản."));
    } finally {
      setLoading(false);
    }
  }, [page, search, role]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [search, role]);

  async function runAction() {
    const current = confirm;
    if (!current) return;
    const { kind, user } = current;
    setBusyId(user.id);
    setError("");
    setNotice("");
    try {
      if (kind === "role") {
        await setUserRole(user.id, user.role === "admin" ? "user" : "admin");
        setNotice(CONFIRM_TEXT[kind].notice(user));
        await load();
      } else if (kind === "lock") {
        await setAdminUserStatus(user.id, false);
        setNotice(CONFIRM_TEXT[kind].notice(user));
        await load();
      } else if (kind === "unlock") {
        await setAdminUserStatus(user.id, true);
        setNotice(CONFIRM_TEXT[kind].notice(user));
        await load();
      } else if (kind === "delete") {
        await deleteAdminUser(user.id);
        setNotice(CONFIRM_TEXT[kind].notice(user));
        await load();
      } else if (kind === "reset") {
        const result = await resetAdminUserPassword(user.id);
        setResetResult(result);
        setCopied(false);
      }
    } catch (err) {
      setError(formatApiError(err, "Thao tác thất bại."));
    } finally {
      setBusyId(null);
      setConfirm(null);
    }
  }

  async function saveEdit(payload) {
    setEditBusy(true);
    setEditError("");
    try {
      const updated = await updateAdminUser(editing.id, payload);
      setNotice(
        `Đã cập nhật thông tin ${updated.email || editing.email}${
          updated.email && updated.email !== editing.email ? ` (email cũ: ${editing.email})` : ""
        }.`,
      );
      setEditing(null);
      await load();
    } catch (err) {
      setEditError(formatApiError(err, "Không thể cập nhật thông tin."));
    } finally {
      setEditBusy(false);
    }
  }

  async function copyResetPassword() {
    try {
      await navigator.clipboard.writeText(resetResult.password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const confirmConfig = confirm ? CONFIRM_TEXT[confirm.kind] : null;

  return (
    <div className="sv-page sv-admin-page">
      <div className="sv-page-heading">
        <div>
          <span className="sv-eyebrow">ADMIN / TÀI KHOẢN</span>
          <h1>Quản lý người dùng</h1>
          <p>
            Tìm kiếm, sửa thông tin, đặt lại mật khẩu, khóa/mở khóa hoặc xóa tài khoản.
            Không thể tự khóa hoặc xóa chính mình, không thể xóa Admin cuối cùng.
          </p>
        </div>
        <span className="sv-catalog-count">{total} tài khoản</span>
      </div>

      <div className="sv-admin-toolbar">
        <input className="sv-answer-field sv-admin-grow" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo email hoặc tên đăng nhập..." aria-label="Tìm tài khoản" />
        <select className="sv-answer-field" value={role} onChange={(event) => setRole(event.target.value)} aria-label="Lọc theo vai trò">
          <option value="">Tất cả vai trò</option>
          <option value="admin">Admin</option>
          <option value="user">Người học</option>
        </select>
        <button type="button" className="sv-admin-refresh" onClick={load} disabled={loading}>{loading ? "Đang tải..." : "↻ Làm mới"}</button>
        <span className="sv-admin-count">Trang {page}/{pages}</span>
      </div>

      {notice && <div className="sv-admin-success" role="status">{notice}</div>}
      {error && <div className="sv-admin-error" role="alert">{error}</div>}

      {loading && !items.length ? <PageLoading label="Đang tải tài khoản..." /> : error && !items.length ? <PageError message={error} onRetry={load} /> : (
        <>
          <div className="sv-admin-table-wrap">
            <table className="sv-admin-table sv-users-table">
              <thead>
                <tr>
                  <th>Người dùng</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th>Trình độ</th>
                  <th>Hoạt động</th>
                  <th>Ngày tạo</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {items.length ? items.map((user) => {
                  const self = user.id === me?.id;
                  const locked = user.is_active === false;
                  return (
                    <tr key={user.id} className={locked ? "is-locked" : undefined}>
                      <td>
                        <div className="sv-admin-cell-main">
                          <span className="sv-admin-avatar-sm">{String(user.username || user.email || "?").charAt(0).toUpperCase()}</span>
                          <span><strong>{user.username || "—"} {self && <span className="sv-admin-badge self">Bạn</span>}</strong><small>{user.email}</small></span>
                        </div>
                      </td>
                      <td><span className={`sv-admin-badge ${user.role}`}>{user.role === "admin" ? "Admin" : "Người học"}</span></td>
                      <td><span className={`sv-admin-badge ${locked ? "locked" : "ok"}`}>{locked ? "Đã khóa" : "Hoạt động"}</span></td>
                      <td>{user.learning_level || "—"}</td>
                      <td><span className="sv-admin-strong">{user.xp ?? 0} XP</span><br /><small className="sv-admin-muted">{user.streak ?? 0} ngày liên tiếp</small></td>
                      <td className="sv-admin-muted">{formatDate(user.created_at)}</td>
                      <td>
                        <div className="sv-user-actions">
                          <Link className="sv-admin-mini" to={`/admin/users/${user.id}`}>Chi tiết</Link>
                          <button type="button" className="sv-admin-mini" onClick={() => { setEditError(""); setEditing(user); }} disabled={busyId === user.id}>Sửa</button>
                          <button type="button" className="sv-admin-mini" onClick={() => setConfirm({ kind: "reset", user })} disabled={busyId === user.id}>Reset MK</button>
                          <button type="button" className="sv-admin-mini" onClick={() => setConfirm({ kind: locked ? "unlock" : "lock", user })} disabled={busyId === user.id || (!locked && self)} title={self && !locked ? "Không thể tự khóa chính bạn" : undefined}>{locked ? "Mở khóa" : "Khóa"}</button>
                          <button type="button" className="sv-admin-mini" onClick={() => setConfirm({ kind: "role", user })} disabled={busyId === user.id || (user.role === "admin" && self)}>{user.role === "admin" ? "Thu quyền" : "Cấp Admin"}</button>
                          <button type="button" className="sv-admin-mini danger" onClick={() => setConfirm({ kind: "delete", user })} disabled={busyId === user.id || self} title={self ? "Không thể xóa chính bạn" : undefined}>Xóa</button>
                        </div>
                      </td>
                    </tr>
                  );
                }) : <tr><td colSpan={7} className="sv-admin-empty-cell"><strong>Không tìm thấy tài khoản</strong>Thử thay đổi từ khoá tìm kiếm hoặc bộ lọc vai trò.</td></tr>}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <div className="sv-admin-pagination">
              <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>← Trước</button>
              <span>Trang {page} / {pages}</span>
              <button type="button" onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages}>Sau →</button>
            </div>
          )}
          {!items.length && !loading && !error && <EmptyState title="Chưa có tài khoản" description="Tài khoản mới sẽ xuất hiện sau khi đăng ký." />}
        </>
      )}

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirmConfig && (typeof confirmConfig.title === "function" ? confirmConfig.title(confirm.user) : confirmConfig.title)}
        message={confirmConfig && confirmConfig.message(confirm.user)}
        confirmText={confirmConfig && (typeof confirmConfig.confirmText === "function" ? confirmConfig.confirmText(confirm.user) : confirmConfig.confirmText)}
        danger={Boolean(confirmConfig && confirmConfig.danger)}
        busy={busyId !== null}
        onConfirm={runAction}
        onCancel={() => setConfirm(null)}
      />

      {editing && (
        <AdminUserEditModal
          user={editing}
          busy={editBusy}
          error={editError}
          onSave={saveEdit}
          onClose={() => setEditing(null)}
        />
      )}

      {resetResult && (
        <div className="sv-modal-overlay" onClick={() => setResetResult(null)} role="presentation">
          <div className="sv-modal-card" role="dialog" aria-modal="true" aria-label="Mật khẩu mới" onClick={(event) => event.stopPropagation()}>
            <span className="sv-modal-eyebrow">ADMIN / TÀI KHOẢN</span>
            <h2>Đã đặt lại mật khẩu</h2>
            <p className="sv-modal-sub">
              Mật khẩu mới của <strong>{resetResult.email}</strong> (chỉ hiển thị lần này):
            </p>
            <div className="sv-reset-password-box">
              <code>{resetResult.password}</code>
              <button type="button" onClick={copyResetPassword}>{copied ? "Đã sao chép" : "Sao chép"}</button>
            </div>
            <p className="sv-modal-note">Hãy gửi mật khẩu này cho người dùng. Họ nên đổi lại mật khẩu sau khi đăng nhập.</p>
            <div className="sv-admin-form-actions">
              <button type="button" className="sv-modal-submit" onClick={() => setResetResult(null)}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
