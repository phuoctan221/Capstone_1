import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { fetchLessons } from "../services/lessonService";
import { myDomains, clampPercent, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading, SectionHeading } from "../components/PageState";
import { useAuth } from "../hooks/useAuth";
import ConfirmDialog from "../components/ConfirmDialog";

export default function LearnPage() {
  const user = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const chosen = myDomains(user);
  const requestedDomain = params.get("domain");
  const domain = chosen.some((item) => item.id === requestedDomain) ? requestedDomain : "all";
  const [lessons, setLessons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [skipTarget, setSkipTarget] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchLessons().then((data) => {
      if (active) { setLessons(Array.isArray(data) ? data : []); setError(""); }
    }).catch((err) => { if (active) setError(formatApiError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  const chosenIds = useMemo(() => new Set(chosen.map((item) => item.id)), [user?.interests]);
  const shown = useMemo(() => lessons.filter((lesson) =>
    chosenIds.has(lesson.topic) && (domain === "all" || lesson.topic === domain)
  ), [lessons, domain, chosenIds]);

  const changeDomain = (value) => setParams(value === "all" ? {} : { domain: value });
  const startSkipAssessment = () => {
    if (!skipTarget) return;
    navigate(`/assessments/${skipTarget.domain}/${skipTarget.targetLevel}?skip=1&placement=1`);
    setSkipTarget(null);
  };

  if (loading) return <PageLoading label="Đang tải lộ trình học..." />;
  if (error) return <PageError message={error} onRetry={() => setRefresh((value) => value + 1)} />;

  return <div className="sv-page">
    <div className="sv-page-heading"><div><span className="sv-eyebrow">THIẾT KẾ CHO BẠN</span><h1>Lộ trình từ vựng</h1><p>Học theo lĩnh vực, tiến bộ theo từng cấp độ.</p></div><Link to="/flashcards" className="sv-btn sv-btn-outline">Ôn tập FSRS ↗</Link></div>

    {chosen.length === 0 ? <EmptyState title="Chưa chọn lĩnh vực quan tâm" description="Chọn lĩnh vực quan tâm để lộ trình học hiển thị đúng nội dung cho bạn."><Link className="sv-btn sv-btn-primary" to="/settings/learning">Chọn lĩnh vực</Link></EmptyState> : <>
      {chosen.length > 1 && (
        <div className="sv-filter-row" role="group" aria-label="Lọc lĩnh vực">
          {[{ id: "all", label: "Tất cả" }, ...chosen].map((item) => <button key={item.id} type="button" className={`sv-filter-pill${domain === item.id ? " active" : ""}`} onClick={() => changeDomain(item.id)}>{item.label}</button>)}
        </div>
      )}

      {chosen.filter((item) => domain === "all" || item.id === domain).map((item) => {
        const group = shown.filter((lesson) => lesson.topic === item.id).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
        return <section className="sv-domain-section" key={item.id}>
          <SectionHeading title={item.label} description={item.subtitle} action={<span className="sv-muted-small">{group.length} bài học</span>}/>
          {group.length === 0 ? <div className="sv-inline-empty">Chưa có bài học cho lĩnh vực này. Hãy kiểm tra dữ liệu Vocabulary và cấp độ.</div> :
            <div className="sv-lessons-grid">{group.map((lesson, index) => {
              const locked = lesson.unlocked === false || !lesson.word_count;
              const reviewOnly = lesson.review_only === true;
              const requirement = lesson.unlock_requirement;
              const unitCount = lesson.unit_count || 0;
              const nextUnit = lesson.next_unit || 1;
              const nextWords = lesson.next_unit_word_count || 0;
              const slug = lesson.slug || lesson.id;
              return <div key={slug} className={`sv-lesson-card${locked ? " is-disabled" : ""}`} aria-disabled={locked}>
                <div className="sv-lesson-top"><span className="sv-level-tag">{lesson.level}</span><span className={`sv-status-tag${lesson.completed ? " success" : ""}`}>{lesson.completed ? "Đã hoàn thành" : reviewOnly ? "Ôn tập" : locked ? "Đã khóa" : lesson.recommended ? "Đang học" : "Có thể học"}</span></div>
                <div className="sv-lesson-num">BÀI {String(index + 1).padStart(2,"0")} · {unitCount} UNIT</div><h3>{lesson.title}</h3><p>{lesson.description || `${lesson.word_count} từ vựng cấp độ ${lesson.level}`}</p>
                <div className="sv-lesson-meter"><div style={{ width: `${clampPercent(lesson.progress_percent)}%` }}/></div>
                <div className="sv-lesson-bottom"><span>{lesson.learned_count ?? 0}/{lesson.word_count} từ đã học</span><strong>{locked ? "—" : "→"}</strong></div>
                <div className="sv-unit-strip">
                  {locked ? requirement
                    ? <><span className="sv-unit-next">Cần đạt {requirement.level} trước khi học {lesson.level}</span><button type="button" className="sv-unit-continue sv-skip-level-button" onClick={() => setSkipTarget({ domain: lesson.domain, level: requirement.level, targetLevel: lesson.level })}>Học vượt →</button></>
                    : <span className="sv-unit-next">Chưa khả dụng</span>
                    : <><span className="sv-unit-next">{reviewOnly ? "Nội dung dưới mốc hiện tại" : `Bài ${nextUnit}/${unitCount || 1} · ${nextWords} từ`}</span><Link className="sv-unit-continue" to={`/lessons/${slug}?unit=${nextUnit}`}>{reviewOnly ? "Ôn tập →" : "Học tiếp →"}</Link></>}
                </div>
                {!locked && lesson.assessment_required && <Link className="sv-assessment-cta" to={`/assessments/${lesson.domain}/${lesson.level}`}>Hoàn tất Level Assessment để mở {lesson.next_level || "cấp độ tiếp theo"} →</Link>}
                {!locked && unitCount > 1 && <div className="sv-unit-list" aria-label="Danh sách unit">
                  {lesson.units.map((unit) => {
                    const unitLocked = unit.unlocked === false;
                    const label = `Bài ${unit.index} · ${unit.word_count} từ`;
                    return unitLocked
                      ? <span key={unit.index} className="sv-unit-pill is-locked" title={label}>{unit.index}</span>
                      : <Link key={unit.index} className={`sv-unit-pill${unit.completed ? " is-done" : ""}${unit.index === nextUnit ? " is-next" : ""}`} to={`/lessons/${slug}?unit=${unit.index}`} title={label}>{unit.index}</Link>;
                  })}
                </div>}
              </div>;
            })}</div>}
        </section>;
      })}
      {!shown.length && <EmptyState title="Chưa có bài học" description="Nếu tài khoản mới, hãy chọn lĩnh vực quan tâm trong phần cài đặt học tập."><Link className="sv-btn sv-btn-outline" to="/settings/learning">Cài đặt học tập</Link></EmptyState>}
    </>}
    <ConfirmDialog
      open={Boolean(skipTarget)}
      title="Bạn muốn chuyển đến học vượt không?"
      message={skipTarget ? `Bạn sẽ làm bài kiểm tra cấp độ ${skipTarget.level}. Đạt từ 70% để mở khóa cấp độ ${skipTarget.targetLevel}.` : ""}
      confirmText="Làm bài kiểm tra"
      cancelText="Ở lại lộ trình"
      onConfirm={startSkipAssessment}
      onCancel={() => setSkipTarget(null)}
    />
  </div>;
}
