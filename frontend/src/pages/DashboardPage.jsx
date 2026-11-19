import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDashboard } from "../services/learningService";
import { fetchMe } from "../services/authService";
import { domainOf, myDomains, formatApiError } from "../constants/domains";
import { computeLevelProgress } from "../constants/levels";
import { EmptyState, PageError, PageLoading, SectionHeading, StatTile } from "../components/PageState";
import DailyPlanCard from "../components/DailyPlanCard";
import AIStudyCoachCard from "../components/AIStudyCoachCard";
import { useAuth } from "../hooks/useAuth";

export default function DashboardPage() {
  const user = useAuth();
  const [state, setState] = useState({ loading: true, progress: null, stats: null, lessons: [], daily: null, user: null, error: "", secondaryError: "" });
  const [refresh, setRefresh] = useState(0);
  const chosen = useMemo(() => myDomains(user), [user]);
  const levelProgress = useMemo(() => computeLevelProgress(state.lessons, chosen), [state.lessons, chosen]);

  useEffect(() => {
    let active = true;
    (async () => {
      setState((old) => ({ ...old, loading: true, error: "" }));
      try {
        const [me, data] = await Promise.allSettled([fetchMe(), fetchDashboard()]);
        if (!active) return;
        if (me.status === "fulfilled") {
          setState((old) => ({ ...old, user: me.value }));
        }
        if (data.status === "fulfilled") {
          setState({
            loading: false,
            progress: data.value.progress || null,
            stats: data.value.stats || null,
            lessons: Array.isArray(data.value.lessons) ? data.value.lessons : [],
            daily: data.value.daily || null,
            user: data.value.user || null,
            error: "",
            secondaryError: "",
          });
        } else {
          setState((old) => ({
            ...old,
            loading: false,
            error: formatApiError(data.reason),
          }));
        }
      } catch (err) {
        if (active) {
          setState((old) => ({
            ...old,
            loading: false,
            error: formatApiError(err),
          }));
        }
      }
    })();
    return () => { active = false; };
  }, [refresh]);

  const progress = state.progress || {};
  const stats = state.stats || {};
  const firstName = String(user?.username || "bạn").trim().split(/\s+/).slice(-1)[0];
  const chosenIds = chosen.map((domain) => domain.id);
  const nextLesson = state.lessons
    .filter((lesson) => lesson.word_count > 0 && !lesson.completed && lesson.unlocked !== false && chosenIds.includes(lesson.topic))
    .sort((a, b) => Number(Boolean(b.recommended)) - Number(Boolean(a.recommended)) || Number(Boolean(a.review_only)) - Number(Boolean(b.review_only)) || (a.order ?? 0) - (b.order ?? 0))[0];
  const due = stats.due_today;
  const levelMessage = (() => {
    if (!levelProgress || levelProgress.allCompleted) {
      return "Bạn đã hoàn thành các cấp độ hiện có trong lộ trình.";
    }
    if (levelProgress.remaining > 0) {
      const levelLabel = levelProgress.targetLevel
        ? ` ở cấp độ ${levelProgress.targetLevel}`
        : " trong lộ trình hiện tại";
      const nextLabel = levelProgress.nextLevel ? ` trước khi làm bài kiểm tra mở ${levelProgress.nextLevel}` : "";
      return <>Bạn còn <strong>{levelProgress.remaining} từ</strong> cần học{levelLabel}{nextLabel}.</>;
    }
    if (levelProgress.assessmentRequired && levelProgress.nextLevel) {
      return <>Bạn đã hoàn thành nội dung. Hãy làm <strong>Level Assessment</strong> để mở khóa {levelProgress.nextLevel}.</>;
    }
    return "Tiếp tục lộ trình học để mở cấp độ tiếp theo.";
  })();

  return (
    <div className="sv-page sv-dashboard">
      <div className="sv-hero">
        <div className="sv-hero-content">
          <span className="sv-hero-kicker">KHÔNG GIAN HỌC TẬP CỦA BẠN</span>
          <h1>Chào {firstName},<br/><span>học thêm một chút nhé.</span></h1>
          <p>Từ vựng dễ nhớ hơn khi bạn học đúng kỹ năng và ôn tập đúng lúc.</p>
          {(levelProgress || state.loading) && <div className="sv-hero-words">
            <div className="sv-hero-level-row">
              <span className="sv-hero-level-label">Trình độ hiện tại (CEFR)</span>
              <span className="sv-hero-level-value">{state.user?.learning_level ?? user?.learning_level ?? progress.level ?? "—"}</span>
            </div>
            <span>{state.loading ? "Đang tải lộ trình học tập..." : levelMessage}</span>
          </div>}
          <div className="sv-hero-actions">
            <Link className="sv-btn sv-btn-light" to={nextLesson ? `/lessons/${nextLesson.slug || nextLesson.id}?unit=${nextLesson.next_unit || 1}` : "/learn"}>Tiếp tục học <span>→</span></Link>
          </div>
        </div>
        <div className="sv-hero-art" aria-hidden="true"><div className="sv-art-orbit sv-art-orbit-one"/><div className="sv-art-orbit sv-art-orbit-two"/><div className="sv-art-card sv-art-card-one"><span>Meaning</span><b>◎</b></div><div className="sv-art-card sv-art-card-two"><span>Spelling</span><b>✦</b></div><div className="sv-art-card sv-art-card-three"><span>Context</span><b>▤</b></div></div>
      </div>

      {state.loading && <PageLoading label="Đang tải tiến độ học tập..." />}
      {!state.loading && state.error && <PageError message={state.error} onRetry={() => setRefresh((value) => value + 1)} />}
      {!state.loading && !state.error && <>
        {state.secondaryError && <div className="sv-notice" role="status">{state.secondaryError} <button type="button" onClick={() => setRefresh((value) => value + 1)}>Tải lại</button></div>}

        <AIStudyCoachCard plan={state.daily} nextLesson={nextLesson} />
        <DailyPlanCard plan={state.daily} />

        <div className="sv-stats-grid">
          <StatTile label="Từ đã bắt đầu học" value={progress.words_learned ?? "—"} note="Đã luyện tập hoặc ôn tập" icon="Aa" tone="blue"/>
          <StatTile label="Từ đã thành thạo" value={progress.words_mastered ?? "—"} note="Đạt cả 3 kỹ năng" icon="✓" tone="green"/>
          <StatTile label="Cần ôn hôm nay" value={due ?? "—"} note="Theo lịch FSRS" icon="↻" tone="amber"/>
          <StatTile label="XP tích lũy" value={progress.xp ?? "—"} note={`Cấp độ ${progress.level ?? "—"} · ${progress.streak ?? "—"} ngày liên tiếp`} icon="✦" tone="violet"/>
        </div>

        <div className="sv-two-col">
          <section className="sv-panel">
            <SectionHeading eyebrow="BẮT ĐẦU Ở ĐÂY" title="Bài học tiếp theo"/>
            {nextLesson ? <Link to={`/lessons/${nextLesson.slug || nextLesson.id}?unit=${nextLesson.next_unit || 1}`} className="sv-next-lesson"><span className="sv-next-icon">{domainOf(nextLesson.topic)?.glyph || "Aa"}</span><span><strong>{nextLesson.title}</strong><small>Bài {nextLesson.next_unit || 1}/{nextLesson.unit_count || 1} · {nextLesson.next_unit_word_count || 15} từ · {nextLesson.level}</small></span><span className="sv-next-arrow">→</span></Link>
              : <EmptyState title="Chưa có bài học phù hợp" description="Hãy khám phá lộ trình hoặc cập nhật lĩnh vực quan tâm."><Link to="/learn" className="sv-btn sv-btn-primary">Xem lộ trình</Link></EmptyState>}
          </section>
          <section className="sv-panel sv-panel-tinted">
            <SectionHeading eyebrow="ÔN TẬP THÔNG MINH" title="Đến hạn ôn tập"/>
            <div className="sv-review-callout"><div className="sv-due-number">{due ?? "—"}</div><p>từ đang chờ được ôn theo thuật toán FSRS.</p></div>
            <Link className="sv-btn sv-btn-primary sv-btn-full" to="/flashcards">Mở bộ thẻ ôn tập →</Link>
          </section>
        </div>
      </>}
    </div>
  );
}
