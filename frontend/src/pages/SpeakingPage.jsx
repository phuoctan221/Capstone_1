import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../services/api";
import PronunciationPreview from "../components/PronunciationPreview";
import SpeakingFeedback from "../components/SpeakingFeedback";
import CustomSpeakingWords from "../components/CustomSpeakingWords";
import "./SpeakingPage.css";

function errorText(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : "Không thực hiện được. Kiểm tra dữ liệu hoặc kết nối và thử lại.";
}

const searchText = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase().trim();

export default function SpeakingPage() {
  const [params, setParams] = useSearchParams();
  const exerciseId = params.get("exercise");
  const [words, setWords] = useState([]);
  const [selected, setSelected] = useState([]);
  const [customWords, setCustomWords] = useState([]);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("auto");
  const [exercise, setExercise] = useState(null);
  const [index, setIndex] = useState(0);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const recorder = useRef(null);
  const stream = useRef(null);
  const timer = useRef(null);
  const mounted = useRef(true);
  const operation = useRef(0);
  const busy = ["requesting", "recording", "scoring", "loading"].includes(status);
  const maxSeconds = exercise?.assessment_provider === "chivox" && exercise?.items[index]?.text.trim().split(/\s+/).length === 1 ? 18 : 30;

  useEffect(() => {
    mounted.current = true;
    api.get("/speaking/words").then(r => { if (mounted.current) setWords(r.data); }).catch(e => { if (mounted.current) setError(errorText(e)); });
    return () => {
      mounted.current = false;
      operation.current++;
      clearTimeout(timer.current);
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    let active = true;
    operation.current++;
    clearTimeout(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach(t => t.stop());
    setExercise(null);
    setIndex(0);
    setStatus(exerciseId ? "loading" : "idle");
    if (exerciseId) api.get(`/speaking/exercises/${exerciseId}`).then(r => {
      if (active) { setExercise(r.data); setStatus("idle"); }
    }).catch(e => { if (active) { setError(errorText(e)); setStatus("idle"); } });
    return () => { active = false; };
  }, [exerciseId]);

  async function create() {
    setStatus("loading"); setError("");
    try {
      const r = await api.post("/speaking/exercises", {
        auto_select: mode === "auto",
        vocabulary_ids: mode === "learned" ? selected : [],
        custom_words: mode === "custom" ? customWords : [],
      });
      setParams({ exercise: r.data.id });
    } catch (e) { setError(errorText(e)); }
    finally { setStatus("idle"); }
  }

  function stop() {
    clearTimeout(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  async function start() {
    window.speechSynthesis?.cancel();
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("Trình duyệt chưa hỗ trợ thu âm. Hãy mở bằng Chrome/Edge/Safari qua HTTPS hoặc localhost."); return;
    }
    const currentOperation = ++operation.current;
    setStatus("requesting");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current || currentOperation !== operation.current) { media.getTracks().forEach(t => t.stop()); return; }
      stream.current = media;
      const mime = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find(t => MediaRecorder.isTypeSupported(t));
      if (!mime) throw new Error("format");
      const instance = new MediaRecorder(media, { mimeType: mime });
      recorder.current = instance;
      const chunks = [];
      instance.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      instance.onstop = async () => {
        media.getTracks().forEach(t => t.stop());
        clearTimeout(timer.current);
        if (!mounted.current || currentOperation !== operation.current) return;
        setStatus("scoring");
        try {
          const blob = new Blob(chunks, { type: mime });
          const r = await api.post(`/speaking/exercises/${exercise.id}/items/${index}/score`, blob, {
            headers: { "Content-Type": mime }, timeout: 240000,
          });
          if (mounted.current && currentOperation === operation.current) setExercise(prev => ({ ...prev, results: { ...prev.results, [index]: r.data } }));
        } catch (e) { if (mounted.current && currentOperation === operation.current) setError(errorText(e)); }
        finally { if (mounted.current && currentOperation === operation.current) setStatus("idle"); }
      };
      instance.onerror = () => {
        operation.current++;
        clearTimeout(timer.current);
        media.getTracks().forEach(t => t.stop());
        if (mounted.current) { setStatus("idle"); setError("Thu âm bị gián đoạn. Hãy thử lại."); }
      };
      instance.start(); setStatus("recording");
      timer.current = setTimeout(stop, maxSeconds * 1000);
    } catch (e) {
      stream.current?.getTracks().forEach(t => t.stop());
      if (mounted.current && currentOperation === operation.current) {
        setStatus("idle"); setError(e.name === "NotAllowedError" ? "Hãy cho phép sử dụng micro để luyện nói." : "Không mở được micro hoặc định dạng thu âm chưa hỗ trợ.");
      }
    }
  }

  const result = exercise?.results?.[index];
  const filteredWords = words.filter(w => searchText(`${w.word} ${w.meaning}`).includes(searchText(query)));
  return <section className="speaking-page">
    <h1>Luyện nói</h1>
    <p>Luyện phát âm từ đã học hoặc thêm từ bạn muốn luyện.</p>
    {error && <p role="alert" className="speaking-error">{error}</p>}
    {!exercise ? <div className="speaking-card">
      <h2>1. Chọn nội dung luyện tập</h2>
      <label>Nguồn từ vựng <select value={mode} onChange={e => setMode(e.target.value)} disabled={busy}>
        <option value="auto">Tự động chọn 20 từ đã học</option><option value="learned">Tự chọn từ đã học</option><option value="custom">Nhập từ muốn luyện</option>
      </select></label>
      {mode === "learned" && <fieldset disabled={busy}><legend>Từ đã học</legend>
        <p>Các từ bạn đã luyện tập hoặc ôn tập, theo tiến độ học hiện tại.</p>
        <label htmlFor="learned-word-search">Tìm từ đã học</label>
        <div className="speaking-search">
          <input id="learned-word-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Nhập từ tiếng Anh hoặc nghĩa tiếng Việt…" />
          {query && <button type="button" className="btn" onClick={() => setQuery("")}>Xóa tìm kiếm</button>}
        </div>
        <p role="status">{filteredWords.length}/{words.length} từ · Đã chọn {selected.length}/20</p>
        {!words.length && <p>Bạn chưa có từ đã học. Hãy học thêm từ rồi quay lại nhé.</p>}
        {words.length > 0 && !filteredWords.length && <p>Không tìm thấy từ phù hợp. Hãy thử từ khóa khác.</p>}
        <div className="speaking-words">{filteredWords.map(w => <label key={w.id}>
          <input type="checkbox" checked={selected.includes(w.id)} disabled={selected.length >= 20 && !selected.includes(w.id)} onChange={e => setSelected(prev => e.target.checked ? [...prev, w.id] : prev.filter(id => id !== w.id))} />
          <strong>{w.word}</strong> {w.meaning}
        </label>)}</div>
      </fieldset>}
      {mode === "custom" && <CustomSpeakingWords words={customWords} onChange={setCustomWords} disabled={busy} />}
      {mode === "auto" ? <p>Bài luyện sẽ chọn 20 từ trong số những từ bạn đã học, ưu tiên từ cần ôn thêm. Nếu chưa đủ 20 từ, bạn sẽ luyện với số từ hiện có.</p> : mode === "learned" && <>
        <h3>Danh sách xem trước</h3>
        <p>{words.filter(w => selected.includes(w.id)).map(w => w.word).join(" · ") || "Chưa chọn từ."}</p>
        <p>Chọn tối đa 20 từ cho mỗi bài luyện.</p>
      </>}
      {!words.length && mode === "auto" && <p>Hãy học một số từ trước khi tạo bài luyện nói.</p>}
      <button className="btn btn-primary" disabled={busy || (mode === "custom" ? !customWords.length : !words.length) || (mode === "learned" && (!selected.length || selected.length > 20))} onClick={create}>{busy ? "Đang chuẩn bị bài luyện…" : mode === "auto" ? "Chọn từ và bắt đầu luyện" : "Tạo bài luyện nói"}</button>
    </div> : <div className="speaking-card">
      <p>Mục {index + 1}/{exercise.items.length} · {exercise.items[index].source === "custom" ? "Từ tự chọn" : "Từ đã học"}</p>
      <h2 className="speaking-target">{exercise.items[index].text}</h2>
      <PronunciationPreview text={exercise.items[index].text} disabled={busy} />
      <p>Đọc đúng nội dung trên. Bản ghi tự kết thúc sau {maxSeconds} giây.</p>
      <p>Bản thu âm sẽ được phân tích để đánh giá phát âm của bạn.</p>
      <div className="speaking-actions">
        {status === "recording" ? <button className="btn btn-primary" onClick={stop}>Kết thúc và đánh giá</button> : <button className="btn btn-primary" disabled={busy} onClick={start}>{status === "scoring" ? "Đang đánh giá…" : status === "requesting" ? "Đang mở micro…" : result ? "Luyện lại" : "Bắt đầu nói"}</button>}
        <button className="btn" disabled={busy || index === 0} onClick={() => setIndex(i => i - 1)}>Từ trước</button>
        <button className="btn" disabled={busy || index === exercise.items.length - 1} onClick={() => setIndex(i => i + 1)}>Từ tiếp theo</button>
        <button className="btn" disabled={busy} onClick={() => setParams({})}>Chọn bài mới</button>
      </div>
      {status === "recording" && <p role="status">● Đang thu âm…</p>}
      {result && <div aria-live="polite">
        <h3>{result.status === "retry" ? "Cần thu âm lại" : result.provider === "chivox" ? `Điểm tổng ${result.overall}/100` : `Điểm phát âm ${result.pronunciation ?? "—"}/100`}</h3>
        {result.warning && <p role="status" className="speaking-error">{result.status === "retry" ? "Bạn chưa đọc đúng từ/cụm từ. Hãy đọc lại nhé." : "Chưa nghe rõ giọng đọc của bạn. Hãy đọc lại ở nơi yên tĩnh nhé."}</p>}
        {result.status !== "retry" && <>
          {result.provider === "chivox" && result.pronunciation != null && <p>Điểm phát âm: {result.pronunciation}/100</p>}
        </>}
        <SpeakingFeedback result={result} />
      </div>}
    </div>}
  </section>;
}
