import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createAdminLesson,
  deleteAdminLesson,
  fetchAdminLessonWords,
  fetchAdminLessons,
  updateAdminLesson,
} from "../services/adminService";
import { DOMAINS, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading } from "../components/PageState";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const EMPTY_FORM = { domain: "general", level: "A1", title: "", description: "", order: 0 };

export default function AdminLessonsPage() {
  const [lessons, setLessons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [domain, setDomain] = useState("");
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [wordLesson, setWordLesson] = useState(null);
  const [words, setWords] = useState([]);
  const [wordsLoading, setWordsLoading] = useState(false);
  const [wordsError, setWordsError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminLessons();
      setLessons(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(formatApiError(err, "Không thể tải danh sách bài học."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const shown = useMemo(() => lessons.filter((lesson) => {
    if (domain && lesson.domain !== domain) return false;
    if (level && lesson.level !== level) return false;
    if (search.trim()) {
      const needle = search.trim().toLowerCase();
      const haystack = `${lesson.title} ${lesson.slug} ${lesson.description}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  }), [lessons, domain, level, search]);

  const updateField = (event) => setForm((old) => ({ ...old, [event.target.name]: event.target.value }));

  function startCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError("");
    document.getElementById("admin-lesson-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function startEdit(lesson) {
    setEditing(lesson);
    setForm({
      domain: lesson.domain,
      level: lesson.level,
      title: lesson.title || "",
      description: lesson.description || "",
      order: lesson.order ?? 0,
    });
    setFormError("");
    document.getElementById("admin-lesson-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setFormError("");
    try {
      if (editing) {
        await updateAdminLesson(editing.id, {
          title: form.title.trim(),
          description: form.description.trim(),
          order: Number(form.order) || 0,
        });
        setNotice(`Đã cập nhật bài học ${editing.id}.`);
      } else {
        await createAdminLesson({
          domain: form.domain,
          level: form.level,
          title: form.title.trim() || undefined,
          description: form.description.trim() || undefined,
          order: Number(form.order) || 0,
        });
        setNotice(`Đã tạo bài học ${form.domain}-${form.level.toLowerCase()}.`);
      }
      setEditing(null);
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setFormError(formatApiError(err, "Không thể lưu bài học."));
    } finally {
      setSaving(false);
    }
  }

  async function remove(lesson) {
    if (!window.confirm(`Xóa bài học ${lesson.id}? Chỉ xóa được khi bài học không còn từ vựng.`)) return;
    setBusyId(lesson.id);
    setError("");
    setNotice("");
    try {
      await deleteAdminLesson(lesson.id);
      setNotice(`Đã xóa bài học ${lesson.id}.`);
      if (wordLesson?.id === lesson.id) {
        setWordLesson(null);
        setWords([]);
      }
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể xóa bài học."));
    } finally {
      setBusyId(null);
    }
  }

  async function showWords(lesson) {
    setWordLesson(lesson);
    setWords([]);
    setWordsError("");
    setWordsLoading(true);
    try {
      const data = await fetchAdminLessonWords(lesson.id, { page: 1, page_size: 200 });
      setWords(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      setWordsError(formatApiError(err, "Không thể tải từ vựng của bài học."));
    } finally {
      setWordsLoading(false);
    }
  }

  return (
    <div className="sv-page sv-admin-page">
      <div className="sv-page-heading">
        <div>
          <span className="sv-eyebrow">ADMIN / BÀI HỌC</span>
          <h1>Quản lý bài học</h1>
          <p>Bài học được nhóm tự động theo lĩnh vực + cấp độ từ kho từ vựng. Tại đây bạn có thể đặt tiêu đề/mô tả và kiểm tra từ vựng.</p>
        </div>
        <span className="sv-catalog-count">{shown.length}/{lessons.length} bài học</span>
      </div>

      {notice && <div className="sv-admin-success" role="status">{notice}</div>}
      {error && <div className="sv-admin-error" role="alert">{error}</div>}

      <section className="sv-admin-form" id="admin-lesson-form">
        <h2>{editing ? `Sửa bài học ${editing.id}` : "Tạo / cập nhật bài học"}</h2>
        <p>{editing ? "Chỉ tiêu đề, mô tả và thứ tự có thể sửa; lĩnh vực/cấp độ lấy từ từ vựng." : "Tạo bản ghi tiêu đề cho một cặp lĩnh vực + cấp độ. Bài học chỉ có từ vựng khi kho từ có dữ liệu tương ứng."}</p>
        <form onSubmit={submit}>
          <div className="sv-admin-form-grid three">
            <div>
              <label className="sv-form-label" htmlFor="lesson-domain">Lĩnh vực</label>
              <select className="sv-answer-field" id="lesson-domain" name="domain" value={form.domain} onChange={updateField} disabled={Boolean(editing)}>
                {DOMAINS.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
              </select>
            </div>
            <div>
              <label className="sv-form-label" htmlFor="lesson-level">Cấp độ</label>
              <select className="sv-answer-field" id="lesson-level" name="level" value={form.level} onChange={updateField} disabled={Boolean(editing)}>
                {LEVELS.map((item) => <option value={item} key={item}>{item}</option>)}
              </select>
            </div>
            <div>
              <label className="sv-form-label" htmlFor="lesson-order">Thứ tự</label>
              <input className="sv-answer-field" id="lesson-order" name="order" type="number" min="0" value={form.order} onChange={updateField} />
            </div>
          </div>
          <label className="sv-form-label" htmlFor="lesson-title">Tiêu đề hiển thị</label>
          <input className="sv-answer-field" id="lesson-title" name="title" value={form.title} onChange={updateField} placeholder="Để trống để dùng tiêu đề mặc định" />
          <label className="sv-form-label" htmlFor="lesson-description">Mô tả</label>
          <textarea className="sv-answer-field" id="lesson-description" name="description" value={form.description} onChange={updateField} rows={2} placeholder="Để trống để dùng mô tả tự động theo số từ vựng" />
          {formError && <div className="sv-admin-error" role="alert">{formError}</div>}
          <div className="sv-admin-form-actions">
            {editing && <button type="button" className="sv-btn sv-btn-outline" onClick={startCreate} disabled={saving}>Hủy sửa</button>}
            <button type="submit" className="sv-btn sv-btn-primary" disabled={saving}>{saving ? "Đang lưu..." : editing ? "Lưu thay đổi" : "Tạo bài học"}</button>
          </div>
        </form>
      </section>

      <div className="sv-admin-section-title" style={{ marginTop: 24 }}><div><span>DANH SÁCH BÀI HỌC</span><h2>Theo lĩnh vực và cấp độ</h2></div></div>
      <div className="sv-admin-toolbar">
        <input className="sv-answer-field sv-admin-grow" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo tiêu đề hoặc mã bài..." aria-label="Tìm bài học" />
        <select className="sv-answer-field" value={domain} onChange={(event) => setDomain(event.target.value)} aria-label="Lọc lĩnh vực">
          <option value="">Tất cả lĩnh vực</option>
          {DOMAINS.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
        </select>
        <select className="sv-answer-field" value={level} onChange={(event) => setLevel(event.target.value)} aria-label="Lọc cấp độ">
          <option value="">Tất cả cấp độ</option>
          {LEVELS.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
        <button type="button" className="sv-admin-refresh" onClick={load} disabled={loading}>{loading ? "Đang tải..." : "↻ Làm mới"}</button>
      </div>

      {loading && !lessons.length ? <PageLoading label="Đang tải bài học..." /> : error && !lessons.length ? <PageError message={error} onRetry={load} /> : shown.length ? (
        <div className="sv-admin-table-wrap">
          <table className="sv-admin-table">
            <thead><tr><th>Bài học</th><th>Lĩnh vực</th><th>Cấp độ</th><th>Từ vựng</th><th>Câu hỏi</th><th>Thao tác</th></tr></thead>
            <tbody>
              {shown.map((lesson) => (
                <tr key={lesson.id}>
                  <td><div className="sv-admin-cell-main"><span><strong>{lesson.title}</strong><small>{lesson.id} {lesson.metadata_exists ? "· đã đặt tiêu đề" : ""}</small></span></div></td>
                  <td>{DOMAINS.find((item) => item.id === lesson.domain)?.label || lesson.domain}</td>
                  <td><span className="sv-admin-badge">{lesson.level}</span></td>
                  <td><span className="sv-admin-strong">{lesson.word_count}</span> <small className="sv-admin-muted">từ</small></td>
                  <td><span className="sv-admin-strong">{lesson.exercise_count}</span> <small className="sv-admin-muted">câu</small></td>
                  <td><div className="sv-admin-actions"><button type="button" className="sv-edit-link" onClick={() => showWords(lesson)}>Từ vựng</button><button type="button" className="sv-edit-link" onClick={() => startEdit(lesson)}>Sửa</button><button type="button" className="sv-danger-link" onClick={() => remove(lesson)} disabled={busyId === lesson.id}>{busyId === lesson.id ? "Đang xóa..." : "Xóa"}</button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title="Không có bài học phù hợp" description="Thử đổi bộ lọc hoặc thêm từ vựng cho lĩnh vực/cấp độ mới." />}

      {wordLesson && (
        <section className="sv-admin-form" style={{ marginTop: 18 }}>
          <div className="sv-admin-inline" style={{ justifyContent: "space-between" }}>
            <div><h2>Từ vựng của {wordLesson.title}</h2><p>{wordLesson.id} · {wordLesson.word_count} từ</p></div>
            <button type="button" className="sv-admin-refresh" onClick={() => { setWordLesson(null); setWords([]); }}>Đóng</button>
          </div>
          {wordsError && <div className="sv-admin-error" role="alert">{wordsError}</div>}
          {wordsLoading ? <PageLoading label="Đang tải từ vựng..." /> : words.length ? (
            <div className="sv-admin-words-list" style={{ maxHeight: 420 }}>
              {words.map((word) => <div className="sv-admin-word-row" key={word.id}><span><strong>{word.word}</strong> <small>{word.phonetic || ""}</small></span><span>{word.meaning} <small>· {word.domain} · {word.level}</small></span></div>)}
            </div>
          ) : <div className="sv-admin-empty-cell"><strong>Bài học chưa có từ vựng</strong>Thêm từ vựng cùng lĩnh vực và cấp độ trong mục Quản lý từ vựng.</div>}
        </section>
      )}
      <p className="sv-admin-footnote">Lưu ý: xóa bài học chỉ xóa tiêu đề/mô tả. Muốn xóa một bài có từ vựng, hãy chuyển hoặc xóa từ vựng trước để tránh mất dữ liệu học tập.</p>
    </div>
  );
}
