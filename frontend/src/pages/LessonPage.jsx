import { useEffect, useState, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { fetchLesson, submitStudyAnswer } from "../services/lessonService";

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const MODES = [
  { key: "quiz", label: "Trắc nghiệm", desc: "Chọn đáp án đúng" },
  { key: "typing", label: "Gõ từ", desc: "Viết lại từ chính xác" },
  { key: "listening", label: "Nghe", desc: "Nghe và chọn từ" },
  { key: "flashcard", label: "Thẻ ghi nhớ", desc: "Lật thẻ để nhớ" },
];

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = 0.9;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export default function LessonPage() {
  const { lessonId } = useParams();
  const navigate = useNavigate();
  const [lesson, setLesson] = useState(null);
  const [mode, setMode] = useState(null); // null = overview, else study
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setLesson(await fetchLesson(lessonId));
      } catch {
        navigate("/learn");
      }
      setLoading(false);
    })();
  }, [lessonId, navigate]);

  if (loading) {
    return (
      <div className="lesson-loading">
        <span className="lesson-spinner" />
        <p className="muted">Đang tải bài học...</p>
      </div>
    );
  }
  if (!lesson) return null;

  if (mode) {
    return (
      <StudySession
        lesson={lesson}
        mode={mode}
        onExit={() => setMode(null)}
      />
    );
  }

  const total = lesson.word_count || lesson.words.length;
  const learned = lesson.learned_count || 0;
  const percent = total ? Math.round((learned / total) * 100) : 0;

  return (
    <div className="lesson-page">
      <div className="lesson-topbar">
        <Link to="/learn" className="lesson-back">
          ← Lộ trình
        </Link>
        <span className="lesson-level-pill">{lesson.level}</span>
      </div>

      <header className="lesson-hero">
        <div className="lesson-hero-head">
          <div className="lesson-hero-title">
            <h1>{lesson.title}</h1>
            <p className="lesson-hero-sub">
              {total} từ vựng · Đã thuộc {learned}/{total}
            </p>
          </div>
        </div>

        <div className="lesson-hero-progress">
          <div className="lesson-hero-progress-head">
            <span>Tiến độ bài học</span>
            <strong>{percent}%</strong>
          </div>
          <div className="lesson-hero-bar">
            <div
              className="lesson-hero-bar-fill"
              style={{ width: `${percent}%` }}
            />
          </div>
          <div className="lesson-hero-stats">
            <div>
              <strong>{learned}</strong>
              <span>Đã thuộc</span>
            </div>
            <div>
              <strong>{Math.max(total - learned, 0)}</strong>
              <span>Còn lại</span>
            </div>
            <div>
              <strong>{total}</strong>
              <span>Tổng số</span>
            </div>
          </div>
        </div>
      </header>

      <section className="lesson-section">
        <div className="lesson-section-head">
          <h2>Chọn cách học</h2>
          <p className="muted">Luyện tập theo nhiều hình thức khác nhau</p>
        </div>
        <div className="mode-grid">
          {MODES.map((m) => (
            <button
              key={m.key}
              className="mode-card"
              onClick={() => setMode(m.key)}
            >
              <span className="mode-label">{m.label}</span>
              <span className="mode-desc">{m.desc}</span>
              <span className="mode-arrow">Bắt đầu →</span>
            </button>
          ))}
        </div>
      </section>

      <Link to={`/lessons/${lessonId}/quiz`} className="lesson-quiz-cta">
        <span className="lesson-quiz-text">
          <strong>Bài kiểm tra cuối bài</strong>
          <span>Kiểm tra lại toàn bộ từ vựng đã học</span>
        </span>
        <span className="lesson-quiz-arrow">→</span>
      </Link>

      <section className="lesson-section">
        <div className="lesson-section-head">
          <h2>Danh sách từ vựng</h2>
          <span className="badge">{lesson.words.length} từ</span>
        </div>
        <div className="word-list">
          {lesson.words.map((w, i) => (
            <div className="word-row" key={w.id}>
              <span className="word-index">{i + 1}</span>
              <div className="word-body">
                <div className="word-row-main">
                  <strong>{w.word}</strong>
                  {w.phonetic && (
                    <span className="word-phonetic">/{w.phonetic}/</span>
                  )}
                </div>
                <div className="word-meaning">{w.meaning}</div>
                {w.example && (
                  <div className="word-example">“{w.example}”</div>
                )}
              </div>
              <button
                className="speak-btn"
                onClick={() => speak(w.word)}
                title="Phát âm"
                aria-label={`Phát âm ${w.word}`}
              >
                Phát âm
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function StudySession({ lesson, mode, onExit }) {
  const words = lesson.words;
  const queue = useMemo(() => shuffle(words), [words, mode]);

  const [index, setIndex] = useState(0);
  const [feedback, setFeedback] = useState(null);
  const [input, setInput] = useState("");
  const [flipped, setFlipped] = useState(false);
  const [sessionXp, setSessionXp] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [finished, setFinished] = useState(false);

  const current = queue[index];
  const modeInfo = MODES.find((m) => m.key === mode);

  const choices = useMemo(() => {
    if (!current) return [];
    const others = shuffle(words.filter((w) => w.id !== current.id))
      .slice(0, 3)
      .map((w) => w.meaning);
    return shuffle([current.meaning, ...others]);
  }, [current, words]);

  const listeningChoices = useMemo(() => {
    if (!current) return [];
    return shuffle([
      current,
      ...shuffle(words.filter((w) => w.id !== current.id)).slice(0, 3),
    ]);
  }, [current, words]);

  useEffect(() => {
    if (mode === "listening" && current && !finished) speak(current.word);
  }, [mode, current, index, finished]);

  const answer = async (isCorrect) => {
    if (feedback) return;
    setFeedback(isCorrect ? "correct" : "wrong");
    if (isCorrect) setCorrectCount((c) => c + 1);
    try {
      const res = await submitStudyAnswer(current.id, "", isCorrect);
      setSessionXp((x) => x + res.xp_gained);
    } catch { }
  };

  const next = () => {
    setFeedback(null);
    setInput("");
    setFlipped(false);
    if (index + 1 >= queue.length) {
      setFinished(true);
    } else {
      setIndex(index + 1);
    }
  };

  const restart = () => {
    setIndex(0);
    setFeedback(null);
    setInput("");
    setFlipped(false);
    setSessionXp(0);
    setCorrectCount(0);
    setFinished(false);
  };

  if (!current) return null;

  const progressPercent = Math.round(((index + 1) / queue.length) * 100);

  if (finished) {
    const accuracy = Math.round((correctCount / queue.length) * 100);
    return (
      <div className="lesson-page">
        <div className="study-complete">
          <h1>
            {accuracy >= 80
              ? "Tuyệt vời!"
              : accuracy >= 50
                ? "Cố lên nhé!"
                : "Tiếp tục luyện tập!"}
          </h1>
          <p className="muted">
            Bạn đã hoàn thành phiên {modeInfo.label.toLowerCase()}.
          </p>
          <div className="study-complete-stats">
            <div>
              <strong>{correctCount}/{queue.length}</strong>
              <span>Câu đúng</span>
            </div>
            <div>
              <strong>{accuracy}%</strong>
              <span>Độ chính xác</span>
            </div>
            <div>
              <strong>+{sessionXp}</strong>
              <span>XP nhận được</span>
            </div>
          </div>
          <div className="study-complete-actions">
            <button className="btn btn-outline" onClick={restart}>
              Học lại
            </button>
            <button className="btn" onClick={onExit}>
              Hoàn tất
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="lesson-page study-session">
      <div className="study-topbar">
        <button className="lesson-back" onClick={onExit}>
          ← Thoát
        </button>
        <div className="study-meta">
          <span className="study-mode-chip">{modeInfo.label}</span>
          <span className="study-xp-chip">+{sessionXp} XP</span>
        </div>
      </div>

      <div className="study-progress-wrap">
        <div className="study-progress-head">
          <span>
            Câu {index + 1}/{queue.length}
          </span>
          <span>{progressPercent}%</span>
        </div>
        <div className="study-progress">
          <div
            className="study-progress-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      <div className={`card study-card study-card-${mode}`}>
        {mode === "quiz" && (
          <>
            <p className="study-eyebrow">Chọn nghĩa đúng</p>
            <p className="study-question">
              “{current.word}” có nghĩa là gì?
            </p>
            <div className="choice-grid">
              {choices.map((c, i) => (
                <button
                  key={i}
                  className={`choice ${
                    feedback && c === current.meaning ? "right" : ""
                  } ${feedback === "wrong" && c !== current.meaning ? "dim" : ""}`}
                  disabled={!!feedback}
                  onClick={() => answer(c === current.meaning)}
                >
                  {c}
                </button>
              ))}
            </div>
          </>
        )}

        {mode === "typing" && (
          <>
            <p className="study-eyebrow">Viết lại từ tiếng Anh</p>
            <p className="study-question">Nghĩa: “{current.meaning}”</p>
            <p className="muted study-hint">
              Gợi ý phiên âm: /{current.phonetic}/
            </p>
            <input
              className="typing-input"
              value={input}
              autoFocus
              disabled={!!feedback}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !feedback && input.trim()) {
                  answer(
                    input.trim().toLowerCase() === current.word.toLowerCase()
                  );
                }
              }}
              placeholder="Gõ từ..."
            />
            {!feedback && (
              <button
                className="btn study-submit"
                disabled={!input.trim()}
                onClick={() =>
                  answer(
                    input.trim().toLowerCase() === current.word.toLowerCase()
                  )
                }
              >
                Kiểm tra
              </button>
            )}
            {feedback === "wrong" && (
              <p className="study-answer-reveal">
                Đáp án đúng: <strong>{current.word}</strong>
              </p>
            )}
          </>
        )}

        {mode === "listening" && (
          <>
            <p className="study-eyebrow">Nghe và chọn từ đúng</p>
            <div className="listening-box">
              <button
                className="listen-big-btn"
                onClick={() => speak(current.word)}
                aria-label="Nghe lại"
              >
                Nghe
              </button>
              <p className="muted">Nhấn để nghe lại</p>
            </div>
            <div className="choice-grid">
              {listeningChoices.map((w) => (
                <button
                  key={w.id}
                  className={`choice ${
                    feedback && w.id === current.id ? "right" : ""
                  } ${feedback === "wrong" && w.id !== current.id ? "dim" : ""}`}
                  disabled={!!feedback}
                  onClick={() => answer(w.id === current.id)}
                >
                  {w.word}
                </button>
              ))}
            </div>
          </>
        )}

        {mode === "flashcard" && (
          <>
            <div
              className={`flashcard-big ${flipped ? "is-flipped" : ""}`}
              onClick={() => setFlipped((f) => !f)}
            >
              {!flipped ? (
                <div className="flashcard-face">
                  <div className="word">{current.word}</div>
                  <div className="word-phonetic">/{current.phonetic}/</div>
                  <p className="muted flashcard-tip">Nhấn để xem nghĩa</p>
                </div>
              ) : (
                <div className="flashcard-face">
                  <div className="meaning">{current.meaning}</div>
                  {current.example && (
                    <p className="word-example">“{current.example}”</p>
                  )}
                </div>
              )}
            </div>
            <div className="flashcard-toolbar">
              <button
                className="speak-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  speak(current.word);
                }}
                aria-label="Phát âm"
              >
                Nghe
              </button>
              {!flipped ? (
                <button
                  className="btn btn-outline flashcard-flip-btn"
                  onClick={() => setFlipped(true)}
                >
                  Xem nghĩa
                </button>
              ) : (
                <div className="flashcard-actions">
                  <button
                    className="btn btn-danger"
                    onClick={() => answer(false)}
                  >
                    Chưa nhớ
                  </button>
                  <button className="btn btn-success" onClick={() => answer(true)}>
                    Đã nhớ
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {feedback && (
          <div
            className={`study-footer ${
              feedback === "correct" ? "is-correct" : "is-wrong"
            }`}
          >
            <span
              className={feedback === "correct" ? "feedback-ok" : "feedback-no"}
            >
              {feedback === "correct" ? "✓ Chính xác!" : "✗ Sai rồi"}
            </span>
            <button className="btn" onClick={next}>
              {index + 1 >= queue.length ? "Hoàn thành →" : "Tiếp tục →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
