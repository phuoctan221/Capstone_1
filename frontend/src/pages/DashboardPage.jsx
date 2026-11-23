import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchLessons, fetchProgress } from "../services/lessonService";
import { fetchDailyPlan, fetchStats } from "../services/learningService";
import { domainOf, myDomains, formatApiError } from "../constants/domains";
import { computeLevelProgress } from "../constants/levels";
import { EmptyState, PageError, PageLoading, SectionHeading, StatTile } from "../components/PageState";
import DailyPlanCard from "../components/DailyPlanCard";
import { useAuth } from "../hooks/useAuth";

export default function DashboardPage() {
  const user = useAuth();
  const [state, setState] = useState({ loading: true, progress: null, stats: null, lessons: [], daily: null, error: "", secondaryError: "" });
  const [refresh, setRefresh] = useState(0);
  const chosen = useMemo(() => myDomains(user), [user]);
  const levelProgress = useMemo(() => computeLevelProgress(state.lessons, chosen), [state.lessons, chosen]);

  useEffect(() => {
    let active = true;
    (async () => {
      setState((old) => ({ ...old, loading: true, error: "" }));
      const results = await Promise.allSettled([fetchProgress(), fetchStats(), fetchLessons(), fetchDailyPlan()]);
      if (!active) return;
      const progress = results[0].status === "fulfilled" ? results[0].value : null;
      const stats = results[1].status === "fulfilled" ? results[1].value : null;
      const lessons = results[2].status === "fulfilled" && Array.isArray(results[2].value) ? results[2].value : [];
      const daily = results[3].status === "fulfilled" ? results[3].value : null;
      const secondaryError = results.slice(1).some((result) => result.status === "rejected")
        ? "Một số thống kê chưa tải được. Bạn có thể thử tải lại." : "";
      setState({
        loading: false, progress, stats, lessons, daily,
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
  const chosenIds = chosen.map((domain) => domain.id);
  const nextLesson = state.lessons.find(
    (lesson) => lesson.word_count > 0 && !lesson.completed && lesson.unlocked !== false && chosenIds.includes(lesson.topic)
  );
  const due = stats.due_today;

  return (
    <div className="sv-page sv-dashboard">
      <div className="sv-hero">
        <div className="sv-hero-content">
          <span className="sv-hero-kicker">Không gian học tập</span>
          <h1>Chào {firstName},<br/><span>tiếp tục bài học hôm nay nhé.</span></h1>
          <p>Từ vựng dễ nhớ hơn khi bạn học đúng kỹ năng và ôn tập đúng lúc.</p>
          {levelProgress && <div className="sv-hero-words">
            <b>{levelProgress.remaining}</b>
            <span>{levelProgress.allCompleted
              ? "từ còn lại · bạn đã hoàn thành lộ trình hiện có"
              : levelProgress.nextLevel
                ? `từ còn lại để lên ${levelProgress.nextLevel}`
                : "từ còn lại để lên cấp tiếp theo"}</span>
          </div>}
          <div className="sv-hero-actions">
            <Link className="sv-btn sv-btn-light" to={nextLesson ? `/lessons/${nextLesson.slug || nextLesson.id}?unit=${nextLesson.next_unit || 1}` : "/learn"}>Tiếp tục học <span>→</span></Link>
            <Link className="sv-btn sv-btn-ghost-light" to="/flashcards">Ôn tập FSRS</Link>
          </div>
        </div>
      </div>

      {state.secondaryError && <div className="sv-notice" role="status">{state.secondaryError} <button type="button" onClick={() => setRefresh((value) => value + 1)}>Tải lại</button></div>}

      <DailyPlanCard plan={state.daily} />

      <div className="sv-stats-grid">
        <StatTile label="Từ đã bắt đầu học" value={progress.words_learned ?? "—"} note="Đã luyện tập hoặc ôn tập" icon="Aa" tone="blue"/>
        <StatTile label="Từ đã thành thạo" value={progress.words_mastered ?? "—"} note="Đạt cả 3 kỹ năng" icon="✓" tone="green"/>
        <StatTile label="Cần ôn hôm nay" value={due ?? "—"} note="Theo lịch FSRS" icon="↻" tone="amber"/>
        <StatTile label="XP tích lũy" value={progress.xp ?? "—"} note={`Cấp độ ${progress.level ?? "—"} · ${progress.streak ?? "—"} ngày liên tiếp`} icon="XP" tone="violet"/>
      </div>

      <div className="sv-two-col">
        <section className="sv-panel">
          <SectionHeading eyebrow="Bắt đầu ở đây" title="Bài học tiếp theo"/>
          {nextLesson ? <Link to={`/lessons/${nextLesson.slug || nextLesson.id}?unit=${nextLesson.next_unit || 1}`} className="sv-next-lesson"><span className="sv-next-icon">{domainOf(nextLesson.topic)?.glyph || "Aa"}</span><span><strong>{nextLesson.title}</strong><small>Bài {nextLesson.next_unit || 1}/{nextLesson.unit_count || 1} · {nextLesson.next_unit_word_count || 15} từ · {nextLesson.level}</small></span><span className="sv-next-arrow">→</span></Link>
            : <EmptyState title="Chưa có bài học phù hợp" description="Hãy khám phá lộ trình hoặc cập nhật lĩnh vực quan tâm."><Link to="/learn" className="sv-btn sv-btn-primary">Xem lộ trình</Link></EmptyState>}
        </section>
        <section className="sv-panel sv-panel-tinted">
          <SectionHeading eyebrow="Ôn tập thông minh" title="Đến hạn ôn tập"/>
          <div className="sv-review-callout"><div className="sv-due-number">{due ?? "—"}</div><p>từ đang chờ được ôn theo thuật toán FSRS.</p></div>
          <Link className="sv-btn sv-btn-primary sv-btn-full" to="/flashcards">Mở bộ thẻ ôn tập →</Link>
        </section>
      </div>
    </div>
  );
}
