import { useCallback, useEffect, useState } from "react";
import { createAdminVocabulary, deleteAdminVocabulary, fetchAdminVocabularies, updateAdminVocabulary } from "../services/adminService";
import { generateWithAI } from "../services/vocabularyService";
import { DOMAINS, formatApiError } from "../constants/domains";
import { PageError, PageLoading } from "../components/PageState";

const PAGE_SIZE = 50;
const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const EMPTY = { word: "", phonetic: "", part_of_speech: "", meaning: "", example: "", synonyms: "", antonyms: "", domain: "general", level: "A1" };

function toList(value) {
  return String(value || "").split(/[,;\n]/).map((item) => item.trim()).filter(Boolean);
}

export default function AdminPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("");
  const [level, setLevel] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminVocabularies({
        page,
        page_size: PAGE_SIZE,
        search: search.trim() || undefined,
        domain: domain || undefined,
        level: level || undefined,
      });
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotal(Number(data.total) || 0);
    } catch (err) {
      setError(formatApiError(err, "Không thể tải danh sách từ vựng."));
    } finally {
      setLoading(false);
    }
  }, [page, search, domain, level]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(() => { setPage(1); }, [search, domain, level]);

  const updateField = (event) => setForm((old) => ({ ...old, [event.target.name]: event.target.value }));

  function startEdit(word) {
    setEditing(word);
    setForm({
      word: word.word || "",
      phonetic: word.phonetic || "",
      part_of_speech: word.part_of_speech || "",
      meaning: word.meaning || "",
      example: word.example || "",
      synonyms: (word.synonyms || []).join(", "),
      antonyms: (word.antonyms || []).join(", "),
      domain: word.domain || word.topic || "general",
      level: word.level || "A1",
    });
    setFormError("");
    document.getElementById("admin-vocab-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function resetForm() {
    setEditing(null);
    setForm(EMPTY);
    setFormError("");
  }

  async function fillWithAI() {
    if (!form.word.trim()) {
      setFormError("Nhập từ tiếng Anh trước khi dùng AI gợi ý.");
      return;
    }
    setAiLoading(true);
    setFormError("");
    try {
      const data = await generateWithAI(form.word.trim());
      const aiDomain = DOMAINS.some((item) => item.id === data.topic) ? data.topic : form.domain;
      setForm((old) => ({
        ...old,
        word: data.word || old.word,
        phonetic: data.phonetic || "",
        part_of_speech: data.part_of_speech || "",
        meaning: data.meaning || "",
        example: data.example || "",
        synonyms: (data.synonyms || []).join(", "),
        antonyms: (data.antonyms || []).join(", "),
        domain: aiDomain,
        level: data.level || old.level,
      }));
    } catch (err) {
      setFormError(formatApiError(err, "AI gợi ý thất bại."));
    } finally {
      setAiLoading(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    if (!form.word.trim() || !form.meaning.trim()) {
      setFormError("Từ tiếng Anh và nghĩa không được để trống.");
      return;
    }
    setSaving(true);
    setFormError("");
    const payload = {
      word: form.word.trim(),
      phonetic: form.phonetic.trim(),
      part_of_speech: form.part_of_speech.trim(),
      meaning: form.meaning.trim(),
      example: form.example.trim(),
      synonyms: toList(form.synonyms),
      antonyms: toList(form.antonyms),
      topic: form.domain,
      domain: form.domain,
      level: form.level,
    };
    try {
      if (editing) {
        await updateAdminVocabulary(editing.id, payload);
        setNotice(`Đã cập nhật từ “${payload.word}”.`);
      } else {
        await createAdminVocabulary(payload);
        setNotice(`Đã thêm từ “${payload.word}”.`);
      }
      resetForm();
      await load();
    } catch (err) {
      setFormError(formatApiError(err, "Không thể lưu từ vựng."));
    } finally {
      setSaving(false);
    }
  }

  async function remove(word) {
    if (!window.confirm(`Xóa từ “${word.word}”? Thao tác này thay đổi dữ liệu dùng chung.`)) return;
    setBusyId(word.id);
    setError("");
    setNotice("");
    try {
      await deleteAdminVocabulary(word.id);
      setNotice(`Đã xóa từ “${word.word}”.`);
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể xóa từ vựng."));
    } finally {
      setBusyId(null);
    }
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="sv-page sv-admin-page">
      <div className="sv-page-heading">
        <div>
          <span className="sv-eyebrow">ADMIN / NỘI DUNG</span>
          <h1>Quản lý từ vựng</h1>
          <p>Thêm, sửa, xóa từ vựng dùng chung theo lĩnh vực và cấp độ. Bài học được nhóm tự động từ dữ liệu này.</p>
        </div>
        <span className="sv-catalog-count">{total} từ vựng</span>
      </div>

      {notice && <div className="sv-admin-success" role="status">{notice}</div>}

      <section className="sv-admin-form" id="admin-vocab-form">
        <h2>{editing ? `Sửa từ: ${editing.word}` : "Thêm từ vựng mới"}</h2>
        <p>{editing ? "Cập nhật nội dung hiển thị cho người học." : "Từ mới sẽ xuất hiện trong bài học tương ứng với lĩnh vực và cấp độ."}</p>
        <form onSubmit={submit}>
          <div className="sv-admin-form-grid three">
            <div>
              <label className="sv-form-label" htmlFor="admin-word">Từ tiếng Anh</label>
              <input className="sv-answer-field" id="admin-word" name="word" value={form.word} onChange={updateField} required />
            </div>
            <div>
              <label className="sv-form-label" htmlFor="admin-meaning">Nghĩa tiếng Việt</label>
              <input className="sv-answer-field" id="admin-meaning" name="meaning" value={form.meaning} onChange={updateField} required />
            </div>
            <div>
              <label className="sv-form-label" htmlFor="admin-phonetic">Phiên âm</label>
              <input className="sv-answer-field" id="admin-phonetic" name="phonetic" value={form.phonetic} onChange={updateField} placeholder="/ˈæp.əl/" />
            </div>
          </div>
          <div className="sv-admin-form-grid three">
            <div>
              <label className="sv-form-label" htmlFor="admin-pos">Loại từ</label>
              <input className="sv-answer-field" id="admin-pos" name="part_of_speech" value={form.part_of_speech} onChange={updateField} placeholder="noun, verb..." />
            </div>
            <div>
              <label className="sv-form-label" htmlFor="admin-domain">Lĩnh vực</label>
              <select className="sv-answer-field" id="admin-domain" name="domain" value={form.domain} onChange={updateField}>
                {DOMAINS.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
              </select>
            </div>
            <div>
              <label className="sv-form-label" htmlFor="admin-level">Trình độ</label>
              <select className="sv-answer-field" id="admin-level" name="level" value={form.level} onChange={updateField}>
                {LEVELS.map((item) => <option value={item} key={item}>{item}</option>)}
              </select>
            </div>
          </div>
          <label className="sv-form-label" htmlFor="admin-example">Câu ví dụ</label>
          <textarea className="sv-answer-field" id="admin-example" name="example" value={form.example} onChange={updateField} rows={2} />
          <div className="sv-admin-form-grid">
            <div>
              <label className="sv-form-label" htmlFor="admin-synonyms">Từ đồng nghĩa (cách nhau bằng dấu phẩy)</label>
              <input className="sv-answer-field" id="admin-synonyms" name="synonyms" value={form.synonyms} onChange={updateField} />
            </div>
            <div>
              <label className="sv-form-label" htmlFor="admin-antonyms">Từ trái nghĩa (cách nhau bằng dấu phẩy)</label>
              <input className="sv-answer-field" id="admin-antonyms" name="antonyms" value={form.antonyms} onChange={updateField} />
            </div>
          </div>
          {formError && <div className="sv-admin-error" role="alert">{formError}</div>}
          <div className="sv-admin-form-actions">
            {!editing && <button type="button" className="sv-btn sv-btn-outline" onClick={fillWithAI} disabled={aiLoading || saving}>{aiLoading ? "AI đang gợi ý..." : "✨ AI gợi ý"}</button>}
            {editing && <button type="button" className="sv-btn sv-btn-outline" onClick={resetForm} disabled={saving}>Hủy sửa</button>}
            <button type="submit" className="sv-btn sv-btn-primary" disabled={saving}>{saving ? "Đang lưu..." : editing ? "Lưu thay đổi" : "Thêm từ vựng"}</button>
          </div>
        </form>
      </section>

      <div className="sv-admin-section-title" style={{ marginTop: 24 }}><div><span>KHO TỪ DÙNG CHUNG</span><h2>Danh sách từ vựng</h2></div></div>

      <div className="sv-admin-toolbar">
        <input className="sv-answer-field sv-admin-grow" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo từ hoặc nghĩa..." aria-label="Tìm từ vựng" />
        <select className="sv-answer-field" value={domain} onChange={(event) => setDomain(event.target.value)} aria-label="Lọc lĩnh vực">
          <option value="">Tất cả lĩnh vực</option>
          {DOMAINS.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
        </select>
        <select className="sv-answer-field" value={level} onChange={(event) => setLevel(event.target.value)} aria-label="Lọc trình độ">
          <option value="">Tất cả trình độ</option>
          {LEVELS.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
        <button type="button" className="sv-admin-refresh" onClick={load} disabled={loading}>{loading ? "Đang tải..." : "↻ Làm mới"}</button>
        <span className="sv-admin-count">Trang {page}/{pages}</span>
      </div>

      {error && <div className="sv-admin-error" role="alert">{error}</div>}
      {loading && !items.length ? <PageLoading label="Đang tải từ vựng..." /> : error && !items.length ? <PageError message={error} onRetry={load} /> : (
        <>
          <div className="sv-admin-table-wrap">
            <table className="sv-admin-table">
              <thead><tr><th>Từ</th><th>Nghĩa</th><th>Lĩnh vực</th><th>Cấp độ</th><th>Ví dụ</th><th>Thao tác</th></tr></thead>
              <tbody>
                {items.length ? items.map((word) => (
                  <tr key={word.id}>
                    <td><div className="sv-admin-cell-main"><span><strong>{word.word}</strong><small>{word.phonetic || "Chưa có phiên âm"}</small></span></div></td>
                    <td>{word.meaning}</td>
                    <td><span className="sv-admin-badge">{DOMAINS.find((item) => item.id === (word.domain || word.topic))?.label || word.domain || word.topic}</span></td>
                    <td><span className="sv-admin-badge">{word.level}</span></td>
                    <td className="sv-admin-muted">{word.example || "—"}</td>
                    <td><div className="sv-admin-actions"><button type="button" className="sv-edit-link" onClick={() => startEdit(word)}>Sửa</button><button type="button" className="sv-danger-link" disabled={busyId === word.id} onClick={() => remove(word)}>{busyId === word.id ? "Đang xóa..." : "Xóa"}</button></div></td>
                  </tr>
                )) : <tr><td colSpan={6} className="sv-admin-empty-cell"><strong>Không tìm thấy từ vựng</strong>Thử đổi bộ lọc hoặc thêm từ mới ở biểu mẫu phía trên.</td></tr>}
              </tbody>
            </table>
          </div>
          {pages > 1 && <div className="sv-admin-pagination"><button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>← Trước</button><span>Trang {page} / {pages}</span><button type="button" onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages}>Sau →</button></div>}
        </>
      )}
    </div>
  );
}
