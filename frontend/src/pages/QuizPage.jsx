import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchLesson, fetchQuiz, submitQuiz } from "../services/lessonService";
import { formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading } from "../components/PageState";

export default function QuizPage() {
  const { lessonId } = useParams();
  const [lesson, setLesson] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [durations, setDurations] = useState({});
  const [index, setIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchLesson(lessonId), fetchQuiz(lessonId, 10)])
      .then(([lessonData, quizData]) => { if (active) { setLesson(lessonData); setQuestions(quizData?.questions || []); setError(""); } })
      .catch((err) => { if (active) setError(formatApiError(err, "Không thể tạo bài kiểm tra. Có thể bài học thiếu từ vựng.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [lessonId, refresh]);

  useEffect(() => { startedAt.current = Date.now(); }, [index]);

  function choose(option) {
    if (submitting) return;
    setAnswers((old) => ({ ...old, [index]: option }));
    setDurations((old) => ({ ...old, [index]: old[index] ?? Math.min(600000, Date.now() - startedAt.current) }));
    setError("");
  }

  async function finish() {
    if (submitting || questions.some((_, i) => answers[i] == null)) return;
    setSubmitting(true); setError("");
    const rows = questions.map((question, i) => ({
      vocabulary_id: question.vocabulary_id,
      question_token: question.question_token,
      user_answer: answers[i],
      response_time_ms: Math.min(600000, Math.max(0, Math.round(durations[i] ?? 0))),
      hint_used: false,
    }));
    try { setResult(await submitQuiz(lessonId, rows)); }
    catch (err) { setError(formatApiError(err, "Nộp bài không thành công. Bạn có thể thử lại với cùng các câu hỏi.")); }
    finally { setSubmitting(false); }
  }

  if (loading) return <PageLoading label="Đang chuẩn bị bài kiểm tra..."/>;
  if (!lesson || !questions.length) return <div className="sv-page"><div className="sv-breadcrumb"><Link to={`/lessons/${lessonId}`}>← Quay lại bài học</Link></div>{error ? <PageError message={error} onRetry={() => setRefresh((value)=>value+1)}/> : <EmptyState title="Chưa có câu hỏi" description="Lesson cần có ít nhất hai từ vựng để tạo quiz."/>}</div>;

  if (result) return (
    <div className="sv-page">
      <div className="sv-practice-result">
        <span className="sv-success-symbol">
          {result.passed ? "✓" : "↗"}
        </span>

        <span className="sv-eyebrow">KẾT QUẢ BÀI KIỂM TRA</span>

        <h1>
          {result.passed
            ? "Hoàn thành xuất sắc!"
            : "Hãy luyện tập thêm nhé!"}
        </h1>

        <p>Điểm đã được backend chấm và cập nhật.</p>

        <div className="sv-result-grid">
          <div>
            <strong>{result.correct}/{result.total}</strong>
            <span>Trả lời đúng</span>
          </div>
          <div>
            <strong>{result.percent}%</strong>
            <span>Độ chính xác</span>
          </div>
          <div>
            <strong>+{result.xp_gained}</strong>
            <span>XP nhận được</span>
          </div>
        </div>

        <div className="sv-result-actions">
          <Link className="sv-btn sv-btn-outline" to={`/lessons/${lessonId}`}>
            Quay về bài học
          </Link>
          <Link className="sv-btn sv-btn-primary" to="/dashboard">
            Xem tổng quan →
          </Link>
        </div>
      </div>

      <section className="sv-ai-analysis">
        <h2>Phân tích lỗi sai: Vấn đề gặp phải </h2>

        {result.error_analysis?.length > 0 ? (
          result.error_analysis.map((item, i) => (
            <article
              className="sv-ai-mistake mistake-analysis-item"
              key={`${item.vocabulary_id}-${i}`}
            >
              <h3>Câu {i + 1}: {item.question}</h3>

              <p>
                <strong>Bạn đã chọn:</strong> {item.user_answer || "(Chưa trả lời)"}
              </p>

              <p>
                <strong>Đáp án đúng:</strong> {item.correct_answer}
              </p>

              {item.analysis ? (
                <>
                  <p>
                    <strong>Loại lỗi:</strong> {item.analysis.error_type}
                  </p>

                  <p>
                    <strong>Bạn sai ở đâu:</strong>{" "}
                    {item.analysis.what_went_wrong}
                  </p>

                  <p>
                    <strong>AI giải thích:</strong>{" "}
                    {item.analysis.explanation}
                  </p>

                  {item.analysis.example && (
                    <p>
                      <strong>Ví dụ:</strong> {item.analysis.example}
                    </p>
                  )}

                  {item.analysis.tip && (
                    <p>
                      <strong>Mẹo ghi nhớ:</strong> {item.analysis.tip}
                    </p>
                  )}
                </>
              ) : (
                <p>AI chưa tạo được phân tích cho câu này.</p>
              )}
            </article>
          ))
        ) : (
          <p>
            {result.correct === result.total
              ? "Bạn đã trả lời đúng tất cả câu hỏi. Không có lỗi sai cần phân tích."
              : "Chưa nhận được dữ liệu phân tích lỗi sai từ backend."}
          </p>
        )}
      </section>
    </div>
  );

  const question = questions[index];
  const answeredCount = questions.filter((_, i) => answers[i] !== undefined).length;
  return <div className="sv-page sv-practice-page"><div className="sv-practice-top"><Link className="sv-back-link" to={`/lessons/${lessonId}`}>← Thoát kiểm tra</Link><span className="sv-level-tag">Quiz · {index+1}/{questions.length}</span></div><div className="sv-progress-track"><div style={{width:`${(index+1)/questions.length*100}%`}}/></div>
    <div className="sv-practice-panel"><div className="sv-practice-heading"><span className="sv-eyebrow">KIỂM TRA CUỐI BÀI · {lesson.title}</span><span className="sv-question-number">{String(index+1).padStart(2,"0")}</span></div><h1>{question.question}</h1><p className="sv-practice-tip">Chọn đáp án bạn cho là chính xác.</p><div className="sv-options-grid">{(question.options || []).map((option, i) => <button key={`${i}-${option}`} className={`sv-option${answers[index] === option ? " selected" : ""}`} onClick={() => choose(option)} disabled={submitting}><span className="sv-option-letter">{String.fromCharCode(65+i)}</span>{option}</button>)}</div>
      {error && <div className="sv-notice sv-notice-error" role="alert">{error}</div>}
      <div className="sv-quiz-footer"><button className="sv-btn sv-btn-outline" onClick={() => setIndex((value)=>Math.max(0,value-1))} disabled={index===0 || submitting}>← Câu trước</button><span className="sv-muted-small">Đã trả lời {answeredCount}/{questions.length}</span>{index + 1 < questions.length ? <button className="sv-btn sv-btn-primary" disabled={answers[index] === undefined || submitting} onClick={() => setIndex((value)=>value+1)}>Câu tiếp →</button> : <button className="sv-btn sv-btn-primary" disabled={answeredCount < questions.length || submitting} onClick={finish}>{submitting ? "Đang nộp..." : "Nộp bài →"}</button>}</div>
    </div>
  </div>;
}
