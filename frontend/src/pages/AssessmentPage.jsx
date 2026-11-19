import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { createAssessment, fetchAssessment, submitAssessment } from "../services/lessonService";
import { formatApiError } from "../constants/domains";
import { PageError, PageLoading } from "../components/PageState";

export default function AssessmentPage() {
  const { domain, level } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const skipLearning = searchParams.get("skip") === "1";
  const isPlacement = searchParams.get("placement") === "1";
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; setLoading(true); createAssessment(domain, level.toUpperCase(), skipLearning, isPlacement ? level.toUpperCase() : null).then((data) => { if (active) { setAttempt(data); setAnswers(Object.fromEntries((data.questions || []).map((item) => [item.exercise_item_id, ""]))); } }).catch((err) => { if (active) setError(formatApiError(err)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [domain, level, skipLearning, isPlacement]);
  const update = (id, value) => setAnswers((previous) => ({ ...previous, [id]: value }));
  const submit = async (event) => { event.preventDefault(); if (!attempt || submitting) return; if (Object.values(answers).some((value) => !String(value).trim())) return setError("Hãy trả lời tất cả câu hỏi trước khi nộp bài."); setSubmitting(true); setError(""); try { setResult(await submitAssessment(attempt.attempt_id, attempt.questions.map((item) => ({ exercise_item_id: item.exercise_item_id, answer: answers[item.exercise_item_id] })))); } catch (err) { setError(formatApiError(err, "Không thể nộp bài đánh giá.")); } finally { setSubmitting(false); } };
  if (loading) return <PageLoading label="Đang chuẩn bị Level Assessment..." />;
  if (error && !attempt) return <PageError message={error} onRetry={() => navigate(0)} />;
  if (result) return <div className="sv-page"><div className="sv-practice-result"><span className="sv-success-symbol">{result.passed ? "✓" : "↗"}</span><span className="sv-eyebrow">LEVEL ASSESSMENT · {level.toUpperCase()}</span><h1>{result.passed ? "Bạn đã được thăng cấp!" : "Chưa đạt mốc thăng cấp"}</h1><p>{result.passed ? `Bạn đã mở khóa ${result.opened_level || result.next_level || "cấp độ tiếp theo"}.${result.placement_target ? " Các cấp thấp hơn hiện dùng để ôn tập tùy chọn." : ""}` : "Hoàn thành thêm luyện tập rồi thử lại sau thời gian chờ."}</p><div className="sv-result-grid"><div><strong>{result.correct}/{result.total}</strong><span>Trả lời đúng</span></div><div><strong>{result.percent}%</strong><span>Điểm số</span></div><div><strong>{result.passed ? "PASS" : "RETRY"}</strong><span>Trạng thái</span></div></div><div className="sv-result-actions"><Link className="sv-btn sv-btn-primary" to="/learn">Về lộ trình →</Link></div></div></div>;
  return <div className="sv-page sv-practice-page"><div className="sv-page-heading"><div><span className="sv-eyebrow">{skipLearning ? "HỌC VƯỢT · " : ""}LEVEL ASSESSMENT</span><h1>Đánh giá cấp độ {level.toUpperCase()}</h1><p>{isPlacement ? `Đạt từ 70% để vào thẳng ${level.toUpperCase()}; các cấp thấp hơn vẫn có thể dùng để ôn tập.` : skipLearning ? "Bạn đang làm bài kiểm tra học vượt. " : ""}{!isPlacement && "Pass từ 70% để mở khóa Level tiếp theo. "}Bài làm hết hạn vào {new Date(attempt.expires_at).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}.</p></div><Link to="/learn" className="sv-btn sv-btn-outline">Quay lại</Link></div><form className="sv-assessment-form" onSubmit={submit}>{attempt.questions.map((item, index) => <article className="sv-assessment-question" key={item.exercise_item_id}><b>Câu {index + 1}/{attempt.questions.length} · {item.skill}</b><p>{item.cloze || item.prompt}</p>{item.options?.length ? <div className="sv-assessment-options">{item.options.map((option) => <label key={option}><input type="radio" name={item.exercise_item_id} value={option} checked={answers[item.exercise_item_id] === option} onChange={(event) => update(item.exercise_item_id, event.target.value)} /> {option}</label>)}</div> : <input value={answers[item.exercise_item_id] || ""} onChange={(event) => update(item.exercise_item_id, event.target.value)} placeholder="Nhập câu trả lời" />}</article>)}{error && <p className="sv-notice sv-notice-error">{error}</p>}<button className="sv-btn sv-btn-primary" disabled={submitting}>{submitting ? "Đang chấm..." : "Nộp Level Assessment"}</button></form></div>;
}