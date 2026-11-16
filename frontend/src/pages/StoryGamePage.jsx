import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../services/api";
import "./StoryGamePage.css";

const TOPICS = { daily: "Đời sống", work: "Công việc", travel: "Du lịch", school: "Trường học", technology: "Công nghệ" };
const TONES = { warm: "Ấm áp", funny: "Hài hước", serious: "Nghiêm túc", adventure: "Phiêu lưu" };
const normalize = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/gi, "d").toLowerCase().trim();
const message = e => typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Chưa tải được nội dung. Bạn thử lại nhé.";

function BookIcon({ className = "" }) {
  return <svg className={className} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M16 8c-4-3-8-3-12-2v21c4-1 8-1 12 2 4-3 8-3 12-2V6c-4-1-8-1-12 2Zm0 0v21" /><path d="M8 11h4m-4 5h4m8-5h4m-4 5h4" /></svg>;
}

export function StoryParagraph({ text, words, onWord }) {
  const patterns = words.map(w => w.word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a, b) => b.length - a.length);
  if (!patterns.length) return <p>{text}</p>;
  const parts = text.split(new RegExp(`(?<![a-zA-Z])(${patterns.join("|")})(?![a-zA-Z])`, "gi"));
  return <p>{parts.map((part, i) => {
    const word = words.find(w => w.word.toLowerCase() === part.toLowerCase());
    return word ? <button key={i} type="button" className="story-inline-word" onClick={() => onWord(word)} aria-label={`${part}: ${word.meaning}`}>{part}</button> : part;
  })}</p>;
}

export default function StoryGamePage() {
  const [params, setParams] = useSearchParams();
  const storyId = params.get("story");
  const historyView = params.get("view") === "history";
  const [topic, setTopic] = useState("work");
  const [tone, setTone] = useState("warm");
  const [words, setWords] = useState([]);
  const [wordStatus, setWordStatus] = useState("loading");
  const [wordError, setWordError] = useState("");
  const [selected, setSelected] = useState([]);
  const [picker, setPicker] = useState(false);
  const [query, setQuery] = useState("");
  const [story, setStory] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [answers, setAnswers] = useState({});
  const [translation, setTranslation] = useState(false);
  const [activeWord, setActiveWord] = useState(null);
  const mounted = useRef(true);
  const creationLock = useRef(false);
  const currentStory = useRef(storyId);
  currentStory.current = storyId;
  const busy = creating || submitting;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setWordStatus("loading"); setWordError("");
    api.get("/games/story/words", { signal: controller.signal }).then(({ data }) => {
      if (!controller.signal.aborted) { setWords(data); setWordStatus("ready"); }
    }).catch(e => { if (!controller.signal.aborted) { setWordStatus("error"); setWordError(message(e)); } });
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    setError(""); setStory(null); setAnswers({}); setTranslation(false); setActiveWord(null);
    if (!storyId && !historyView) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    const url = historyView ? "/games/story/stories" : `/games/story/stories/${storyId}`;
    api.get(url, { signal: controller.signal }).then(({ data }) => {
      if (controller.signal.aborted) return;
      if (historyView) setHistory(data);
      else {
        setStory(data);
        if (data.result) setAnswers(Object.fromEntries(data.result.feedback.map((f, i) => [i, f.selected])));
      }
    }).catch(e => { if (!controller.signal.aborted) setError(message(e)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [storyId, historyView, refresh]);

  async function create(demo = false) {
    if (creationLock.current) return;
    creationLock.current = true;
    setCreating(true); setError("");
    try {
      const { data } = await api.post(demo ? "/games/story/demo" : "/games/story/stories",
        demo ? {} : { topic, tone, vocabulary_ids: selected }, { timeout: 50000 });
      if (mounted.current) { setParams({ story: data.id }); setPicker(false); }
    } catch (e) { if (mounted.current) setError(message(e)); }
    finally { creationLock.current = false; if (mounted.current) setCreating(false); }
  }

  async function submit() {
    if (!story || submitting) return;
    const id = story.id;
    setSubmitting(true); setError("");
    try {
      const { data } = await api.post(`/games/story/stories/${id}/answers`, { answers: [answers[0], answers[1], answers[2]] });
      if (mounted.current && currentStory.current === id) setStory(prev => ({ ...prev, result: data }));
    } catch (e) { if (mounted.current && currentStory.current === id) setError(message(e)); }
    finally { if (mounted.current) setSubmitting(false); }
  }

  const chosenWords = words.filter(w => selected.includes(w.id));
  const filtered = words.filter(w => normalize(`${w.word} ${w.meaning}`).includes(normalize(query)));

  return <div className="story-game">
    <div className="story-page-heading"><div><h1>Game học tiếng Anh</h1><p>Biến từ quen thành một câu chuyện mới.</p></div><span className="story-mode-label">Đọc, khám phá, ghi nhớ</span></div>
    <nav className="story-tabs" aria-label="Game">
      <button type="button" className={!historyView ? "active" : ""} disabled={busy} onClick={() => setParams(storyId ? { story: storyId } : {})}><BookIcon />AI Story</button>
      <button type="button" className={historyView ? "active" : ""} disabled={busy} onClick={() => setParams({ view: "history" })}>Lịch sử truyện</button>
    </nav>

    {!historyView && <>
      <section className="story-builder" aria-labelledby="story-builder-title">
        <div className="story-builder-intro"><BookIcon /><div><h2 id="story-builder-title">AI Story</h2><p>Học qua truyện để nhớ lâu hơn.</p></div></div>
        <div className="story-controls">
          <label>Chủ đề<select value={topic} onChange={e => setTopic(e.target.value)} disabled={busy}>{Object.entries(TOPICS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label>Sắc thái<select value={tone} onChange={e => setTone(e.target.value)} disabled={busy}>{Object.entries(TONES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <button type="button" className="story-primary" disabled={busy || wordStatus !== "ready" || !selected.length} onClick={() => create()}>{creating ? "Đang chuẩn bị truyện…" : "Tạo truyện mới"}</button>
        </div>
        <div className="story-word-toolbar"><h3>Chọn từ đưa vào truyện</h3><span>Đã chọn {selected.length}/7</span><button type="button" className="story-secondary" disabled={busy} aria-expanded={picker} aria-controls="story-word-picker" onClick={() => setPicker(!picker)}>{picker ? "Đóng danh sách" : "+ Chọn từ đã học"}</button></div>
        <div className="story-selected">{chosenWords.length ? chosenWords.map(w => <button type="button" key={w.id} disabled={busy} onClick={() => setSelected(prev => prev.filter(id => id !== w.id))} aria-label={`Bỏ từ ${w.word}`}>{w.word}<span aria-hidden="true">×</span></button>) : <p>Chọn từ 1 đến 7 từ đã học để chúng trở thành một phần của câu chuyện.</p>}</div>
        {picker && <div className="story-picker" id="story-word-picker">
          <label htmlFor="story-word-search">Tìm từ hoặc nghĩa tiếng Việt</label>
          <input id="story-word-search" type="search" placeholder="Ví dụ: journey, hành trình…" value={query} onChange={e => setQuery(e.target.value)} disabled={busy} />
          {wordStatus === "loading" && <p role="status">Đang tải từ đã học…</p>}
          {wordStatus === "ready" && !words.length && <p>Bạn chưa có từ đã học. <Link to="/learn">Học thêm từ</Link> hoặc thử truyện mẫu bên dưới.</p>}
          {wordStatus === "ready" && words.length > 0 && !filtered.length && <p>Không tìm thấy từ phù hợp.</p>}
          <div className="story-word-options">{filtered.map(w => <label key={w.id}><input type="checkbox" checked={selected.includes(w.id)} disabled={busy || (selected.length >= 7 && !selected.includes(w.id))} onChange={e => setSelected(prev => e.target.checked ? [...prev, w.id] : prev.filter(id => id !== w.id))} /><span><strong>{w.word}</strong><small>{w.meaning}</small></span></label>)}</div>
        </div>}
        {wordError && <p role="alert" className="story-error">{wordError} <button type="button" onClick={() => setRefresh(v => v + 1)}>Tải lại danh sách</button></p>}
      </section>
    </>}

    {error && <div className="story-error" role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => setRefresh(v => v + 1)}>Thử tải lại</button>{!historyView && <button type="button" disabled={busy} onClick={() => create(true)}>Chơi truyện mẫu</button>}</div>}
    {(loading || creating) && <div className="story-loading" role="status" aria-live="polite"><BookIcon /><p>{creating ? "Đang chuẩn bị câu chuyện cho bạn…" : "Đang mở trang truyện…"}</p><div /><div /><div /></div>}

    {!historyView && !story && !loading && !creating && <section className="story-empty"><BookIcon /><h2>Mỗi từ mở ra một câu chuyện</h2><p>Chọn chủ đề, sắc thái và những từ bạn muốn nhớ. Đọc truyện, khám phá nghĩa rồi thử thách bản thân với 3 câu hỏi.</p><button type="button" className="story-secondary" onClick={() => create(true)} disabled={busy}>Chơi thử với truyện mẫu</button><small>Không cần chọn từ để chơi thử.</small></section>}

    {historyView && !loading && !creating && !error && <section className="story-history"><h2>Những câu chuyện của bạn</h2><p>20 truyện gần nhất được lưu để bạn đọc lại.</p>{history.length ? <ul>{history.map(item => <li key={item.id}><button type="button" onClick={() => setParams({ story: item.id })}><span><strong>{item.title}</strong><small>{TOPICS[item.topic]} — {new Date(item.created_at).toLocaleDateString("vi-VN")}{item.source === "demo" ? " — Truyện mẫu" : ""}</small></span><span>{item.score == null ? "Đọc tiếp" : `${item.score}/3 câu đúng`}</span></button></li>)}</ul> : <div className="story-empty"><BookIcon /><p>Bạn chưa có truyện nào. Câu chuyện đầu tiên đang chờ bạn.</p><button type="button" className="story-primary" onClick={() => setParams({})}>Bắt đầu chơi</button></div>}</section>}

    {story && !historyView && !loading && !creating && <>
      <article className="story-reader">
        <div className="story-reader-meta"><span>{TOPICS[story.topic]} / {TONES[story.tone]}</span><span>{story.source === "demo" ? "Truyện mẫu" : "Truyện của bạn"}</span></div>
        <h2>{story.title}</h2><p className="story-reading-hint">Bấm vào từ được tô màu để xem nghĩa.</p>
        <div className="story-prose" lang="en">{story.paragraphs.map((text, i) => <StoryParagraph key={i} text={text} words={story.words} onWord={setActiveWord} />)}</div>
        {activeWord && <div className="story-word-meaning" role="status"><strong>{activeWord.word}</strong><span>{activeWord.meaning || "Chưa có nghĩa cho từ này."}</span><button type="button" aria-label="Đóng nghĩa của từ" onClick={() => setActiveWord(null)}>×</button></div>}
        <button type="button" className="story-secondary" aria-expanded={translation} aria-controls="story-translation" onClick={() => setTranslation(!translation)}>{translation ? "Ẩn bản dịch" : "Xem bản dịch tiếng Việt"}</button>
        {translation && <div id="story-translation" className="story-translation" lang="vi"><h3>Bản dịch</h3>{story.translation.map((text, i) => <p key={i}>{text}</p>)}</div>}
        <details className="story-glossary"><summary>Từ vựng trong truyện ({story.words.length})</summary><dl>{story.words.map((w, i) => <div key={i}><dt>{w.word}</dt><dd>{w.meaning || "—"}</dd></div>)}</dl></details>
      </article>
      <section className="story-quiz" aria-labelledby="story-quiz-title"><div className="story-quiz-heading"><div><h2 id="story-quiz-title">Bạn nhớ được bao nhiêu?</h2><p>Trả lời 3 câu hỏi để hoàn thành câu chuyện.</p></div>{story.result && <strong className="story-score" role="status">{story.result.score}/3 câu đúng</strong>}</div>
        {story.questions.map((q, i) => <fieldset key={`${story.id}-${i}`} disabled={busy || Boolean(story.result)}><legend>{i + 1}. {q.question}</legend><div className="story-answer-options">{q.options.map((option, j) => <label key={j} className={story.result?.feedback[i].answer === j ? "correct" : story.result && answers[i] === j ? "incorrect" : answers[i] === j ? "selected" : ""}><input type="radio" name={`story-${story.id}-q${i}`} value={j} checked={answers[i] === j} onChange={() => setAnswers(prev => ({ ...prev, [i]: j }))} /><span>{option}</span>{story.result?.feedback[i].answer === j && <small>Đáp án đúng</small>}</label>)}</div>{story.result && <p className="story-explanation">{story.result.feedback[i].correct ? "Bạn trả lời đúng. " : "Chưa đúng. "}{story.result.feedback[i].explanation}</p>}</fieldset>)}
        {!story.result ? <button type="button" className="story-primary" disabled={busy || [0, 1, 2].some(i => answers[i] == null)} onClick={submit}>{submitting ? "Đang kiểm tra…" : "Kiểm tra đáp án"}</button> : <div className="story-finish"><p>{story.result.score === 3 ? "Bạn đã hiểu trọn vẹn câu chuyện. Thử một chủ đề mới nhé!" : "Đọc lại phần giải thích để nhớ câu chuyện và các từ lâu hơn nhé."}</p><button type="button" className="story-secondary" onClick={() => { setParams({}); window.scrollTo({ top: 0, behavior: "instant" }); }}>Tạo câu chuyện tiếp theo</button></div>}
      </section>
    </>}
  </div>;
}
