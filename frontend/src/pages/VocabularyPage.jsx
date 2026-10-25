import { useEffect, useState, useCallback } from "react";
import VocabularyForm from "../components/VocabularyForm";
import VocabularyBatchForm from "../components/VocabularyBatchForm";
import VocabularyCard from "../components/VocabularyCard";
import {
  fetchVocabularies,
  deleteVocabulary,
} from "../services/vocabularyService";

export default function VocabularyPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const pageSize = 12;

  const load = useCallback(async () => {
    const params = { page, page_size: pageSize };
    if (search) params.search = search;
    if (level) params.level = level;
    try {
      const data = await fetchVocabularies(params);
      setItems(data.items);
      setTotal(data.total);
      setError("");
    } catch {
      setError("Không tải được danh sách từ vựng. Vui lòng thử lại.");
    }
  }, [page, search, level]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (id) => {
    if (!window.confirm("Xóa từ này?")) return;
    try {
      await deleteVocabulary(id);
      setError("");
      load();
    } catch {
      setError("Không xóa được từ vựng. Vui lòng thử lại.");
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <VocabularyForm onCreated={load} />

      <div style={{ margin: "1.5rem 0" }}>
        <VocabularyBatchForm onCreated={load} />
      </div>

      <div style={{ display: "flex", gap: "1rem", margin: "1.5rem 0" }}>
        <input
          placeholder="Tìm kiếm từ hoặc nghĩa..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ flex: 1, padding: "0.6rem 0.75rem", border: "1px solid var(--border)", borderRadius: 8 }}
        />
        <select
          value={level}
          onChange={(e) => {
            setLevel(e.target.value);
            setPage(1);
          }}
          style={{ padding: "0.6rem", border: "1px solid var(--border)", borderRadius: 8 }}
        >
          <option value="">Tất cả trình độ</option>
          {["A1", "A2", "B1", "B2", "C1", "C2"].map((lv) => (
            <option key={lv}>{lv}</option>
          ))}
        </select>
      </div>

      {error && <p className="error">{error}</p>}

      <p className="muted">Tổng cộng: {total} từ</p>

      <div className="grid">
        {items.map((v) => (
          <VocabularyCard key={v.id} vocab={v} onDelete={handleDelete} />
        ))}
        {items.length === 0 && <p className="muted">Chưa có từ vựng nào.</p>}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center", marginTop: "1.5rem" }}>
          <button className="btn btn-outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Trước
          </button>
          <span style={{ alignSelf: "center" }}>
            {page} / {totalPages}
          </span>
          <button className="btn btn-outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            Sau
          </button>
        </div>
      )}
    </div>
  );
}
