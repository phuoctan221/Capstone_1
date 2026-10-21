import { useEffect, useState } from "react";
import Flashcard from "../components/Flashcard";
import { fetchDueCards, reviewCard, fetchStats } from "../services/learningService";
import { fetchVocabulary } from "../services/vocabularyService";

export default function FlashcardPage() {
  const [cards, setCards] = useState([]);
  const [vocabMap, setVocabMap] = useState({});
  const [stats, setStats] = useState(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const due = await fetchDueCards();
    const st = await fetchStats();
    setCards(due);
    setStats(st);
    setIndex(0);

    const map = {};
    await Promise.all(
      due.map(async (card) => {
        try {
          const v = await fetchVocabulary(card.vocabulary_id);
          map[card.vocabulary_id] = v;
        } catch {
          map[card.vocabulary_id] = null;
        }
      })
    );
    setVocabMap(map);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const handleReview = async (vocabId, remembered) => {
    await reviewCard(vocabId, remembered);
    setIndex((i) => i + 1);
    if (index + 1 >= cards.length) load();
  };

  if (loading) return <p className="muted">Đang tải...</p>;

  const current = cards[index];

  return (
    <div>
      {stats && (
        <div className="stats">
          <div className="card stat-box">
            <div className="number">{stats.total_words}</div>
            <div className="label">Tổng số từ</div>
          </div>
          <div className="card stat-box">
            <div className="number">{stats.learning}</div>
            <div className="label">Đang học</div>
          </div>
          <div className="card stat-box">
            <div className="number">{stats.mastered}</div>
            <div className="label">Đã thuộc</div>
          </div>
          <div className="card stat-box">
            <div className="number">{stats.due_today}</div>
            <div className="label">Đến hạn hôm nay</div>
          </div>
        </div>
      )}

      {!current ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem" }}>
          <h2>Không còn thẻ nào đến hạn 🎉</h2>
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            Quay lại sau để ôn tập tiếp nhé!
          </p>
        </div>
      ) : (
        <>
          <p className="muted" style={{ marginBottom: "0.75rem" }}>
            Thẻ {index + 1} / {cards.length}
          </p>
          <Flashcard
            card={current}
            vocab={vocabMap[current.vocabulary_id]}
            onReview={handleReview}
          />
        </>
      )}
    </div>
  );
}
