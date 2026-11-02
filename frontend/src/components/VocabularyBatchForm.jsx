import { useState } from "react";
import { generateBatchWithAI } from "../services/vocabularyService";

const TOPICS = [
  "general",
  "academic",
  "business",
  "technology",
  "science",
  "daily-life",
  "travel",
];

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

export default function VocabularyBatchForm({ onCreated }) {
  const [topic, setTopic] = useState("technology");
  const [level, setLevel] = useState("B1");
  const [count, setCount] = useState(10);
  const [wordsText, setWordsText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const manualWords = wordsText
    .split(/[\n,;]/)
    .map((w) => w.trim())
    .filter(Boolean);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await generateBatchWithAI({
        words: manualWords,
        topic,
        level,
        count: Number(count) || 10,
        save: true,
      });
      setResult(data);
      if (data.saved > 0) onCreated?.();
    } catch (err) {
      setError(err.response?.data?.detail || "Tạo hàng loạt thất bại");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2 style={{ marginBottom: "0.5rem" }}>✨ Tạo hàng loạt bằng AI</h2>
      <p className="muted" style={{ marginBottom: "1rem", fontSize: "0.85rem" }}>
        Để trống danh sách từ để AI tự gợi ý theo chủ đề và trình độ, hoặc nhập
        từng từ (mỗi dòng một từ) để AI bổ sung chi tiết.
      </p>

      <div style={{ display: "flex", gap: "1rem" }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label>Chủ đề</label>
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            {TOPICS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="form-group" style={{ flex: 1 }}>
          <label>Trình độ</label>
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((lv) => (
              <option key={lv}>{lv}</option>
            ))}
          </select>
        </div>
        <div className="form-group" style={{ width: "8rem" }}>
          <label>Số từ</label>
          <input
            type="number"
            min="1"
            max="30"
            value={count}
            onChange={(e) => setCount(e.target.value)}
          />
        </div>
      </div>

      <div className="form-group">
        <label>Danh sách từ (để trống = AI tự gợi ý)</label>
        <textarea
          value={wordsText}
          onChange={(e) => setWordsText(e.target.value)}
          rows={3}
          placeholder={"innovative\nresilient\nambiguous"}
        />
      </div>

      {manualWords.length > 0 && (
        <p className="muted" style={{ fontSize: "0.8rem", marginBottom: "0.75rem" }}>
          Sẽ xử lý {manualWords.length} từ: {manualWords.slice(0, 8).join(", ")}
          {manualWords.length > 8 ? "..." : ""}
        </p>
      )}

      {error && <p className="error">{error}</p>}

      <button className="btn" type="submit" disabled={loading}>
        {loading
          ? "Đang tạo... (có thể mất vài phút)"
          : `Tạo ${manualWords.length > 0 ? manualWords.length : count} từ`}
      </button>

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <div className="stats">
            <div className="stat-box">
              <div className="number">{result.requested}</div>
              <div className="label">Yêu cầu</div>
            </div>
            <div className="stat-box">
              <div className="number">{result.succeeded}</div>
              <div className="label">Thành công</div>
            </div>
            <div className="stat-box">
              <div className="number">{result.failed}</div>
              <div className="label">Lỗi</div>
            </div>
            <div className="stat-box">
              <div className="number">{result.saved}</div>
              <div className="label">Đã lưu</div>
            </div>
          </div>

          {result.failed > 0 && (
            <div style={{ marginTop: "0.75rem" }}>
              {result.items
                .filter((i) => !i.ok)
                .map((i) => (
                  <p key={i.word} className="error" style={{ fontSize: "0.8rem" }}>
                    {i.word}: {i.error}
                  </p>
                ))}
            </div>
          )}
        </div>
      )}
    </form>
  );
}
