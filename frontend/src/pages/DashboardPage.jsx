import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchLessons, fetchProgress } from "../services/lessonService";
import { fetchStats } from "../services/learningService";
import { domainOf, myDomains, clampPercent, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading, SectionHeading, StatTile } from "../components/PageState";
import { useAuth } from "../hooks/useAuth";

export default function DashboardPage() {
  const user = useAuth();
  const [state, setState] = useState({ loading: true, progress: null, stats: null, lessons: [], error: "", secondaryError: "" });
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      setState((old) => ({ ...old, loading: true, error: "" }));
      const results = await Promise.allSettled([fetchProgress(), fetchStats(), fetchLessons()]);
      if (!active) return;
      const progress = results[0].status === "fulfilled" ? results[0].value : null;
      const stats = results[1].status === "fulfilled" ? results[1].value : null;
      const lessons = results[2].status === "fulfilled" && Array.isArray(results[2].value) ? results[2].value : [];
      const secondaryError = results.slice(1).some((result) => result.status === "rejected")
        ? "Một số thống kê chưa tải được. Bạn có thể thử tải lại." : "";
      setState({
        loading: false, progress, stats, lessons,
        error: results[0].status === "rejected" ? formatApiError(results[0].reason) : "",
        secondaryError,
      });
    })();
    return () => { active = false; };
  }, [refresh]);

  if (state.loading) return <PageLoading label="Đang chuẩn bị không gian học tập..." />;
  if (state.error) return <PageError message={state.error} onRetry={() => setRefresh((value) => value + 1)} />;

  const progress = state.progress || {};
  const stats = state.stats || {};
  const firstName = String(user?.username || "bạn").trim().split(/\s+/).slice(-1)[0];
  const chosen = myDomains(user);
  const chosenIds = chosen.map((domain) => domain.id);
  const nextLesson = state.lessons.find(
    (lesson) => lesson.word_count > 0 && !lesson.completed && lesson.unlocked !== false && chosenIds.includes(lesson.topic)
  );
  const due = stats.due_today;

  return (
    <div className="sv-page sv-dashboard">
      <div className="sv-hero">
        <div className="sv-hero-content">
          <span className="sv-hero-kicker">KHÔNG GIAN HỌC TẬP CỦA BẠN</span>
          <h1>Chào {firstName},<br/><span>học thêm một chút nhé.</span></h1>
          <p>Từ vựng dễ nhớ hơn khi bạn học đúng kỹ năng và ôn tập đúng lúc.</p>
          <div className="sv-hero-actions">
            <Link className="sv-btn sv-btn-light" to={nextLesson ? `/lessons/${nextLesson.slug || nextLesson.id}` : "/learn"}>Tiếp tục học <span>→</span></Link>
            <Link className="sv-btn sv-btn-ghost-light" to="/flashcards">Ôn tập FSRS</Link>
          </div>
        </div>
        <div className="sv-hero-art" aria-hidden="true"><div className="sv-art-orbit sv-art-orbit-one"/><div className="sv-art-orbit sv-art-orbit-two"/><div className="sv-art-card sv-art-card-one"><span>Meaning</span><b>◎</b></div><div className="sv-art-card sv-art-card-two"><span>Spelling</span><b>✦</b></div><div className="sv-art-card sv-art-card-three"><span>Context</span><b>▤</b></div></div>
      </div>

      {state.secondaryError && <div className="sv-notice" role="status">{state.secondaryError} <button type="button" onClick={() => setRefresh((value) => value + 1)}>Tải lại</button></div>}

      <div className="sv-stats-grid">
        <StatTile label="Từ đã bắt đầu học" value={progress.words_learned ?? "—"} note="Các từ đã có điểm Mastery" icon="Aa" tone="blue"/>
        <StatTile label="Từ đã thành thạo" value={progress.words_mastered ?? "—"} note="Đạt cả 3 kỹ năng" icon="✓" tone="green"/>
        <StatTile label="Cần ôn hôm nay" value={due ?? "—"} note="Theo lịch FSRS" icon="↻" tone="amber"/>
        <StatTile label="XP tích lũy" value={progress.xp ?? "—"} note={`Cấp độ ${progress.level ?? "—"} · ${progress.streak ?? "—"} ngày liên tiếp`} icon="✦" tone="violet"/>
      </div>

      {chosen.length ? (
        <>
          <SectionHeading eyebrow="LĨNH VỰC CỦA BẠN" title="Lĩnh vực bạn đang học" description="Chỉ những lĩnh vực bạn đã chọn khi bắt đầu học." action={<Link className="sv-text-link" to="/learn">Xem mọi bài học →</Link>}/>
          <div className="sv-domains-grid">
            {chosen.map((domain) => {
              const subset = state.lessons.filter((lesson) => lesson.topic === domain.id);
              const total = subset.reduce((sum, lesson) => sum + (lesson.word_count || 0), 0);
              const finished = subset.filter((lesson) => lesson.completed).length;
              const pct = subset.length ? (finished / subset.length) * 100 : 0;
              return <Link key={domain.id} to={`/learn?domain=${domain.id}`} className={`sv-domain-card sv-tone-${domain.tone}`}>
                <div className="sv-domain-glyph">{domain.glyph}</div><span className="sv-domain-count">{subset.length} bài học</span>
                <h3>{domain.label}</h3><p>{domain.subtitle}</p>
                <div className="sv-domain-progress"><div style={{ width: `${clampPercent(pct)}%` }}/></div>
                <div className="sv-domain-footer"><span>{finished}/{subset.length} bài hoàn thành · {total} từ</span><b>↗</b></div>
              </Link>;
            })}
          </div>
        </>
      ) : (
        <section className="sv-panel">
          <SectionHeading eyebrow="LĨNH VỰC CỦA BẠN" title="Chưa chọn lĩnh vực quan tâm"/>
          <EmptyState title="Bạn chưa chọn lĩnh vực nào" description="Chọn lĩnh vực quan tâm để lộ trình học hiển thị đúng nội dung cho bạn.">
            <Link className="sv-btn sv-btn-primary" to="/settings/learning">Chọn lĩnh vực</Link>
          </EmptyState>
        </section>
      )}

      <div className="sv-two-col">
        <section className="sv-panel">
          <SectionHeading eyebrow="BẮT ĐẦU Ở ĐÂY" title="Bài học tiếp theo"/>
          {nextLesson ? <Link to={`/lessons/${nextLesson.slug || nextLesson.id}`} className="sv-next-lesson"><span className="sv-next-icon">{domainOf(nextLesson.topic)?.glyph || "Aa"}</span><span><strong>{nextLesson.title}</strong><small>{nextLesson.word_count} từ · {nextLesson.level}</small></span><span className="sv-next-arrow">→</span></Link>
            : <EmptyState title="Chưa có bài học phù hợp" description="Hãy khám phá lộ trình hoặc cập nhật lĩnh vực quan tâm."><Link to="/learn" className="sv-btn sv-btn-primary">Xem lộ trình</Link></EmptyState>}
        </section>
        <section className="sv-panel sv-panel-tinted">
          <SectionHeading eyebrow="ÔN TẬP THÔNG MINH" title="Đến hạn ôn tập"/>
          <div className="sv-review-callout"><div className="sv-due-number">{due ?? "—"}</div><p>từ đang chờ được ôn theo thuật toán FSRS.</p></div>
          <Link className="sv-btn sv-btn-primary sv-btn-full" to="/flashcards">Mở bộ thẻ ôn tập →</Link>
        </section>
      </div>
    </div>
  );
}
