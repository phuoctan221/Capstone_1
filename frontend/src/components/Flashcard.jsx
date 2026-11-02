import { useState } from "react";

export default function Flashcard({ card, vocab, onReview }) {
  const [revealed, setRevealed] = useState(false);

  if (!vocab) return null;

  return (
    <div>
      <div className="card flashcard" onClick={() => setRevealed(true)}>
        <div className="word">{vocab.word}</div>
        {vocab.phonetic && <p className="muted">/{vocab.phonetic}/</p>}
        {revealed ? (
          <div className="meaning">
            <p>{vocab.meaning}</p>
            {vocab.example && (
              <p className="muted" style={{ fontStyle: "italic", marginTop: 8 }}>
                "{vocab.example}"
              </p>
            )}
          </div>
        ) : (
          <p className="muted" style={{ marginTop: "1.5rem" }}>
            Nhấn để xem đáp án
          </p>
        )}
      </div>
      {revealed && (
        <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
          <button
            className="btn btn-danger"
            style={{ flex: 1 }}
            onClick={() => {
              onReview(card.vocabulary_id, false);
              setRevealed(false);
            }}
          >
            Chưa nhớ
          </button>
          <button
            className="btn"
            style={{ flex: 1, background: "var(--success)" }}
            onClick={() => {
              onReview(card.vocabulary_id, true);
              setRevealed(false);
            }}
          >
            Đã nhớ
          </button>
        </div>
      )}
    </div>
  );
}
