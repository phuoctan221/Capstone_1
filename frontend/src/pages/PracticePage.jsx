import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchLesson } from "../services/lessonService";
import { submitPracticeAnswer } from "../services/exerciseService";
import { SKILLS, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading } from "../components/PageState";

const randomize = (items) => {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
};
const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function makeCloze(word) {
  const example = String(word.example || "").trim();
  const target = String(word.word || "").trim();
  if (!example || !target) return null;
  const matcher = new RegExp(`(^|[^\\p{L}])(${escapeRegex(target)})(?=$|[^\\p{L}])`, "iu");
  return matcher.test(example) ? example.replace(matcher, (_, prefix) => `${prefix}________`) : null;
}

export default function PracticePage() {
  const { lessonId, skill } = useParams();
  const skillConfig = SKILLS.find((item) => item.id === skill);
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [hint, setHint] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null);
  const [totalCorrect, setTotalCorrect] = useState(0);
  const [xp, setXp] = useState(0);
  const [finished, setFinished] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchLesson(lessonId).then((data) => {
      if (active) { setLesson(data); setError(""); startedAt.current = Date.now(); }
    }).catch((err) => { if (active) setError(formatApiError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [lessonId, refresh]);

  useEffect(() => { setIndex(0); setAnswer(""); setFeedback(null); setHint(false); setPending(null); setTotalCorrect(0); setXp(0); setFinished(false); startedAt.current = Date.now(); }, [lessonId, skill]);

  const queue = useMemo(() => {
    const words = Array.isArray(lesson?.words) ? lesson.words : [];
    if (skill === "context") return words.filter((item) => makeCloze(item));
    if (skill === "meaning" && new Set(words.map((item) => item.meaning)).size < 2) return [];
    return words;
  }, [lesson, skill]);
  const current = queue[index];
  const choices = useMemo(() => {
    if (!current || skill !== "meaning") return [];
    const others = randomize([...new Set(queue.filter((w) => w.id !== current.id).map((item) => item.meaning))].filter((item) => item !== current.meaning)).slice(0, 3);
    return randomize([current.meaning, ...others]);
  }, [current, queue, skill]);

  async function send(payload) {
    setBusy(true);
    setError("");
    try {
      const result = await submitPracticeAnswer(payload);
      setFeedback(result);
      setTotalCorrect((value) => value + Number(Boolean(result.correct)));
      setXp((value) => value + Number(result.xp_gained || 0));
      setPending(null);
    } catch (err) {
      setError(formatApiError(err, "Không thể lưu câu trả lời. Thử gửi lại để tránh tính điểm trùng."));
      setPending(payload);
    } finally { setBusy(false); }
  }

  function submit(value) {
    if (busy || feedback || pending || !current) return;
    const submitted = String(value || "").trim();
    if (!submitted) return;
    setAnswer(submitted);
    const payload = {
      vocabularyId: current.id,
      answer: submitted,
      skill,
      attemptId: crypto.randomUUID(),
      responseTimeMs: Math.max(0, Date.now() - startedAt.current),
      hintUsed: hint,
    };
    send(payload);
  }

  function next() {
    if (index + 1 >= queue.length) { setFinished(true); return; }
    setIndex((value) => value + 1);
    setAnswer(""); setFeedback(null); setPending(null); setHint(false); setError("");
    startedAt.current = Date.now();
  }

  if (!skillConfig) return <PageError message="Kỹ năng không hợp lệ. Chọn Meaning, Spelling hoặc Context."/>;
  if (loading) return <PageLoading label="Đang chuẩn bị bài luyện tập..."/>;
  if (!lesson) return <PageError message={error || "Không tìm thấy bài học."} onRetry={() => setRefresh((value) => value+1)}/>;
  if (!queue.length) return <div className="sv-page"><div className="sv-breadcrumb"><Link to={`/lessons/${lessonId}`}>← Quay lại bài học</Link></div><EmptyState title="Chưa đủ câu hỏi cho kỹ năng này" description={skill === "context" ? "Cần các từ có câu ví dụ chứa chính từ cần điền. Backend nên cung cấp ngân hàng Context đã kiểm duyệt." : "Cần thêm từ vựng hoặc nghĩa khác nhau trong bài học trước khi luyện."}><Link className="sv-btn sv-btn-primary" to={`/lessons/${lessonId}`}>Về bài học</Link></EmptyState></div>;

  if (finished) return <div className="sv-page"><div className="sv-practice-result"><span className="sv-success-symbol">✓</span><span className="sv-eyebrow">HOÀN THÀNH BUỔI HỌC</span><h1>Bạn đã hoàn thành {skillConfig.label}!</h1><p>Kết quả đã được backend chấm và lưu vào tiến độ học tập.</p><div className="sv-result-grid"><div><strong>{totalCorrect}/{queue.length}</strong><span>Câu đúng</span></div><div><strong>{Math.round(totalCorrect / queue.length * 100)}%</strong><span>Độ chính xác</span></div><div><strong>+{xp}</strong><span>XP nhận được</span></div></div><Link to={`/lessons/${lessonId}`} className="sv-btn sv-btn-primary">Trở về bài học →</Link></div></div>;

  return <div className="sv-page sv-practice-page">
    <div className="sv-practice-top"><Link to={`/lessons/${lessonId}`} className="sv-back-link">← Thoát bài luyện</Link><div><span className="sv-level-tag">{skillConfig.label}</span><span className="sv-muted-small"> Câu {index + 1} / {queue.length}</span></div></div>
    <div className="sv-progress-track" role="progressbar" aria-valuenow={index + 1} aria-valuemin={0} aria-valuemax={queue.length}><div style={{ width: `${(index + 1) / queue.length * 100}%` }}/></div>
    <div className="sv-practice-panel"><div className="sv-practice-heading"><span className="sv-eyebrow">{skillConfig.subtitle.toUpperCase()}</span><span className="sv-question-number">{String(index+1).padStart(2,"0")} / {String(queue.length).padStart(2,"0")}</span></div>
      {skill === "meaning" && <><h1>“{current.word}” có nghĩa là gì?</h1><p className="sv-practice-tip">Chọn một đáp án. Hệ thống sẽ chấm điểm trên máy chủ.</p><div className="sv-options-grid">{choices.map((option, i) => <button key={`${option}-${i}`} type="button" className={`sv-option${answer === option ? " selected" : ""}`} disabled={busy || Boolean(feedback) || Boolean(pending)} onClick={() => submit(option)}><span className="sv-option-letter">{String.fromCharCode(65+i)}</span>{option}</button>)}</div></>}
      {skill === "spelling" && <><h1>Viết từ tiếng Anh có nghĩa:</h1><div className="sv-definition">{current.meaning}</div><p className="sv-practice-tip">Nhập từ chính xác vào ô bên dưới.</p></>}
      {skill === "context" && <><h1>Điền từ thích hợp vào chỗ trống.</h1><div className="sv-context-line">{makeCloze(current)}</div><p className="sv-practice-tip">Nghĩa gợi ý: {current.meaning}</p></>}
      {skill !== "meaning" && <form onSubmit={(e) => { e.preventDefault(); submit(answer); }}><label htmlFor="practice-answer" className="sv-form-label">Câu trả lời của bạn</label><input id="practice-answer" className="sv-answer-field" value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={busy || Boolean(feedback) || Boolean(pending)} autoComplete="off" autoFocus placeholder="Nhập từ tiếng Anh..."/><div className="sv-practice-bottom"><button type="button" className="sv-btn sv-btn-outline" disabled={Boolean(feedback) || busy || Boolean(pending)} onClick={() => setHint(true)}>{hint ? `Gợi ý: ${current.word?.charAt(0) || "?"}…` : "Xem gợi ý"}</button><button className="sv-btn sv-btn-primary" type="submit" disabled={!answer.trim() || busy || Boolean(feedback) || Boolean(pending)}>{busy ? "Đang chấm..." : "Kiểm tra →"}</button></div></form>}
      {error && <div className="sv-notice sv-notice-error" role="alert">{error} {pending && <button type="button" disabled={busy} onClick={() => send(pending)}>Thử gửi lại cùng mã câu trả lời</button>}</div>}
      {feedback && <div className={`sv-answer-feedback ${feedback.correct ? "sv-feedback-success" : "sv-feedback-wrong"}`} role="status"><div><strong>{feedback.correct ? "Chính xác!" : "Chưa đúng, tiếp tục cố gắng!"}</strong><p>Đáp án đúng: <b>{feedback.correct_answer || "—"}</b>{feedback.xp_gained != null && ` · +${feedback.xp_gained} XP`}</p></div><button type="button" className="sv-btn sv-btn-primary" onClick={next}>{index + 1 >= queue.length ? "Xem kết quả →" : "Câu tiếp theo →"}</button></div>}
    </div>
    <div className="sv-practice-footnote">Kết quả được đánh giá tại backend · Mỗi lần trả lời có ID riêng để tránh cộng điểm trùng.</div>
  </div>;
}
