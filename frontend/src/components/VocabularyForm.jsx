import { useState } from "react";
import { generateWithAI, createVocabulary } from "../services/vocabularyService";

const EMPTY = {
  word: "",
  phonetic: "",
  part_of_speech: "",
  meaning: "",
  example: "",
  synonyms: [],
  antonyms: [],
  topic: "general",
  level: "A1",
};

export default function VocabularyForm({ onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleAI = async () => {
    if (!form.word.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await generateWithAI(form.word.trim());
      setForm({
        word: data.word,
        phonetic: data.phonetic,
        part_of_speech: data.part_of_speech,
        meaning: data.meaning,
        example: data.example,
        synonyms: data.synonyms || [],
        antonyms: data.antonyms || [],
        topic: data.topic || "general",
        level: data.level || "A1",
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Sinh từ vựng AI thất bại");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const created = await createVocabulary(form);
      setForm(EMPTY);
      onCreated?.(created);
    } catch (err) {
      setError(err.response?.data?.detail || "Lưu thất bại");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2 style={{ marginBottom: "1rem" }}>Thêm từ vựng</h2>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label>Từ</label>
          <input name="word" value={form.word} onChange={handleChange} required />
        </div>
        <button
          type="button"
          className="btn btn-outline"
          onClick={handleAI}
          disabled={loading}
          style={{ alignSelf: "flex-end" }}
        >
          {loading ? "..." : "✨ AI gợi ý"}
        </button>
      </div>
      <div className="form-group">
        <label>Phiên âm</label>
        <input name="phonetic" value={form.phonetic} onChange={handleChange} />
      </div>
      <div className="form-group">
        <label>Nghĩa</label>
        <textarea name="meaning" value={form.meaning} onChange={handleChange} rows={2} required />
      </div>
      <div className="form-group">
        <label>Ví dụ</label>
        <textarea name="example" value={form.example} onChange={handleChange} rows={2} />
      </div>
      <div style={{ display: "flex", gap: "1rem" }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label>Trình độ</label>
          <select name="level" value={form.level} onChange={handleChange}>
            {["A1", "A2", "B1", "B2", "C1", "C2"].map((lv) => (
              <option key={lv}>{lv}</option>
            ))}
          </select>
        </div>
        <div className="form-group" style={{ flex: 1 }}>
          <label>Chủ đề</label>
          <input name="topic" value={form.topic} onChange={handleChange} />
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" type="submit" disabled={loading}>
        Lưu từ vựng
      </button>
    </form>
  );
}
