import { useCallback, useEffect, useState } from "react";
import {
  deleteAdminExercise,
  fetchAdminExercises,
  fetchAdminLessons,
  regenerateAdminExercises,
  updateAdminExercise,
} from "../services/adminService";
import { DOMAINS, SKILLS, formatApiError } from "../constants/domains";
import { PageError, PageLoading } from "../components/PageState";

const PAGE_SIZE = 50;
const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const EMPTY_FORM = { prompt: "", options: "", correct_answer: "", accepted_answers: "", cloze: "", hint: "", active: true };

function splitLines(value) {
  return String(value || "").split(/\n/).map((item) => item.trim()).filter(Boolean);
}

export default function AdminExercisesPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [domain, setDomain] = useState("");
  const [level, setLevel] = useState("");
  const [skill, setSkill] = useState("");
  const [active, setActive] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [lessonOptions, setLessonOptions] = useState([]);
  const [regenLesson, setRegenLesson] = useState("");
  const [regenerating, setRegenerating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminExercises({
        page,
        page_size: PAGE_SIZE,
        domain: domain || undefined,
        level: level || undefined,
        skill: skill || undefined,
        active: active === "" ? undefined : active === "true",
        search: search.trim() || undefined,
      });
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotal(Number(data.total) || 0);
    } catch (err) {
      setError(formatApiError(err, "Không thể tải ngân hàng câu hỏi."));
    } finally {
      setLoading(false);
    }
  }, [page, domain, level, skill, active, search]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(() => { setPage(1); }, [domain, level, skill, active, search]);

  useEffect(() => {
    let alive = true;
    fetchAdminLessons()
      .then((data) => {
        if (!alive) return;
        const options = (Array.isArray(data) ? data : []).filter((lesson) => lesson.word_count > 0);
        setLessonOptions(options);
        setRegenLesson((current) => current || (options.find((lesson) => lesson.id === "general-a1")?.id || options[0]?.id || ""));
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const updateField = (event) => {
    const { name, value, type, checked } = event.target;
    setForm((old) => ({ ...old, [name]: type === "checkbox" ? checked : value }));
  };

  function startEdit(item) {
    setEditing(item);
    setForm({
      prompt: item.prompt || "",
      options: (item.options || []).join("\n"),
      correct_answer: item.correct_answer || "",
      accepted_answers: (item.accepted_answers || []).join("\n"),
      cloze: item.cloze || "",
      hint: item.hint || "",
      active: item.active !== false,
    });
    setFormError("");
    document.getElementById("admin-exercise-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function cancelEdit() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError("");
  }

  async function submit(event) {
    event.preventDefault();
    if (saving || !editing) return;
    setSaving(true);
    setFormError("");
    const options = splitLines(form.options);
    if (editing.skill === "meaning" && options.length < 2) {
      setFormError("Câu hỏi Meaning cần ít nhất 2 lựa chọn.");
      setSaving(false);
      return;
    }
    try {
      await updateAdminExercise(editing.exercise_item_id, {
        prompt: form.prompt.trim(),
        options,
        correct_answer: form.correct_answer.trim(),
        accepted_answers: splitLines(form.accepted_answers),
        cloze: form.cloze.trim() || null,
        hint: form.hint.trim() || null,
        active: form.active,
      });
      setNotice(`Đã cập nhật câu hỏi ${editing.exercise_item_id}.`);
      cancelEdit();
      await load();
    } catch (err) {
      setFormError(formatApiError(err, "Không thể cập nhật câu hỏi."));
    } finally {
      setSaving(false);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Xóa câu hỏi "${item.prompt}"?`)) return;
    setBusyId(item.exercise_item_id);
    setError("");
    setNotice("");
    try {
      await deleteAdminExercise(item.exercise_item_id);
      setNotice("Đã xóa câu hỏi.");
      if (editing?.exercise_item_id === item.exercise_item_id) cancelEdit();
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể xóa câu hỏi."));
    } finally {
      setBusyId(null);
    }
  }

  async function toggleActive(item) {
    setBusyId(item.exercise_item_id);
    setError("");
    setNotice("");
    try {
      await updateAdminExercise(item.exercise_item_id, { active: !item.active });
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể đổi trạng thái câu hỏi."));
    } finally {
      setBusyId(null);
    }
  }

  async function regenerate() {
    if (!regenLesson) return;
    setRegenerating(true);
    setError("");
    setNotice("");
    try {
      const data = await regenerateAdminExercises(regenLesson);
      setNotice(`Đã tạo/cập nhật ${data.items} câu hỏi cho ${data.lesson_id}.`);
      await load();
    } catch (err) {
      setError(formatApiError(err, "Không thể tái tạo câu hỏi."));
    } finally {
      setRegenerating(false);
    }
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="sv-page sv-admin-page">
      <div className="sv-page-heading">
        <div>
          <span className="sv-eyebrow">ADMIN / CÂU HỎI</span>
          <h1>Quản lý câu hỏi</h1>
          <p>Kiểm tra và chỉnh sửa câu hỏi Meaning, Spelling, Context. Đáp án được lưu phía server và không gửi xuống người học.</p>
        </div>
        <span className="sv-catalog-count">{total} câu hỏi</span>
      </div>

      {notice && <div className="sv-admin-success" role="status">{notice}</div>}
      {error && <div className="sv-admin-error" role="alert">{error}</div>}

      <section className="sv-admin-form">
        <h2>Tái tạo ngân hàng câu hỏi</h2>
        <p>Sinh lại câu hỏi từ từ vựng hiện có của một bài học. Thao tác này cập nhật các câu chuẩn theo dữ liệu mới nhất.</p>
        <div className="sv-admin-inline">
          <select className="sv-answer-field sv-admin-grow" value={regenLesson} onChange={(event) => setRegenLesson(event.target.value)} aria-label="Chọn bài học để tái tạo câu hỏi">
            {lessonOptions.length ? lessonOptions.map((lesson) => <option value={lesson.id} key={lesson.id}>{lesson.title} ({lesson.word_count} từ)</option>) : <option value="">Chưa có bài học có từ vựng</option>}
          </select>
          <button type="button" className="sv-btn sv-btn-primary" onClick={regenerate} disabled={regenerating || !regenLesson}>{regenerating ? "Đang tái tạo..." : "Tái tạo câu hỏi"}</button>
        </div>
      </section>

      {editing && (
        <section className="sv-admin-form" id="admin-exercise-form" style={{ marginTop: 18 }}>
          <div className="sv-admin-inline" style={{ justifyContent: "space-between" }}>
            <div><h2>Chỉnh sửa câu hỏi</h2><p>{editing.exercise_item_id} · {editing.word || editing.skill}</p></div>
            <span className={`sv-admin-badge ${editing.skill}`}>{editing.skill}</span>
          </div>
          <form onSubmit={submit}>
            <label className="sv-form-label" htmlFor="exercise-prompt">Nội dung câu hỏi</label>
            <textarea className="sv-answer-field" id="exercise-prompt" name="prompt" value={form.prompt} onChange={updateField} rows={2} required />
            <div className="sv-admin-form-grid">
              <div>
                <label className="sv-form-label" htmlFor="exercise-correct">Đáp án đúng</label>
                <input className="sv-answer-field" id="exercise-correct" name="correct_answer" value={form.correct_answer} onChange={updateField} required />
              </div>
              <div>
                <label className="sv-form-label" htmlFor="exercise-hint">Gợi ý</label>
                <input className="sv-answer-field" id="exercise-hint" name="hint" value={form.hint} onChange={updateField} />
              </div>
            </div>
            <label className="sv-form-label" htmlFor="exercise-options">Lựa chọn (mỗi dòng một lựa chọn)</label>
            <textarea className="sv-answer-field" id="exercise-options" name="options" value={form.options} onChange={updateField} rows={3} placeholder={editing.skill === "meaning" ? "Bắt buộc với câu Meaning" : "Không bắt buộc với Spelling/Context"} />
            <label className="sv-form-label" htmlFor="exercise-accepted">Đáp án được chấp nhận (mỗi dòng một đáp án)</label>
            <textarea className="sv-answer-field" id="exercise-accepted" name="accepted_answers" value={form.accepted_answers} onChange={updateField} rows={2} />
            <label className="sv-form-label" htmlFor="exercise-cloze">Câu cloze (Context)</label>
            <textarea className="sv-answer-field" id="exercise-cloze" name="cloze" value={form.cloze} onChange={updateField} rows={2} />
            <label className="sv-admin-check"><input name="active" type="checkbox" checked={form.active} onChange={updateField} /> Câu hỏi đang hoạt động</label>
            {formError && <div className="sv-admin-error" role="alert">{formError}</div>}
            <div className="sv-admin-form-actions">
              <button type="button" className="sv-btn sv-btn-outline" onClick={cancelEdit} disabled={saving}>Hủy</button>
              <button type="submit" className="sv-btn sv-btn-primary" disabled={saving}>{saving ? "Đang lưu..." : "Lưu câu hỏi"}</button>
            </div>
          </form>
        </section>
      )}

      <div className="sv-admin-section-title" style={{ marginTop: 24 }}><div><span>NGÂN HÀNG CÂU HỎI</span><h2>Danh sách câu hỏi</h2></div></div>
      <div className="sv-admin-toolbar">
        <input className="sv-answer-field sv-admin-grow" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo từ hoặc nội dung câu hỏi..." aria-label="Tìm câu hỏi" />
        <select className="sv-answer-field" value={domain} onChange={(event) => setDomain(event.target.value)} aria-label="Lọc lĩnh vực">
          <option value="">Tất cả lĩnh vực</option>
          {DOMAINS.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
        </select>
        <select className="sv-answer-field" value={level} onChange={(event) => setLevel(event.target.value)} aria-label="Lọc cấp độ">
          <option value="">Tất cả cấp độ</option>
          {LEVELS.map((item) => <option value={item} key={item}>{item}</option>)}
        </select>
        <select className="sv-answer-field" value={skill} onChange={(event) => setSkill(event.target.value)} aria-label="Lọc kỹ năng">
          <option value="">Tất cả kỹ năng</option>
          {SKILLS.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
        </select>
        <select className="sv-answer-field" value={active} onChange={(event) => setActive(event.target.value)} aria-label="Lọc trạng thái">
          <option value="">Mọi trạng thái</option>
          <option value="true">Đang hoạt động</option>
          <option value="false">Đã tắt</option>
        </select>
        <button type="button" className="sv-admin-refresh" onClick={load} disabled={loading}>{loading ? "Đang tải..." : "↻ Làm mới"}</button>
        <span className="sv-admin-count">Trang {page}/{pages}</span>
      </div>

      {loading && !items.length ? <PageLoading label="Đang tải câu hỏi..." /> : error && !items.length ? <PageError message={error} onRetry={load} /> : (
        <>
          <div className="sv-admin-table-wrap">
            <table className="sv-admin-table">
              <thead><tr><th>Câu hỏi</th><th>Kỹ năng</th><th>Bài học</th><th>Đáp án</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
              <tbody>
                {items.length ? items.map((item) => (
                  <tr key={item.exercise_item_id}>
                    <td><div className="sv-admin-cell-main"><span><strong>{item.prompt}</strong><small>{item.word || item.exercise_item_id}</small></span></div></td>
                    <td><span className={`sv-admin-badge ${item.skill}`}>{item.skill}</span></td>
                    <td>{item.domain} · {item.level}</td>
                    <td><span className="sv-admin-strong">{item.correct_answer}</span>{item.options?.length ? <small className="sv-admin-muted"> · {item.options.length} lựa chọn</small> : null}</td>
                    <td><button type="button" className={`sv-admin-badge ${item.active ? "admin" : "off"}`} onClick={() => toggleActive(item)} disabled={busyId === item.exercise_item_id} title="Bấm để đổi trạng thái">{item.active ? "Hoạt động" : "Đã tắt"}</button></td>
                    <td><div className="sv-admin-actions"><button type="button" className="sv-edit-link" onClick={() => startEdit(item)}>Sửa</button><button type="button" className="sv-danger-link" onClick={() => remove(item)} disabled={busyId === item.exercise_item_id}>{busyId === item.exercise_item_id ? "Đang xử lý..." : "Xóa"}</button></div></td>
                  </tr>
                )) : <tr><td colSpan={6} className="sv-admin-empty-cell"><strong>Không tìm thấy câu hỏi</strong>Hãy tái tạo câu hỏi cho một bài học có từ vựng hoặc đổi bộ lọc.</td></tr>}
              </tbody>
            </table>
          </div>
          {pages > 1 && <div className="sv-admin-pagination"><button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>← Trước</button><span>Trang {page} / {pages}</span><button type="button" onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages}>Sau →</button></div>}
        </>
      )}
    </div>
  );
}
