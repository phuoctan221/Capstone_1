export default function VocabularyCard({ vocab, onDelete }) {
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>{vocab.word}</h3>
        {onDelete && (
          <button className="btn btn-danger" onClick={() => onDelete(vocab.id)}>
            Xóa
          </button>
        )}
      </div>
      {vocab.phonetic && <p className="muted">/{vocab.phonetic}/</p>}
      <p style={{ margin: "0.5rem 0" }}>{vocab.meaning}</p>
      {vocab.example && (
        <p className="muted" style={{ fontStyle: "italic" }}>
          "{vocab.example}"
        </p>
      )}
      <div style={{ marginTop: "0.75rem" }}>
        <span className="badge">{vocab.level}</span>
        <span className="badge">{vocab.topic}</span>
        {vocab.part_of_speech && (
          <span className="badge">{vocab.part_of_speech}</span>
        )}
      </div>
    </div>
  );
}
