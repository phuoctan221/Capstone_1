import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDueCards, reviewCard, fetchStats } from "../services/learningService";
import { formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading, SectionHeading, StatTile } from "../components/PageState";

const RATINGS = [
  { id: 1, label: "Again", meaning: "Quên", tone: "red" },
  { id: 2, label: "Hard", meaning: "Khó", tone: "amber" },
  { id: 3, label: "Good", meaning: "Nhớ", tone: "blue" },
  { id: 4, label: "Easy", meaning: "Dễ", tone: "green" },
];

const MODES = [
  { id: "classic", label: "Lật thẻ", hint: "Xem nghĩa" },
  { id: "recall", label: "Recall", hint: "Tự nhớ nghĩa" },
  { id: "cloze", label: "Cloze", hint: "Điền từ vào câu" },
];
const MODE_KEY = "sv_review_mode";

function readMode() {
  try {
    const value = localStorage.getItem(MODE_KEY);
    return MODES.some((item) => item.id === value) ? value : "classic";
  } catch {
    return "classic";
  }
}

function wordVariants(word) {
  const base = word.toLowerCase();
  const variants = new Set([base, `${base}s`, `${base}es`, `${base}ed`, `${base}ing`]);
  if (base.endsWith("e")) {
    const stem = base.slice(0, -1);
    variants.add(`${stem}ing`);
    variants.add(`${stem}ed`);
  }
  if (base.endsWith("y")) {
    const stem = base.slice(0, -1);
    variants.add(`${stem}ies`);
    variants.add(`${stem}ied`);
  }
  return [...variants].sort((a, b) => b.length - a.length);
}

function buildCloze(card) {
  const example = card?.example?.trim();
  const word = card?.word?.trim();
  if (!example || !word) return null;
  for (const variant of wordVariants(word)) {
    const escaped = variant.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = new RegExp(`\\b${escaped}\\b`, "i").exec(example);
    if (!match) continue;
    return {
      before: example.slice(0, match.index),
      after: example.slice(match.index + match[0].length),
      answer: match[0],
    };
  }
  return null;
}

function normalizeAnswer(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function answerMatches(input, expected) {
  const typed = normalizeAnswer(input);
  if (!typed) return false;
  const parts = String(expected || "")
    .split(/[,;/·]/)
    .map(normalizeAnswer)
    .filter(Boolean);
  return parts.some((part) => {
    if (part === typed) return true;
    const shorter = typed.length < part.length ? typed : part;
    const longer = typed.length < part.length ? part : typed;
    return shorter.length >= 3 && longer.includes(shorter);
  });
}

function humanInterval(ms) {
  const minutes = Math.round(ms / 60000);
  if (minutes < 1) return "vài giây nữa";
  if (minutes < 60) return `sau ${minutes} phút`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `sau ${hours} giờ`;
  const days = Math.round(hours / 24);
  if (days < 30) return `sau ${days} ngày`;
  return `sau ${Math.round(days / 30)} tháng`;
}

export default function FlashcardPage() {
  const [cards, setCards] = useState([]);
  const [stats, setStats] = useState(null);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [mode, setMode] = useState(readMode);
  const [answer, setAnswer] = useState("");
  const [checked, setChecked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [toast, setToast] = useState(null);
  const reviewId = useRef(crypto.randomUUID());
  const toastTimer = useRef(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [due, responseStats] = await Promise.all([fetchDueCards(), fetchStats()]);
      const items = Array.isArray(due) ? due : (due?.items || []);
      setCards(items); setStats(responseStats); setIndex(0); setRevealed(false);
      setAnswer(""); setChecked(false); reviewId.current = crypto.randomUUID();
    } catch (err) { setError(formatApiError(err, "Không tải được danh sách ôn tập.")); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load, refresh]);
  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const handleReview = useCallback(async (rating) => {
    const current = cards[index];
    if (!current || busy) return;
    setBusy(true); setError("");
    try {
      const result = await reviewCard(current.vocabulary_id, rating, reviewId.current);
      const dueAt = result?.fsrs?.due_at ? new Date(result.fsrs.due_at) : null;
      if (dueAt && !Number.isNaN(dueAt.getTime())) {
        const ratingInfo = RATINGS.find((item) => item.id === rating);
        if (toastTimer.current) clearTimeout(toastTimer.current);
        setToast({
          tone: ratingInfo?.tone || "blue",
          word: current.word,
          text: `Đánh giá “${ratingInfo?.meaning ?? rating}” · gặp lại ${humanInterval(dueAt.getTime() - Date.now())}`,
        });
        toastTimer.current = setTimeout(() => setToast(null), 3200);
      }
      if (index + 1 >= cards.length) { setRefresh((value) => value + 1); }
      else {
        setIndex((value) => value + 1); setRevealed(false);
        setAnswer(""); setChecked(false); reviewId.current = crypto.randomUUID();
      }
    } catch (err) {
      setError(formatApiError(err, "Không lưu được kết quả ôn tập. Hãy thử lại."));
    } finally { setBusy(false); }
  }, [busy, cards, index]);

  const current = cards[index];
  const cloze = useMemo(() => buildCloze(current), [current]);
  const effectiveMode = mode === "cloze" && !cloze ? "recall" : mode;
  const expectedAnswer = effectiveMode === "cloze" ? (cloze?.answer || "") : (current?.meaning || "");
  const match = checked && answerMatches(answer, expectedAnswer);
  const ready = !loading && !error && !!current;

  function changeMode(next) {
    setMode(next);
    try { localStorage.setItem(MODE_KEY, next); } catch { }
    setRevealed(false); setAnswer(""); setChecked(false);
  }

  function handleCheck(event) {
    event.preventDefault();
    if (!answer.trim() || checked || busy) return;
    if (!answerMatches(answer, expectedAnswer)) {
      setChecked(true);
      handleReview(1);
      return;
    }
    setChecked(true);
  }

  useEffect(() => {
    function onKey(event) {
      if (!ready || busy) return;
      if (effectiveMode === "classic") {
        if (!revealed && (event.code === "Space" || event.key === "Enter")) {
          event.preventDefault(); setRevealed(true); return;
        }
        const digit = /^Digit([1-4])$/.exec(event.code) || /^Numpad([1-4])$/.exec(event.code);
        if (digit) { event.preventDefault(); handleReview(Number(digit[1])); }
        return;
      }
      if (!checked) return;
      const digit = /^Digit([1-4])$/.exec(event.code) || /^Numpad([1-4])$/.exec(event.code);
      if (digit) { event.preventDefault(); handleReview(Number(digit[1])); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready, busy, revealed, checked, effectiveMode, handleReview]);

  if (loading) return <PageLoading label="Đang lấy những từ đến hạn ôn..."/>;

  const recall = typeof current?.retrievability === "number" ? current.retrievability : null;

  return <div className="sv-page">
    <div className="sv-page-heading"><div><span className="sv-eyebrow">SPACED REPETITION · FSRS</span><h1>Ôn tập thông minh</h1><p>Ôn đúng thời điểm để từ vựng ở lại trong trí nhớ lâu hơn.</p></div><button className="sv-btn sv-btn-outline" onClick={load}>↻ Tải lại</button></div>
    <div className="sv-stats-grid sv-review-stats"><StatTile label="Từ đã bắt đầu" value={stats?.total_words ?? "—"} icon="Aa" note="Đã có trạng thái học"/><StatTile label="Đang học" value={stats?.learning ?? "—"} icon="↗" tone="violet"/><StatTile label="Đã thành thạo" value={stats?.mastered ?? "—"} icon="✓" tone="green"/><StatTile label="Đến hạn" value={stats?.due_today ?? "—"} icon="↻" tone="amber"/></div>
    <div className="sv-review-layout"><div className="sv-review-main">
      {error && <PageError message={error} onRetry={() => setRefresh((value) => value+1)}/>}
      {!error && !current && <EmptyState title="Bạn đã ôn xong hôm nay!" description="Chưa có thẻ nào đến hạn. Hãy học từ mới hoặc quay lại sau."><Link className="sv-btn sv-btn-primary" to="/learn">Khám phá bài học →</Link></EmptyState>}
      {!error && current && !current.word && <EmptyState title="Không tải được từ vựng của thẻ" description="Dữ liệu thẻ này có thể đã bị xóa. Hãy kiểm tra trong database."><button className="sv-btn sv-btn-outline" onClick={load}>Tải lại</button></EmptyState>}
      {!error && current?.word && <>
        <div className="sv-review-meta"><span>THẺ {index+1} / {cards.length}</span><span>FSRS · 4 mức đánh giá</span></div>
        <div className="sv-progress-track"><div style={{width:`${(index+1)/cards.length*100}%`}}/></div>
        <div className="sv-review-modes" role="tablist" aria-label="Chế độ ôn tập">
          {MODES.map((item) => <button key={item.id} type="button" role="tab" aria-selected={mode === item.id} className={`sv-review-mode${mode === item.id ? " is-active" : ""}`} onClick={() => changeMode(item.id)}><b>{item.label}</b><small>{item.hint}</small></button>)}
        </div>
        {effectiveMode === "classic" ? <>
          <button type="button" className={`sv-flashcard${revealed ? " revealed" : ""}`} onClick={() => setRevealed(true)} aria-label={revealed ? "Đang hiển thị nghĩa của từ" : "Lật thẻ để xem nghĩa"}>
            <span className="sv-flashcard-kicker">{revealed ? "MẶT SAU · NGHĨA" : "MẶT TRƯỚC · TỪ VỰNG"}</span>
            <strong>{revealed ? current.meaning : current.word}</strong>
            {revealed && current.example ? <span className="sv-flashcard-example">“{current.example}”</span> : current.phonetic ? <span className="sv-flashcard-pronunciation">{current.phonetic}</span> : null}
            {revealed && recall != null && recall > 0 && <span className="sv-flashcard-recall">Khả năng nhớ hiện tại: <b>{Math.round(recall * 100)}%</b></span>}
            <span className="sv-flashcard-tap">{revealed ? "Đánh giá mức độ ghi nhớ bên dưới" : "Nhấn thẻ hoặc Space để xem nghĩa ↗"}</span>
          </button>
          <div className="sv-rating-grid">{RATINGS.map((rating) => <button type="button" className={`sv-rating sv-rating-${rating.tone}`} disabled={busy} key={rating.id} onClick={() => handleReview(rating.id)}><b>{rating.meaning}</b><small>{rating.label}</small></button>)}</div>
          <div className="sv-kbd-hint">{revealed ? <><kbd>1</kbd>–<kbd>4</kbd> đánh giá bằng bàn phím</> : <><kbd>1</kbd>–<kbd>4</kbd> đánh giá · <kbd>Space</kbd> xem nghĩa</>}</div>
        </> : <>
          <div className="sv-recall-card" key={current.vocabulary_id}>
            <span className="sv-flashcard-kicker">{effectiveMode === "cloze" ? "ĐIỀN TỪ CÒN THIẾU" : "NHỚ NGHĨA CỦA TỪ"}</span>
            {effectiveMode === "cloze" ? <>
              <p className="sv-cloze-sentence">{cloze.before}<span className="sv-cloze-blank">{checked ? cloze.answer : "_____"}</span>{cloze.after}</p>
              <p className="sv-cloze-meaning">Nghĩa: {current.meaning}</p>
            </> : <>
              <strong className="sv-recall-word">{current.word}</strong>
              {current.phonetic ? <span className="sv-flashcard-pronunciation">{current.phonetic}</span> : null}
              {mode === "cloze" ? <p className="sv-cloze-meaning">Câu ví dụ không chứa từ này nên đang dùng Recall.</p> : null}
            </>}
            <form className="sv-recall-form" onSubmit={handleCheck}>
              <input className="sv-recall-input" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder={effectiveMode === "cloze" ? "Nhập từ còn thiếu..." : "Nhập nghĩa tiếng Việt..."} disabled={checked || busy} autoFocus autoComplete="off" spellCheck={false} aria-label={effectiveMode === "cloze" ? "Từ còn thiếu" : "Nghĩa của từ"}/>
              {!checked && <button type="submit" className="sv-btn sv-btn-primary" disabled={!answer.trim() || busy}>Kiểm tra</button>}
            </form>
            {checked ? <div className={`sv-recall-feedback${match ? " is-correct" : " is-wrong"}`}>
              <b>{match ? "Khớp đáp án" : "Chưa khớp đáp án"}</b>
              <span>{effectiveMode === "cloze" ? `Từ đúng: ${cloze.answer}` : `Nghĩa đúng: ${current.meaning}`}</span>
              {effectiveMode === "recall" && current.example ? <em>“{current.example}”</em> : null}
              {recall != null && recall > 0 ? <span className="sv-flashcard-recall">Khả năng nhớ hiện tại: <b>{Math.round(recall * 100)}%</b></span> : null}
            </div> : <div className="sv-review-hint">Gõ câu trả lời rồi nhấn <kbd>Enter</kbd> để kiểm tra.</div>}
          </div>
          {checked && <><div className="sv-rating-grid">{RATINGS.map((rating) => <button type="button" className={`sv-rating sv-rating-${rating.tone}`} disabled={busy} key={rating.id} onClick={() => handleReview(rating.id)}><b>{rating.meaning}</b><small>{rating.label}</small></button>)}</div><div className="sv-kbd-hint"><kbd>1</kbd>–<kbd>4</kbd> đánh giá bằng bàn phím</div></>}
        </>}
      </>}
    </div><aside className="sv-review-sidebar"><SectionHeading title="Cách ôn hiệu quả"/><ol className="sv-guidelines"><li>Đánh giá 4 mức ngay trên mặt trước, không cần lật thẻ.</li><li>Recall/Cloze trả lời sai sẽ tự chuyển từ và tính là đã quên.</li><li>Chọn đúng mức độ ghi nhớ thực tế để FSRS tính lịch ôn.</li></ol><div className="sv-review-note">Lịch ôn được lưu bởi backend. Không chấm Mastery chỉ bằng hành động lật thẻ.</div></aside></div>
    {toast && <div className={`sv-review-toast sv-review-toast-${toast.tone}`} role="status"><b>{toast.word}</b><span>{toast.text}</span></div>}
  </div>;
}
