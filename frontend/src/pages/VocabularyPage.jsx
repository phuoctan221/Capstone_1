import { useEffect, useState } from "react";
import { fetchVocabularies } from "../services/vocabularyService";
import { DOMAINS, domainOf, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading } from "../components/PageState";

export default function VocabularyPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("");
  const [level, setLevel] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const pageSize = 12;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const params = { page, page_size: pageSize };
        if (search.trim()) params.search = search.trim();
        if (domain) params.topic = domain;
        if (level) params.level = level;
        const data = await fetchVocabularies(params);
        if (active) { setItems(Array.isArray(data?.items) ? data.items : []); setTotal(Number(data?.total || 0)); setError(""); }
      } catch (err) { if (active) setError(formatApiError(err)); }
      finally { if (active) setLoading(false); }
    }, search ? 280 : 0);
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [page, search, domain, level, refresh]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return <div className="sv-page">
    <div className="sv-page-heading"><div><span className="sv-eyebrow">TỪ ĐIỂN HỌC TẬP</span><h1>Thư viện từ vựng</h1><p>Khám phá các từ thuộc General, Technology và Business English.</p></div><span className="sv-catalog-count">{total} kết quả</span></div>
    <div className="sv-catalog-filters"><label className="sv-search"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Tìm theo từ hoặc nghĩa..." aria-label="Tìm từ vựng"/></label><select value={domain} onChange={(event) => { setDomain(event.target.value); setPage(1); }} aria-label="Lọc lĩnh vực"><option value="">Tất cả lĩnh vực</option>{DOMAINS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}</select><select value={level} onChange={(event) => { setLevel(event.target.value); setPage(1); }} aria-label="Lọc trình độ"><option value="">Mọi trình độ</option>{["A1","A2","B1","B2","C1","C2"].map((item) => <option key={item} value={item}>{item}</option>)}</select></div>
    {error ? <PageError message={error} onRetry={() => setRefresh((value) => value+1)}/> : loading ? <PageLoading label="Đang tìm từ vựng..."/> : items.length === 0 ? <EmptyState title="Chưa tìm thấy từ vựng" description="Thử từ khóa khác hoặc thay đổi bộ lọc lĩnh vực/trình độ."/> : <div className="sv-word-grid sv-library-grid">{items.map((word) => <article className="sv-word-card" key={word.id}><div className="sv-word-card-top"><span className="sv-level-tag">{word.level}</span><span className="sv-word-topic">{domainOf(word.topic)?.label || word.topic}</span></div><h3>{word.word}</h3>{word.phonetic && <small>{word.phonetic}</small>}<p>{word.meaning}</p>{word.example && <blockquote>{word.example}</blockquote>}</article>)}</div>}
    {totalPages > 1 && <div className="sv-pagination"><button className="sv-btn sv-btn-outline" onClick={() => setPage((value) => Math.max(1,value-1))} disabled={page===1}>← Trước</button><span>Trang {page} / {totalPages}</span><button className="sv-btn sv-btn-outline" disabled={page === totalPages} onClick={() => setPage((value) => Math.min(totalPages,value+1))}>Sau →</button></div>}
  </div>;
}
