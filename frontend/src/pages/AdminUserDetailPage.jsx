import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchAdminUser, setAdminUserStatus } from "../services/adminService";
import { DOMAINS, formatApiError, formatDate, formatPercent } from "../constants/domains";
import ConfirmDialog from "../components/ConfirmDialog";
import { PageError, PageLoading } from "../components/PageState";

const SKILL_LABELS = {
  meaning: "Meaning — Nhận biết nghĩa",
  spelling: "Spelling — Viết chính tả",
  context: "Context — Dùng trong câu",
};

const DOMAIN_LABELS = Object.fromEntries(DOMAINS.map((domain) => [domain.id, domain.label]));

function domainLabel(domain) {
  return DOMAIN_LABELS[domain] || domain;
}

const RATING_LABELS = {
  1: "Quên",
  2: "Khó",
  3: "Nhớ",
  4: "Dễ",
};

export default function AdminUserDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmLock, setConfirmLock] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await fetchAdminUser(id);
      setData(result);
    } catch (err) {
      setError(formatApiError(err, "Không thể tải thông tin người dùng."));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleLock() {
    const user = data?.user;
    if (!user) return;
    const next = user.is_active === false;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await setAdminUserStatus(user.id, next);
      setNotice(next ? `Đã mở khóa tài khoản ${user.email}.` : `Đã khóa tài khoản ${user.email}.`);
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể cập nhật trạng thái tài khoản."));
    } finally {
      setBusy(false);
      setConfirmLock(false);
    }
  }

  if (loading && !data) return <PageLoading label="Đang tải tiến độ học..." />;
  if (error && !data) return <PageError message={error} onRetry={load} />;
  if (!data) return null;

  const { user, summary, mastery, history, fsrs } = data;
  const locked = user.is_active === false;
  const totalAnswers = (summary?.correct_answers || 0) + (summary?.wrong_answers || 0);
  const maxLessonWords = Math.max(1, ...(mastery?.lessons || []).map((lesson) => lesson.words || 0));

  const stats = [
    { label: "Tổng XP", value: `${user.xp ?? 0}`, sub: `Cấp ${summary?.level ?? 1}` },
    { label: "Chuỗi ngày", value: `${user.streak ?? 0}`, sub: "ngày liên tiếp" },
    { label: "Từ đã học", value: `${summary?.words_learned ?? 0}`, sub: `trên ${fsrs?.total_words ?? 0} thẻ` },
    { label: "Từ đã thuộc", value: `${summary?.words_mastered ?? 0}`, sub: `3 kỹ năng ≥ ${mastery?.threshold ?? 80}` },
    { label: "Bài hoàn thành", value: `${summary?.lessons_completed ?? 0}`, sub: "bài học" },
    { label: "Độ chính xác", value: `${formatPercent(summary?.accuracy)}%`, sub: `${totalAnswers} câu trả lời` },
  ];

  return (
    <div className="sv-page sv-admin-page">
      <Link className="sv-text-link sv-detail-back" to="/admin/users">← Quản lý người dùng</Link>

      <div className="sv-detail-hero">
        <div className="sv-detail-hero-main">
          <span className="sv-admin-avatar-lg">{String(user.username || user.email || "?").charAt(0).toUpperCase()}</span>
          <div>
            <span className="sv-eyebrow">ADMIN / CHI TIẾT NGƯỜI DÙNG</span>
            <h1>{user.username || "—"}</h1>
            <p>{user.email}</p>
            <div className="sv-detail-badges">
              <span className={`sv-admin-badge ${user.role}`}>{user.role === "admin" ? "Admin" : "Người học"}</span>
              <span className={`sv-admin-badge ${locked ? "locked" : "ok"}`}>{locked ? "Đã khóa" : "Hoạt động"}</span>
              {user.learning_level && <span className="sv-admin-badge off">Trình độ {user.learning_level}</span>}
              <span className="sv-admin-badge off">Mục tiêu {user.daily_goal} từ/ngày</span>
            </div>
          </div>
        </div>
        <div className="sv-detail-hero-side">
          <div className="sv-detail-meta">
            <span>Ngày tạo</span><b>{formatDate(user.created_at)}</b>
            <span>Học gần nhất</span><b>{formatDate(summary?.last_study_date)}</b>
            <span>Lĩnh vực quan tâm</span>
            <b className="sv-detail-interests">
              {(user.interests || []).length
                ? user.interests.map((interest) => (
                  <span key={interest} className="sv-detail-chip">{domainLabel(interest)}</span>
                ))
                : "—"}
            </b>
          </div>
          <button type="button" className={locked ? "sv-edit-link" : "sv-danger-link"} onClick={() => setConfirmLock(true)} disabled={busy}>
            {busy ? "Đang xử lý..." : locked ? "Mở khóa tài khoản" : "Khóa tài khoản"}
          </button>
        </div>
      </div>

      {notice && <div className="sv-admin-success" role="status">{notice}</div>}
      {error && <div className="sv-admin-error" role="alert">{error}</div>}

      <div className="sv-detail-stats">
        {stats.map((stat) => (
          <div key={stat.label} className="sv-detail-stat">
            <span>{stat.label}</span>
            <b>{stat.value}</b>
            <small>{stat.sub}</small>
          </div>
        ))}
      </div>

      <div className="sv-admin-split sv-detail-split">
        <div className="sv-admin-stack">
          <section className="sv-panel">
            <div className="sv-admin-section-title"><div><span>TIẾN ĐỘ</span><h2>Theo lĩnh vực</h2></div></div>
            <p className="sv-detail-hint">Số từ đã bắt đầu học / tổng số từ của từng lĩnh vực (chỉ những từ người này đã có trong kho của mình).</p>
            {(summary?.domains || []).map((domain) => (
              <div key={domain.domain} className="sv-admin-bar-row">
                <span>{domainLabel(domain.domain)}</span>
                <div className="sv-admin-bar-track">
                  <div style={{ width: `${domain.total ? formatPercent((domain.started / domain.total) * 100) : 0}%` }} />
                </div>
                <b>{domain.started}/{domain.total}</b>
              </div>
            ))}
            {(summary?.domains || []).every((domain) => !domain.total) && (
              <p className="sv-detail-hint">Người dùng này chưa bắt đầu học từ nào.</p>
            )}
          </section>

          <section className="sv-panel">
            <div className="sv-admin-section-title"><div><span>TIẾN ĐỘ</span><h2>Theo bài học</h2></div></div>
            <div className="sv-admin-table-wrap">
              <table className="sv-admin-table sv-detail-lessons">
                <thead>
                  <tr><th>Bài học</th><th>Lĩnh vực</th><th>Cấp độ</th><th>Từ</th><th>Đã thuộc</th><th>Tiến độ</th></tr>
                </thead>
                <tbody>
                  {(mastery?.lessons || []).length ? mastery.lessons.map((lesson) => (
                    <tr key={lesson.lesson_id}>
                      <td className="sv-admin-strong">{lesson.lesson_id}</td>
                      <td>{domainLabel(lesson.domain)}</td>
                      <td>{lesson.level}</td>
                      <td>{lesson.words}</td>
                      <td>{lesson.mastered}</td>
                      <td>
                        <div className="sv-admin-bar-track">
                          <div style={{ width: `${formatPercent((lesson.mastered / maxLessonWords) * 100)}%` }} />
                        </div>
                      </td>
                    </tr>
                  )) : <tr><td colSpan={6} className="sv-admin-empty-cell"><strong>Chưa có dữ liệu</strong>Người dùng chưa học bài nào.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="sv-admin-stack">
          <section className="sv-panel">
            <div className="sv-admin-section-title"><div><span>KỸ NĂNG</span><h2>Mức thành thạo</h2></div></div>
            <p className="sv-detail-hint">Điểm trung bình mỗi kỹ năng trên toàn bộ từ (ngưỡng thuộc {mastery?.threshold ?? 80}).</p>
            {Object.entries(mastery?.skills || {}).map(([skill, info]) => (
              <div key={skill} className="sv-detail-skill">
                <div className="sv-detail-skill-head">
                  <span>{SKILL_LABELS[skill] || skill}</span>
                  <b>{info.started}/{info.mastered} thuộc</b>
                </div>
                <div className="sv-admin-bar-track">
                  <div style={{ width: `${formatPercent(info.average)}%` }} />
                </div>
              </div>
            ))}
          </section>

          <section className="sv-panel">
            <div className="sv-admin-section-title"><div><span>ÔN TẬP</span><h2>Thẻ ghi nhớ (FSRS)</h2></div></div>
            <div className="sv-detail-fsrs">
              <div><span>Tổng thẻ</span><b>{fsrs?.total_words ?? 0}</b></div>
              <div><span>Đang học</span><b>{fsrs?.learning ?? 0}</b></div>
              <div><span>Đã thuộc</span><b>{fsrs?.mastered ?? 0}</b></div>
              <div><span>Đến hạn ôn</span><b>{fsrs?.due_today ?? 0}</b></div>
            </div>
          </section>
        </div>
      </div>

      <section className="sv-panel sv-detail-recent">
        <div className="sv-admin-section-title"><div><span>HOẠT ĐỘNG</span><h2>Hoạt động gần đây</h2></div></div>
        <div className="sv-admin-table-wrap">
          <table className="sv-admin-table sv-detail-activity">
            <thead>
              <tr><th>Thời gian</th><th>Loại</th><th>Từ</th><th>Chi tiết</th><th>Kết quả</th></tr>
            </thead>
            <tbody>
              {(history?.items || []).length ? history.items.map((item, index) => (
                <tr key={`${item.id}-${index}`}>
                  <td className="sv-admin-muted">{formatDate(item.answered_at || item.reviewed_at)}</td>
                  <td>{item.type === "review" ? "Ôn thẻ" : "Luyện tập"}</td>
                  <td className="sv-admin-strong">{item.word || "—"}</td>
                  <td className="sv-admin-muted">
                    {item.type === "review"
                      ? `Đánh giá: ${RATING_LABELS[item.rating] || item.rating || "—"}`
                      : `Kỹ năng: ${item.skill || "—"}`}
                  </td>
                  <td>
                    {item.type === "review"
                      ? <span className="sv-admin-badge off">Ghi nhận</span>
                      : item.is_correct
                        ? <span className="sv-admin-badge ok">Đúng</span>
                        : <span className="sv-admin-badge locked">Sai</span>}
                  </td>
                </tr>
              )) : <tr><td colSpan={5} className="sv-admin-empty-cell"><strong>Chưa có hoạt động</strong>Người dùng chưa trả lời hay ôn thẻ nào.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <ConfirmDialog
        open={confirmLock}
        title={locked ? "Mở khóa tài khoản?" : "Khóa tài khoản?"}
        message={locked
          ? `${user.email} có thể đăng nhập lại bình thường.`
          : `${user.email} sẽ không thể đăng nhập cho tới khi được mở khóa.`}
        confirmText={locked ? "Mở khóa" : "Khóa tài khoản"}
        danger={!locked}
        busy={busy}
        onConfirm={toggleLock}
        onCancel={() => setConfirmLock(false)}
      />
    </div>
  );
}
