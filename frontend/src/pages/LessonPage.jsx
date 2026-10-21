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
  { key: "quiz", label: "Trắc nghiệm", icon: "🎯", desc: "Chọn đáp án đúng" },
  { key: "typing", label: "Gõ từ", icon: "⌨️", desc: "Viết lại từ chính xác" },
  { key: "listening", label: "Nghe", icon: "🔊", desc: "Nghe và chọn từ" },
  { key: "flashcard", label: "Thẻ ghi nhớ", icon: "🃏", desc: "Lật thẻ để nhớ" },
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

  if (loading) return <p className="muted">Đang tải bài học...</p>;
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

  return (
    <div>
      <Link to="/learn" className="muted">
        ← Lộ trình
      </Link>
      <div className="card" style={{ marginTop: "1rem" }}>
        <div className="lesson-title-row">
          <h1>{lesson.title}</h1>
          <span className="badge">{lesson.level}</span>
        </div>
        <p className="muted">
          {lesson.word_count} từ vựng · Đã thuộc {lesson.learned_count}/
          {lesson.word_count}
        </p>

        <div className="mode-grid">
          {MODES.map((m) => (
            <button
              key={m.key}
              className="mode-card"
              onClick={() => setMode(m.key)}
            >
              <div className="mode-icon">{m.icon}</div>
              <div className="mode-label">{m.label}</div>
              <div className="mode-desc">{m.desc}</div>
            </button>
          ))}
        </div>

        <Link
          to={`/lessons/${lessonId}/quiz`}
          className="btn"
          style={{ marginTop: "1.5rem", display: "inline-block" }}
        >
          📝 Làm bài kiểm tra cuối bài
        </Link>
      </div>

      <h2 style={{ marginTop: "2rem" }}>Danh sách từ vựng</h2>
      <div className="word-list">
        {lesson.words.map((w) => (
          <div className="word-row" key={w.id}>
            <div>
              <div className="word-row-main">
                <strong>{w.word}</strong>
                <span className="muted">/{w.phonetic}/</span>
              </div>
              <div className="muted">{w.meaning}</div>
              {w.example && (
                <div className="word-example muted">"{w.example}"</div>
              )}
            </div>
            <button
              className="speak-btn"
              onClick={() => speak(w.word)}
              title="Phát âm"
            >
              🔊
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function StudySession({ lesson, mode, onExit }) {
  const words = lesson.words;
  const queue = useMemo(() => {
    let list = shuffle(words);
    if (mode === "flashcard") list = shuffle(words);
    return list;
  }, [words, mode]);

  const [index, setIndex] = useState(0);
  const [feedback, setFeedback] = useState(null);
  const [input, setInput] = useState("");
  const [flipped, setFlipped] = useState(false);
  const [sessionXp, setSessionXp] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);

  const current = queue[index];
  const choices = useMemo(() => {
    if (!current) return [];
    const others = shuffle(words.filter((w) => w.id !== current.id))
      .slice(0, 3)
      .map((w) => w.meaning);
    return shuffle([current.meaning, ...others]);
  }, [current, words]);

  useEffect(() => {
    if (mode === "listening" && current) speak(current.word);
  }, [mode, current, index]);

  const answer = async (isCorrect) => {
    setFeedback(isCorrect ? "correct" : "wrong");
    if (isCorrect) setCorrectCount((c) => c + 1);
    try {
      const res = await submitStudyAnswer(current.id, "", isCorrect);
      setSessionXp((x) => x + res.xp_gained);
    } catch {}
  };

  const next = () => {
    setFeedback(null);
    setInput("");
    setFlipped(false);
    if (index + 1 >= queue.length) {
      onExit();
    } else {
      setIndex(index + 1);
    }
  };

  if (!current) return null;
  const modeInfo = MODES.find((m) => m.key === mode);

  return (
    <div>
      <div className="study-header">
        <button className="btn btn-outline" onClick={onExit}>
          ← Thoát
        </button>
        <div className="muted">
          {modeInfo.icon} {modeInfo.label} · {index + 1}/{queue.length} · +
          {sessionXp} XP
        </div>
      </div>

      <div className="card study-card">
        {mode === "quiz" && (
          <>
            <p className="study-question">
              "{current.word}" có nghĩa là gì?
            </p>
            <div className="choice-grid">
              {choices.map((c, i) => (
                <button
                  key={i}
                  className={`choice ${
                    feedback && c === current.meaning ? "right" : ""
                  } ${
                    feedback === "wrong" && c !== current.meaning ? "dim" : ""
                  }`}
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
            <p className="study-question">
              Nghĩa: "{current.meaning}"
            </p>
            <p className="muted">Viết lại từ tiếng Anh ({current.phonetic})</p>
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
                className="btn"
                style={{ marginTop: "1rem" }}
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
              <p className="error" style={{ marginTop: "1rem" }}>
                Đáp án đúng: <strong>{current.word}</strong>
              </p>
            )}
          </>
        )}

        {mode === "listening" && (
          <>
            <p className="study-question">🔊 Nghe và chọn từ đúng</p>
            <button className="btn btn-outline" onClick={() => speak(current.word)}>
              Nghe lại
            </button>
            <div className="choice-grid" style={{ marginTop: "1.5rem" }}>
              {shuffle([current, ...words.filter((w) => w.id !== current.id).slice(0, 3)]).map(
                (w, i) => (
                  <button
                    key={i}
                    className={`choice ${
                      feedback && w.id === current.id ? "right" : ""
                    } ${
                      feedback === "wrong" && w.id !== current.id ? "dim" : ""
                    }`}
                    disabled={!!feedback}
                    onClick={() => answer(w.id === current.id)}
                  >
                    {w.word}
                  </button>
                )
              )}
            </div>
          </>
        )}

        {mode === "flashcard" && (
          <>
            <div
              className="flashcard-big"
              onClick={() => setFlipped((f) => !f)}
            >
              <div className="word">{current.word}</div>
              <div className="muted">/{current.phonetic}/</div>
              {flipped ? (
                <div className="meaning" style={{ marginTop: "1rem" }}>
                  <p>{current.meaning}</p>
                  {current.example && (
                    <p className="muted word-example">"{current.example}"</p>
                  )}
                </div>
              ) : (
                <p className="muted" style={{ marginTop: "1rem" }}>
                  Nhấn để xem nghĩa
                </p>
              )}
            </div>
            <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
              <button
                className="speak-btn"
                onClick={() => speak(current.word)}
              >
                🔊
              </button>
              <button
                className="btn btn-outline"
                style={{ flex: 1 }}
                onClick={() => setFlipped(true)}
              >
                Xem nghĩa
              </button>
            </div>
            {flipped && (
              <div className="flashcard-actions">
                <button
                  className="btn btn-danger"
                  style={{ flex: 1 }}
                  onClick={() => answer(false)}
                >
                  Chưa nhớ
                </button>
                <button
                  className="btn"
                  style={{ flex: 1, background: "var(--success)" }}
                  onClick={() => answer(true)}
                >
                  Đã nhớ
                </button>
              </div>
            )}
          </>
        )}

        {feedback && (
          <div className="study-footer">
            <span
              className={feedback === "correct" ? "feedback-ok" : "feedback-no"}
            >
              {feedback === "correct" ? "✓ Chính xác!" : "✗ Sai rồi"}
            </span>
            <button className="btn" onClick={next}>
              Tiếp tục →
            </button>
          </div>
        )}
      </div>

      <div className="study-progress">
        <div
          className="study-progress-fill"
          style={{ width: `${((index + 1) / queue.length) * 100}%` }}
        />
      </div>
    </div>
  );
}
