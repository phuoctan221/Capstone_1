import { useEffect, useState, useCallback } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { createAssessment, submitAssessment } from "../services/lessonService";
import { fetchMe } from "../services/authService";
import { formatApiError } from "../constants/domains";
import { PageError, PageLoading } from "../components/PageState";

const LEVEL_DESC = {
  A1: "Mới bắt đầu", A2: "Cơ bản", B1: "Trung cấp",
  B2: "Trung cấp khá", C1: "Nâng cao", C2: "Thành thạo",
};

export default function AssessmentPage() {
  const { domain, level } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const skipLearning = searchParams.get("skip") === "1";
  const isPlacement = searchParams.get("placement") === "1";
  const domainsParam = searchParams.get("domains") || "";
  const returnTo = searchParams.get("return") || "/learn";

  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [currentQ, setCurrentQ] = useState(0);
  const [timeLeft, setTimeLeft] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const parsedDomains = domainsParam
      ? domainsParam.split(",").map((d) => d.trim()).filter(Boolean)
      : null;
    createAssessment(
      domain,
      level.toUpperCase(),
      skipLearning,
      isPlacement ? level.toUpperCase() : null,
      parsedDomains
    )
      .then((data) => {
        if (!active) return;
        setAttempt(data);
        setAnswers(
          Object.fromEntries(
            (data.questions || []).map((item) => [item.exercise_item_id, ""])
          )
        );
        if (data.expires_at) {
          const ms = new Date(data.expires_at).getTime() - Date.now();
          setTimeLeft(Math.max(0, Math.floor(ms / 1000)));
        }
      })
      .catch((err) => {
        if (active) setError(formatApiError(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [domain, level, skipLearning, isPlacement, domainsParam]);

  // Countdown timer
  useEffect(() => {
    if (timeLeft === null || timeLeft <= 0 || result) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) { clearInterval(timer); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [timeLeft, result]);

  const formatTime = (seconds) => {
    if (seconds === null) return "";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const update = (id, value) =>
    setAnswers((prev) => ({ ...prev, [id]: value }));

  const submit = useCallback(async (event) => {
    if (event) event.preventDefault();
    if (!attempt || submitting) return;
    const unanswered = Object.values(answers).filter((v) => !String(v).trim()).length;
    if (unanswered > 0) {
      setError(`Còn ${unanswered} câu chưa trả lời. Hãy hoàn thành tất cả trước khi nộp bài.`);
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const res = await submitAssessment(
        attempt.attempt_id,
        attempt.questions.map((item) => ({
          exercise_item_id: item.exercise_item_id,
          answer: answers[item.exercise_item_id],
        }))
      );
      setResult(res);
      // Refresh user data in localStorage so level updates show immediately
      try { await fetchMe(); } catch {}
    } catch (err) {
      setError(formatApiError(err, "Không thể nộp bài đánh giá."));
    } finally {
      setSubmitting(false);
    }
  }, [attempt, answers, submitting]);

  // Auto-submit when time runs out
  useEffect(() => {
    if (timeLeft === 0 && attempt && !result && !submitting) {
      submit();
    }
  }, [timeLeft, attempt, result, submitting, submit]);

  if (loading) return <PageLoading label="Đang chuẩn bị bài kiểm tra đánh giá..." />;
  if (error && !attempt) return <PageError message={error} onRetry={() => navigate(0)} />;

  const questions = attempt?.questions || [];
  const totalQ = questions.length;
  const answered = Object.values(answers).filter((v) => String(v).trim()).length;
  const progressPct = totalQ > 0 ? Math.round((answered / totalQ) * 100) : 0;

  // === RESULT SCREEN ===
  if (result) {
    const questionMap = Object.fromEntries(
      questions.map((q) => [q.exercise_item_id, q])
    );
    const wrongItems = (result.results || [])
      .map((r, i) => ({ ...r, index: i }))
      .filter((r) => !r.correct);
    const requiredCorrect = Math.ceil((result.total || 0) * 0.85);

    return (
      <div className="sv-page">
        <div className="sv-practice-result">
          <span className="sv-success-symbol">{result.passed ? "✓" : "✗"}</span>
          <span className="sv-eyebrow">
            BÀI KIỂM TRA ĐÁNH GIÁ · {level.toUpperCase()} - {LEVEL_DESC[level.toUpperCase()] || ""}
          </span>
          <h1>{result.passed ? "Chúc mừng! Bạn đã thăng hạng!" : "Chưa đạt yêu cầu thăng hạng"}</h1>
          <p>
            {result.passed
              ? `Bạn đã mở khóa trình độ ${result.opened_level || result.next_level || "tiếp theo"}. Lộ trình học tập đã được cập nhật.`
              : `Bạn cần đạt tối thiểu 85% (${requiredCorrect}/${result.total} câu đúng) để thăng hạng. Hãy ôn luyện thêm và thử lại sau.`}
          </p>
          <div className="sv-result-grid">
            <div>
              <strong>{result.correct}/{result.total}</strong>
              <span>Trả lời đúng</span>
            </div>
            <div>
              <strong>{result.percent}%</strong>
              <span>Điểm số</span>
            </div>
            <div>
              <strong>{result.passed ? "ĐẠT" : "CHƯA ĐẠT"}</strong>
              <span>Trạng thái</span>
            </div>
          </div>

          {/* Show incorrect answers with full question text for review */}
          {wrongItems.length > 0 && (
            <div className="assessment-review">
              <h3>Chi tiết các câu trả lời sai ({wrongItems.length} câu):</h3>
              {wrongItems.map((r) => {
                const fallbackQ = questionMap[r.exercise_item_id] || {};
                const qText = r.cloze || r.prompt || fallbackQ.cloze || fallbackQ.prompt || "";
                const qSkill = r.skill || fallbackQ.skill || "";
                return (
                  <div key={r.exercise_item_id} className="assessment-review-item">
                    <div className="review-q-head">
                      <span className="review-q-num">
                        Câu {r.index + 1}{qSkill ? ` · ${qSkill.toUpperCase()}` : ""}
                      </span>
                    </div>
                    {qText && <p className="review-q-prompt">{qText}</p>}
                    <span className="review-wrong">
                      Bạn trả lời: {r.user_answer || "(bỏ trống)"}
                    </span>
                    <span className="review-correct">
                      Đáp án đúng: {r.correct_answer}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          <div className="sv-result-actions">
            {result.passed ? (
              <Link className="sv-btn sv-btn-primary" to={returnTo}>
                Tiếp tục học tập →
              </Link>
            ) : (
              <>
                <Link className="sv-btn sv-btn-primary" to="/learn">
                  Về ôn luyện thêm
                </Link>
                <Link className="sv-btn sv-btn-outline" to={returnTo}>
                  Quay lại cài đặt
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  const currentQuestion = questions[currentQ];

  // === TEST SCREEN ===
  return (
    <div className="sv-page sv-practice-page">
      <div className="sv-page-heading">
        <div>
          <span className="sv-eyebrow">
            BÀI KIỂM TRA ĐÁNH GIÁ · {level.toUpperCase()} - {LEVEL_DESC[level.toUpperCase()] || ""}
          </span>
          <h1>Đánh giá trình độ {level.toUpperCase()}</h1>
          <p>
            Trả lời đúng tối thiểu 85% ({Math.ceil(totalQ * 0.85)}/{totalQ} câu) để thăng hạng lên {level.toUpperCase()}.
          </p>
        </div>
        <div className="assessment-header-info">
          {timeLeft !== null && (
            <div className={`assessment-timer ${timeLeft < 60 ? "timer-warning" : ""}`}>
              ⏱ {formatTime(timeLeft)}
            </div>
          )}
          <div className="assessment-progress-text">
            {answered}/{totalQ} đã trả lời
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="assessment-progress-bar">
        <div
          className="assessment-progress-fill"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Question navigation dots */}
      <div className="assessment-nav-dots">
        {questions.map((q, i) => (
          <button
            key={q.exercise_item_id}
            type="button"
            className={`assessment-dot ${i === currentQ ? "dot-active" : ""} ${
              String(answers[q.exercise_item_id] || "").trim() ? "dot-answered" : ""
            }`}
            onClick={() => setCurrentQ(i)}
            title={`Câu ${i + 1}`}
          >
            {i + 1}
          </button>
        ))}
      </div>

      {/* Current question */}
      {currentQuestion && (
        <form className="sv-assessment-form" onSubmit={submit}>
          <article className="sv-assessment-question">
            <b>Câu {currentQ + 1}/{totalQ} · {currentQuestion.skill}</b>
            <p className="assessment-prompt">
              {currentQuestion.cloze || currentQuestion.prompt}
            </p>
            {currentQuestion.options?.length ? (
              <div className="sv-assessment-options">
                {currentQuestion.options.map((option) => (
                  <label
                    key={option}
                    className={`assessment-option ${
                      answers[currentQuestion.exercise_item_id] === option
                        ? "option-selected"
                        : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name={currentQuestion.exercise_item_id}
                      value={option}
                      checked={answers[currentQuestion.exercise_item_id] === option}
                      onChange={(e) => update(currentQuestion.exercise_item_id, e.target.value)}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            ) : (
              <input
                className="assessment-text-input"
                value={answers[currentQuestion.exercise_item_id] || ""}
                onChange={(e) => update(currentQuestion.exercise_item_id, e.target.value)}
                placeholder="Nhập câu trả lời"
                autoFocus
              />
            )}
          </article>

          {/* Navigation buttons */}
          <div className="assessment-actions">
            <button
              type="button"
              className="sv-btn sv-btn-outline"
              disabled={currentQ === 0}
              onClick={() => setCurrentQ((prev) => Math.max(0, prev - 1))}
            >
              ← Câu trước
            </button>

            {currentQ < totalQ - 1 ? (
              <button
                type="button"
                className="sv-btn sv-btn-primary"
                onClick={() => setCurrentQ((prev) => Math.min(totalQ - 1, prev + 1))}
              >
                Câu tiếp →
              </button>
            ) : (
              <button
                type="submit"
                className="sv-btn sv-btn-primary"
                disabled={submitting}
              >
                {submitting ? "Đang chấm..." : `Nộp bài (${answered}/${totalQ})`}
              </button>
            )}
          </div>

          {error && <p className="sv-notice sv-notice-error">{error}</p>}
        </form>
      )}
    </div>
  );
}
