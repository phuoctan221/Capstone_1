import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchLessons, fetchProgress } from "../services/lessonService";

export default function LearnPage() {
  const [lessons, setLessons] = useState([]);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [ls, pg] = await Promise.all([fetchLessons(), fetchProgress()]);
        setLessons(ls);
        setProgress(pg);
      } catch {
        setError("Không tải được lộ trình. Vui lòng thử lại.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <p className="muted">Đang tải lộ trình...</p>;
  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      {progress && (
        <div className="hero-card">
          <div className="hero-level">
            <div className="level-circle">Lv {progress.level}</div>
            <div>
              <h2>Trình độ của bạn</h2>
              <p className="muted">
                {progress.xp} XP · {progress.streak} ngày liên tiếp 🔥
              </p>
            </div>
          </div>
          <div className="hero-xp">
            <div className="xp-bar">
              <div
                className="xp-fill"
                style={{ width: `${Math.min(100, (progress.xp % 500) / 5)}%` }}
              />
            </div>
            <div className="hero-mini">
              <span>{progress.words_learned} từ đã học</span>
              <span>{progress.words_mastered} từ thành thạo</span>
              <span>{progress.lessons_completed} bài hoàn thành</span>
            </div>
          </div>
        </div>
      )}

      <h2 style={{ marginTop: "2rem" }}>Lộ trình học</h2>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Chọn một chủ đề để bắt đầu học từ mới và luyện tập.
      </p>

      <div className="lesson-path">
        {lessons.map((l, i) => (
          <Link to={`/lessons/${l.slug}`} key={l.slug} className="lesson-node">
            <div className={`lesson-badge ${l.completed ? "done" : ""}`}>
              {l.completed ? "✓" : i + 1}
            </div>
            <div className="lesson-info">
              <div className="lesson-title-row">
                <h3>{l.title}</h3>
                <span className="badge">{l.level}</span>
              </div>
              <p className="muted">{l.description}</p>
              <div className="lesson-progress">
                <div
                  className={`lesson-progress-fill ${l.completed ? "done" : ""}`}
                  style={{ width: `${l.progress_percent}%` }}
                />
              </div>
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                {l.learned_count}/{l.word_count} từ đã thuộc
                {l.completed && " · Đã hoàn thành"}
              </p>
            </div>
          </Link>
        ))}
        {lessons.length === 0 && (
          <p className="muted">Chưa có bài học nào. Hãy thêm từ vựng trước.</p>
        )}
      </div>
    </div>
  );
}
