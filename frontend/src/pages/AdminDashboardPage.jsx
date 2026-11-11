import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { fetchAdminStats } from "../services/adminService";
import { DOMAINS, SKILLS, formatApiError, formatDate, formatPercent } from "../constants/domains";
import { PageError, PageLoading } from "../components/PageState";
import "./AdminDashboardPage.css";

const METRICS = [
  { key: "users", label: "Tài khoản", icon: "♙", tone: "violet", value: (s) => s.users?.total, sub: (s) => `${s.users?.admins ?? 0} Admin · ${s.users?.regular ?? 0} người học` },
  { key: "vocab", label: "Từ vựng", icon: "Aa", tone: "blue", value: (s) => s.vocabularies?.total, sub: (s) => `Trên ${DOMAINS.length} lĩnh vực học tập` },
  { key: "lessons", label: "Bài học có dữ liệu", icon: "▤", tone: "amber", value: (s) => s.lessons?.total, sub: (s) => `${s.lessons?.metadata ?? 0} bản ghi tiêu đề · ${s.lessons?.with_exercises ?? 0} bài có câu hỏi` },
  { key: "exercises", label: "Câu hỏi", icon: "✎", tone: "green", value: (s) => s.exercises?.total, sub: (s) => `${s.exercises?.active ?? 0} đang hoạt động trên 3 kỹ năng` },
];

const MODULES = [
  { to: "/admin/users", icon: "♙", tone: "blue", title: "Quản lý người dùng", text: "Tìm kiếm tài khoản, xem vai trò và cấp/thu quyền Admin an toàn." },
  { to: "/admin/vocabulary", icon: "Aa", tone: "violet", title: "Quản lý từ vựng", text: "Thêm, sửa, xoá từ vựng dùng chung theo lĩnh vực và cấp độ." },
  { to: "/admin/domains", icon: "◈", tone: "amber", title: "Quản lý lĩnh vực", text: "Cập nhật tên, mô tả, thứ tự và trạng thái của 3 lĩnh vực MVP." },
  { to: "/admin/lessons", icon: "▤", tone: "green", title: "Quản lý bài học", text: "Xem bài học theo lĩnh vực/cấp độ, từ vựng và ngân hàng câu hỏi." },
  { to: "/admin/exercises", icon: "✎", tone: "blue", title: "Quản lý câu hỏi", text: "Kiểm tra, chỉnh sửa đáp án Meaning, Spelling, Context và tái tạo." },
];

function PanelHead({ kicker, title, icon, tone }) {
  return (
    <header className="sv-admin-panel-head">
      <span className={`sv-admin-panel-chip tone-${tone}`} aria-hidden="true">{icon}</span>
      <div>
        <span>{kicker}</span>
        <h2>{title}</h2>
      </div>
    </header>
  );
}

export default function AdminDashboardPage() {
  const user = useAuth();
  const [version, setVersion] = useState(0);
  const [state, setState] = useState({ loading: true, stats: null, error: "" });

  useEffect(() => {
    let alive = true;
    setState((old) => ({ ...old, loading: true, error: "" }));
    fetchAdminStats()
      .then((stats) => {
        if (alive) setState({ loading: false, stats, error: "" });
      })
      .catch((err) => {
        if (alive) setState({ loading: false, stats: null, error: formatApiError(err, "Không thể tải thống kê quản trị.") });
      });
    return () => { alive = false; };
  }, [version]);

  if (state.loading) return <PageLoading label="Đang tải dữ liệu quản trị..." />;
  if (state.error) return <div className="sv-admin-page"><PageError message={state.error} onRetry={() => setVersion((value) => value + 1)} /></div>;

  const stats = state.stats || {};
  const vocabByDomain = stats.vocabularies?.by_domain || {};
  const exercisesBySkill = stats.exercises?.by_skill || {};
  const vocabTotal = Number(stats.vocabularies?.total) || 0;
  const exerciseTotal = Number(stats.exercises?.total) || 0;
  const domainMax = Math.max(1, ...DOMAINS.map((domain) => Number(vocabByDomain[domain.id]) || 0));
  const skillMax = Math.max(1, ...SKILLS.map((skill) => Number(exercisesBySkill[skill.id]) || 0));

  return (
    <div className="sv-page sv-admin-page sv-admin-home">
      <section className="sv-admin-hero">
        <div>
          <span className="sv-admin-eyebrow">SMARTVOCAB AI / HỆ THỐNG QUẢN TRỊ</span>
          <h1>Xin chào, {user?.username || "Quản trị viên"}.</h1>
          <p>Quản lý nội dung học tập, tài khoản và ngân hàng câu hỏi. Khu vực này tách biệt hoàn toàn với trải nghiệm người học và mọi API đều được backend kiểm tra quyền Admin.</p>
          <div className="sv-admin-top-actions">
            <Link to="/admin/vocabulary" className="sv-admin-hero-button">Quản lý từ vựng <span aria-hidden="true">→</span></Link>
            <Link to="/admin/users" className="sv-btn sv-btn-ghost-light">Quản lý người dùng</Link>
          </div>
        </div>
        <div className="sv-admin-hero-mark" aria-hidden="true"><span>SV</span><small>ADMIN</small></div>
      </section>

      <div className="sv-admin-section-title">
        <div><span>THỐNG KÊ HỆ THỐNG</span><h2>Tổng quan dữ liệu thật</h2></div>
        <button type="button" className="sv-admin-refresh" onClick={() => setVersion((old) => old + 1)}>↻ Làm mới</button>
      </div>

      <div className="sv-admin-metric-grid">
        {METRICS.map((metric) => (
          <article className={`sv-admin-metric tone-${metric.tone}`} key={metric.key}>
            <div className="sv-admin-metric-head">
              <span className="sv-admin-metric-chip" aria-hidden="true">{metric.icon}</span>
              <span>{metric.label}</span>
            </div>
            <strong>{metric.value(stats) ?? "—"}</strong>
            <small>{metric.sub(stats)}</small>
          </article>
        ))}
      </div>

      <div className="sv-admin-breakdown">
        <section className="sv-panel">
          <PanelHead kicker="PHÂN BỔ NỘI DUNG" title="Từ vựng theo lĩnh vực" icon="◈" tone="violet" />
          {DOMAINS.map((domain) => {
            const count = Number(vocabByDomain[domain.id]) || 0;
            const share = vocabTotal ? formatPercent((count / vocabTotal) * 100) : 0;
            return (
              <div className={`sv-admin-bar-row tone-${domain.tone}`} key={domain.id}>
                <span>{domain.label}</span>
                <div className="sv-admin-bar-track"><div style={{ width: `${Math.round((count / domainMax) * 100)}%` }} /></div>
                <b>{count}<em>{share}%</em></b>
              </div>
            );
          })}
        </section>
        <section className="sv-panel">
          <PanelHead kicker="NGÂN HÀNG CÂU HỎI" title="Câu hỏi theo kỹ năng" icon="✎" tone="blue" />
          {SKILLS.map((skill) => {
            const count = Number(exercisesBySkill[skill.id]) || 0;
            const share = exerciseTotal ? formatPercent((count / exerciseTotal) * 100) : 0;
            return (
              <div className={`sv-admin-bar-row tone-${skill.tone}`} key={skill.id}>
                <span>{skill.label}</span>
                <div className="sv-admin-bar-track"><div style={{ width: `${Math.round((count / skillMax) * 100)}%` }} /></div>
                <b>{count}<em>{share}%</em></b>
              </div>
            );
          })}
        </section>
      </div>

      <div className="sv-admin-section-title"><div><span>CHỨC NĂNG QUẢN TRỊ</span><h2>Đi đến khu vực quản lý</h2></div></div>
      <div className="sv-admin-action-grid">
        {MODULES.map((item) => (
          <Link className={`sv-admin-action-card tone-${item.tone}`} to={item.to} key={item.to}>
            <div className="sv-admin-action-top">
              <span className="sv-admin-nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="sv-admin-action-arrow" aria-hidden="true">→</span>
            </div>
            <strong>{item.title}</strong>
            <small>{item.text}</small>
          </Link>
        ))}
      </div>

      <div className="sv-admin-section-title"><div><span>HOẠT ĐỘNG GẦN ĐÂY</span><h2>Tài khoản mới nhất</h2></div><Link className="sv-text-link" to="/admin/users">Xem tất cả →</Link></div>
      <div className="sv-admin-table-wrap sv-admin-recent">
        <table className="sv-admin-table">
          <thead><tr><th>Người dùng</th><th>Vai trò</th><th>Trình độ</th><th>XP</th><th>Ngày tạo</th></tr></thead>
          <tbody>
            {(stats.users?.recent || []).length ? (stats.users?.recent || []).map((item) => (
              <tr key={item.id}>
                <td><div className="sv-admin-cell-main"><span className="sv-admin-avatar-sm">{String(item.username || item.email || "?").charAt(0).toUpperCase()}</span><span><strong>{item.username || "—"}</strong><small>{item.email}</small></span></div></td>
                <td><span className={`sv-admin-badge ${item.role}`}>{item.role === "admin" ? "Admin" : "Người học"}</span></td>
                <td>{item.learning_level || "—"}</td>
                <td>{item.xp ?? 0}</td>
                <td className="sv-admin-muted">{formatDate(item.created_at)}</td>
              </tr>
            )) : <tr><td colSpan={5} className="sv-admin-empty-cell"><strong>Chưa có tài khoản</strong>Dữ liệu sẽ xuất hiện sau khi người dùng đăng ký.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
