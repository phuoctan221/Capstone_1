import { useEffect, useRef, useState } from "react";
import api from "../services/api";

export default function CustomSpeakingWords({ words, onChange, disabled }) {
  const [input, setInput] = useState("");
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(null);
  const sequence = useRef(0);
  useEffect(() => () => { sequence.current++; request.current?.abort(); }, []);

  function edit(value) {
    sequence.current++;
    request.current?.abort();
    setInput(value); setResult(null); setError(""); setChecking(false);
  }
  async function check(event) {
    event.preventDefault();
    if (!input.trim() || disabled || checking) return;
    const word = input.trim().toLowerCase().replace(/’/g, "'");
    if (!/^[a-z]+(?:['-][a-z]+)*$/.test(word)) {
      setError("Nhập một từ tiếng Anh mỗi lần, không kèm số hoặc ký tự đặc biệt."); return;
    }
    const current = ++sequence.current;
    request.current?.abort();
    request.current = new AbortController();
    setChecking(true); setResult(null); setError("");
    try {
      const { data } = await api.post("/speaking/check-word", { word }, { signal: request.current.signal, timeout: 30000 });
      if (sequence.current === current) setResult(data);
    } catch (e) {
      if (sequence.current === current) setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Chưa kiểm tra được từ. Bạn hãy thử lại nhé.");
    } finally { if (sequence.current === current) setChecking(false); }
  }
  function add(word) {
    if (disabled || words.length >= 20) return;
    if (words.includes(word)) { setError("Từ này đã có trong danh sách."); return; }
    onChange([...words, word]);
    edit("");
  }
  return <div className="custom-speaking-words">
    <p>Nhập từng từ muốn luyện. Từ cần được xác nhận trước khi thêm vào bài.</p>
    <form onSubmit={check}>
      <label htmlFor="custom-speaking-word">Từ tiếng Anh</label>
      <div className="speaking-search">
        <input id="custom-speaking-word" value={input} onChange={e => edit(e.target.value)} maxLength={80} disabled={disabled || words.length >= 20} placeholder="Ví dụ: invoice" autoComplete="off" autoCapitalize="none" spellCheck={false} />
        <button type="submit" className="btn" disabled={disabled || checking || !input.trim() || words.length >= 20}>{checking ? "Đang kiểm tra…" : "Kiểm tra từ"}</button>
      </div>
    </form>
    {error && <p role="alert" className="speaking-error">{error}</p>}
    {result && <div aria-live="polite">
      {result.valid ? <div className="speaking-word-feedback">
        <strong>✓ “{result.word}” là từ hợp lệ.</strong>
        {result.definition && <p>Nghĩa tiếng Anh: {result.definition}</p>}
        <button type="button" className="btn" disabled={disabled || words.length >= 20 || words.includes(result.word)} onClick={() => add(result.word)}>Thêm “{result.word}”</button>
      </div> : <>
        <p>Chưa tìm thấy “{result.word}” trong từ điển. Hãy kiểm tra cách viết.</p>
        {result.suggestions?.length > 0 ? <><p>Có phải bạn muốn viết:</p><div className="speaking-actions">{result.suggestions.map(s => <button key={s.word} type="button" className="btn" disabled={disabled || words.length >= 20 || words.includes(s.word)} title={s.definition} onClick={() => add(s.word)}>Thêm “{s.word}”</button>)}</div></>
          : <p>Chưa có từ gần đúng để gợi ý. Bạn thử cách viết khác nhé.</p>}
      </>}
    </div>}
    <h3>Từ đã chọn ({words.length}/20)</h3>
    {words.length ? <ul className="custom-speaking-list">{words.map(word => <li key={word}><strong>{word}</strong><button type="button" className="btn" disabled={disabled} aria-label={`Bỏ từ ${word}`} onClick={() => onChange(words.filter(w => w !== word))}>Bỏ</button></li>)}</ul> : <p>Chưa có từ được chọn.</p>}
    <p>Từ tự nhập dùng cho bài luyện nói này, chưa được tính vào tiến độ từ đã học.</p>
  </div>;
}
