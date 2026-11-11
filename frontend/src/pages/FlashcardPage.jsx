import { useCallback, useEffect, useRef, useState } from "react";
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
      setCards(items); setStats(responseStats); setIndex(0); setRevealed(false); reviewId.current = crypto.randomUUID();
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
      else { setIndex((value) => value + 1); setRevealed(false); reviewId.current = crypto.randomUUID(); }
    } catch (err) {
      setError(formatApiError(err, "Không lưu được kết quả ôn tập. Hãy thử lại."));
    } finally { setBusy(false); }
  }, [busy, cards, index]);

  const current = cards[index];
  const ready = !loading && !error && !!current;
  useEffect(() => {
    function onKey(event) {
      if (!ready || busy) return;
      if (!revealed && (event.code === "Space" || event.key === "Enter")) {
        event.preventDefault(); setRevealed(true); return;
      }
      if (revealed) {
        const digit = /^Digit([1-4])$/.exec(event.code) || /^Numpad([1-4])$/.exec(event.code);
        if (digit) { event.preventDefault(); handleReview(Number(digit[1])); }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready, busy, revealed, handleReview]);

  if (loading) return <PageLoading label="Đang lấy những từ đến hạn ôn..."/>;

  const recall = typeof current?.retrievability === "number" ? current.retrievability : null;

  return <div className="sv-page">
    <div className="sv-page-heading"><div><span className="sv-eyebrow">SPACED REPETITION · FSRS</span><h1>Ôn tập thông minh</h1><p>Ôn đúng thời điểm để từ vựng ở lại trong trí nhớ lâu hơn.</p></div><button className="sv-btn sv-btn-outline" onClick={load}>↻ Tải lại</button></div>
    <div className="sv-stats-grid sv-review-stats"><StatTile label="Từ đã bắt đầu" value={stats?.total_words ?? "—"} icon="Aa" note="Đã có trạng thái học"/><StatTile label="Đang học" value={stats?.learning ?? "—"} icon="↗" tone="violet"/><StatTile label="Đã thành thạo" value={stats?.mastered ?? "—"} icon="✓" tone="green"/><StatTile label="Đến hạn" value={stats?.due_today ?? "—"} icon="↻" tone="amber"/></div>
    <div className="sv-review-layout"><div className="sv-review-main">
      {error && <PageError message={error} onRetry={() => setRefresh((value) => value+1)}/>}
      {!error && !current && <EmptyState title="Bạn đã ôn xong hôm nay!" description="Chưa có thẻ nào đến hạn. Hãy học từ mới hoặc quay lại sau."><Link className="sv-btn sv-btn-primary" to="/learn">Khám phá bài học →</Link></EmptyState>}
      {!error && current && !current.word && <EmptyState title="Không tải được từ vựng của thẻ" description="Dữ liệu thẻ này có thể đã bị xóa. Hãy kiểm tra trong database."><button className="sv-btn sv-btn-outline" onClick={load}>Tải lại</button></EmptyState>}
      {!error && current?.word && <><div className="sv-review-meta"><span>THẺ {index+1} / {cards.length}</span><span>FSRS · 4 mức đánh giá</span></div><div className="sv-progress-track"><div style={{width:`${(index+1)/cards.length*100}%`}}/></div>
        <button type="button" className={`sv-flashcard${revealed ? " revealed" : ""}`} onClick={() => setRevealed(true)} aria-label={revealed ? "Đang hiển thị nghĩa của từ" : "Lật thẻ để xem nghĩa"}>
          <span className="sv-flashcard-kicker">{revealed ? "MẶT SAU · NGHĨA" : "MẶT TRƯỚC · TỪ VỰNG"}</span>
          <strong>{revealed ? current.meaning : current.word}</strong>
          {revealed && current.example ? <span className="sv-flashcard-example">“{current.example}”</span> : current.phonetic ? <span className="sv-flashcard-pronunciation">{current.phonetic}</span> : null}
          {revealed && recall != null && recall > 0 && <span className="sv-flashcard-recall">Khả năng nhớ hiện tại: <b>{Math.round(recall * 100)}%</b></span>}
          <span className="sv-flashcard-tap">{revealed ? "Đánh giá mức độ ghi nhớ bên dưới" : "Nhấn thẻ hoặc Space để xem nghĩa ↗"}</span>
        </button>
        {revealed ? <><div className="sv-rating-grid">{RATINGS.map((rating) => <button type="button" className={`sv-rating sv-rating-${rating.tone}`} disabled={busy} key={rating.id} onClick={() => handleReview(rating.id)}><b>{rating.meaning}</b><small>{rating.label}</small></button>)}</div><div className="sv-kbd-hint"><kbd>1</kbd>–<kbd>4</kbd> đánh giá bằng bàn phím</div></>
          : <div className="sv-review-hint">Hãy thử nhớ nghĩa trước khi lật thẻ · <kbd>Space</kbd></div>}
      </>}
    </div><aside className="sv-review-sidebar"><SectionHeading title="Cách ôn hiệu quả"/><ol className="sv-guidelines"><li>Đọc từ và tự nhớ nghĩa trước khi lật.</li><li>Chọn đúng mức độ ghi nhớ thực tế.</li><li>FSRS sẽ tính thời điểm ôn tiếp theo.</li></ol><div className="sv-review-note">Lịch ôn được lưu bởi backend. Không chấm Mastery chỉ bằng hành động lật thẻ.</div></aside></div>
    {toast && <div className={`sv-review-toast sv-review-toast-${toast.tone}`} role="status"><b>{toast.word}</b><span>{toast.text}</span></div>}
  </div>;
}
