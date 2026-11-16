import { useCallback, useEffect, useState } from "react";
import { ensureAdminDomains, fetchAdminDomains, updateAdminDomain } from "../services/adminService";
import { formatApiError } from "../constants/domains";
import { PageError, PageLoading } from "../components/PageState";

function DomainCard({ domain, onSaved }) {
  const [form, setForm] = useState({
    name: domain.name || "",
    name_vi: domain.name_vi || "",
    description: domain.description || "",
    order: domain.order ?? 0,
    active: domain.active !== false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setForm({
      name: domain.name || "",
      name_vi: domain.name_vi || "",
      description: domain.description || "",
      order: domain.order ?? 0,
      active: domain.active !== false,
    });
  }, [domain]);

  const update = (event) => {
    const { name, value, type, checked } = event.target;
    setForm((old) => ({ ...old, [name]: type === "checkbox" ? checked : value }));
  };

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const updated = await updateAdminDomain(domain.slug, {
        name: form.name.trim(),
        name_vi: form.name_vi.trim(),
        description: form.description.trim(),
        order: Number(form.order) || 0,
        active: form.active,
      });
      onSaved(updated);
    } catch (err) {
      setError(formatApiError(err, "Không thể cập nhật lĩnh vực."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="sv-admin-domain-card">
      <header>
        <div><h2>{domain.name}</h2><small>{domain.slug} · {domain.lesson_count} bài học</small></div>
        <span className={`sv-admin-badge ${form.active ? "admin" : "off"}`}>{form.active ? "Hoạt động" : "Tạm ẩn"}</span>
      </header>
      <div className="sv-admin-domain-stats">
        <span><b>{domain.vocabulary_count ?? 0}</b>từ vựng</span>
        <span><b>{domain.lesson_count ?? 0}</b>cấp độ có dữ liệu</span>
        <span><b>{domain.lessons?.length ?? 0}</b>bài học</span>
      </div>
      <form onSubmit={submit}>
        <label className="sv-form-label" htmlFor={`domain-name-${domain.slug}`}>Tên tiếng Anh</label>
        <input className="sv-answer-field" id={`domain-name-${domain.slug}`} name="name" value={form.name} onChange={update} required />
        <label className="sv-form-label" htmlFor={`domain-name-vi-${domain.slug}`}>Tên tiếng Việt</label>
        <input className="sv-answer-field" id={`domain-name-vi-${domain.slug}`} name="name_vi" value={form.name_vi} onChange={update} required />
        <label className="sv-form-label" htmlFor={`domain-description-${domain.slug}`}>Mô tả</label>
        <textarea className="sv-answer-field" id={`domain-description-${domain.slug}`} name="description" value={form.description} onChange={update} rows={2} />
        <div className="sv-admin-form-grid">
          <div>
            <label className="sv-form-label" htmlFor={`domain-order-${domain.slug}`}>Thứ tự</label>
            <input className="sv-answer-field" id={`domain-order-${domain.slug}`} name="order" type="number" min="0" max="999" value={form.order} onChange={update} />
          </div>
          <div>
            <label className="sv-form-label" htmlFor={`domain-active-${domain.slug}`}>Trạng thái</label>
            <label className="sv-admin-check" htmlFor={`domain-active-${domain.slug}`}><input id={`domain-active-${domain.slug}`} name="active" type="checkbox" checked={form.active} onChange={update} /> Hiển thị cho người học</label>
          </div>
        </div>
        {error && <div className="sv-admin-error" role="alert">{error}</div>}
        <div className="sv-admin-form-actions"><button type="submit" className="sv-btn sv-btn-primary" disabled={saving}>{saving ? "Đang lưu..." : "Lưu lĩnh vực"}</button></div>
      </form>
    </article>
  );
}

export default function AdminDomainsPage() {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ensuring, setEnsuring] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminDomains();
      setDomains(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(formatApiError(err, "Không thể tải danh sách lĩnh vực."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function saved(updated) {
    setDomains((old) => old.map((item) => (item.slug === updated.slug ? updated : item)));
    setNotice(`Đã lưu lĩnh vực ${updated.name}.`);
  }

  async function ensure() {
    setEnsuring(true);
    setError("");
    setNotice("");
    try {
      await ensureAdminDomains();
      setNotice("Đã khôi phục các lĩnh vực mặc định bị thiếu (không ghi đè tuỳ chỉnh).");
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể khởi tạo lĩnh vực."));
    } finally {
      setEnsuring(false);
    }
  }

  return (
    <div className="sv-page sv-admin-page">
      <div className="sv-page-heading">
        <div>
          <span className="sv-eyebrow">ADMIN / LĨNH VỰC</span>
          <h1>Quản lý lĩnh vực</h1>
          <p>Ba lĩnh vực MVP dùng để nhóm từ vựng và bài học. Thay đổi tên/mô tả được giữ nguyên khi khởi động lại backend.</p>
        </div>
        <div className="sv-admin-top-actions">
          <button type="button" className="sv-admin-refresh" onClick={ensure} disabled={ensuring || loading}>{ensuring ? "Đang khởi tạo..." : "Khôi phục mặc định"}</button>
          <button type="button" className="sv-admin-refresh" onClick={load} disabled={loading}>{loading ? "Đang tải..." : "↻ Làm mới"}</button>
        </div>
      </div>

      {notice && <div className="sv-admin-success" role="status">{notice}</div>}
      {error && <div className="sv-admin-error" role="alert">{error}</div>}

      {loading && !domains.length ? <PageLoading label="Đang tải lĩnh vực..." /> : error && !domains.length ? <PageError message={error} onRetry={load} /> : (
        <div className="sv-admin-cards">
          {domains.map((domain) => <DomainCard key={domain.slug} domain={domain} onSaved={saved} />)}
        </div>
      )}
    </div>
  );
}
