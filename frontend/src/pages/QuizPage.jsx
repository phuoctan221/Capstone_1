import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { fetchQuiz, submitQuiz, fetchLesson } from "../services/lessonService";

export default function QuizPage() {
  const { lessonId } = useParams();
  const navigate = useNavigate();
  const [lesson, setLesson] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [index, setIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [les, quiz] = await Promise.all([
          fetchLesson(lessonId),
          fetchQuiz(lessonId, 10),
        ]);
        setLesson(les);
        setQuestions(quiz.questions);
      } catch {
        navigate(`/lessons/${lessonId}`);
      }
      setLoading(false);
    })();
  }, [lessonId, navigate]);

  const choose = (option) => {
    setAnswers({ ...answers, [index]: option });
  };

  const finish = async () => {
    setSubmitting(true);
    const results = questions.map((q, i) => ({
      vocabulary_id: q.vocabulary_id,
      correct: answers[i] === q.answer,
      correct_answer: q.answer,
      user_answer: answers[i] || "",
    }));
    try {
      const res = await submitQuiz(lessonId, results);
      setResult(res);
    } catch {
      setResult({ error: true });
    }
    setSubmitting(false);
  };

  if (loading) return <p className="muted">Đang chuẩn bị bài kiểm tra...</p>;

  if (result) {
    if (result.error)
      return <p className="error">Nộp bài thất bại, vui lòng thử lại.</p>;

    return (
      <div className="card result-card">
        <div className={`result-badge ${result.passed ? "pass" : "fail"}`}>
          {result.passed ? "🎉 Đạt!" : "Cố lên!"}
        </div>
        <h1>
          {result.correct}/{result.total} câu đúng
        </h1>
        <p className="result-percent">{result.percent}%</p>

        <div className="result-stats">
          <div className="result-stat">
            <div className="number">+{result.xp_gained}</div>
            <div className="label">XP nhận được</div>
          </div>
          <div className="result-stat">
            <div className="number">Lv {result.new_level}</div>
            <div className="label">Cấp độ</div>
          </div>
          <div className="result-stat">
            <div className="number">{result.streak}🔥</div>
            <div className="label">Chuỗi ngày</div>
          </div>
        </div>

        <div className="result-actions">
          <Link to={`/lessons/${lessonId}`} className="btn">
            Học tiếp
          </Link>
          <Link to="/learn" className="btn btn-outline">
            Về lộ trình
          </Link>
        </div>
      </div>
    );
  }

  const q = questions[index];
  const done = index + 1 >= questions.length;
  const answeredCount = Object.keys(answers).length;

  return (
    <div>
      <div className="study-header">
        <Link to={`/lessons/${lessonId}`} className="btn btn-outline">
          ← Thoát
        </Link>
        <div className="muted">
          Kiểm tra: {lesson?.title} · {index + 1}/{questions.length}
        </div>
      </div>

      <div className="card study-card">
        <p className="study-question">{q.question}</p>
        <div className="choice-grid">
          {q.options.map((opt, i) => (
            <button
              key={i}
              className={`choice ${answers[index] === opt ? "selected" : ""}`}
              onClick={() => choose(opt)}
            >
              {opt}
            </button>
          ))}
        </div>

        <div className="study-footer">
          {index > 0 && (
            <button
              className="btn btn-outline"
              onClick={() => setIndex(index - 1)}
            >
              ← Trước
            </button>
          )}
          {!done ? (
            <button
              className="btn"
              disabled={answers[index] === undefined}
              onClick={() => setIndex(index + 1)}
            >
              Câu tiếp →
            </button>
          ) : (
            <button
              className="btn"
              disabled={answeredCount < questions.length || submitting}
              onClick={finish}
            >
              {submitting ? "Đang nộp..." : "Nộp bài"}
            </button>
          )}
        </div>
      </div>

      <div className="study-progress">
        <div
          className="study-progress-fill"
          style={{ width: `${((index + 1) / questions.length) * 100}%` }}
        />
      </div>
      <p className="muted" style={{ textAlign: "center", marginTop: "0.5rem" }}>
        Đã trả lời {answeredCount}/{questions.length} câu
      </p>
    </div>
  );
}
