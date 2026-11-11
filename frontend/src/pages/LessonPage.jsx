import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchLesson } from "../services/lessonService";
import { SKILLS, formatPercent, domainOf, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading, SectionHeading } from "../components/PageState";

export default function LessonPage() {
  const { lessonId } = useParams();
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchLesson(lessonId).then((data) => { if (active) { setLesson(data); setError(""); } })
      .catch((err) => { if (active) setError(formatApiError(err, "Không tìm thấy bài học.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [lessonId, refresh]);

  if (loading) return <PageLoading label="Đang chuẩn bị bài học..."/>;
  if (error) return <PageError message={error} onRetry={() => setRefresh((value) => value + 1)}/>;
  if (!lesson) return <EmptyState title="Không tìm thấy bài học" description="Bài học này hiện không khả dụng."/>;

  const words = Array.isArray(lesson.words) ? lesson.words : [];
  const total = Number(lesson.word_count ?? words.length);
  const learned = Number(lesson.learned_count ?? 0);
  const percent = total ? formatPercent((learned / total) * 100) : 0;
  const domain = domainOf(lesson.topic);

  return <div className="sv-page">
    <div className="sv-breadcrumb"><Link to="/learn">Lộ trình</Link><span>/</span><span>{domain?.label || lesson.topic}</span><span>/</span><b>{lesson.level}</b></div>
    <div className="sv-lesson-hero"><div className="sv-lesson-hero-main"><span className="sv-eyebrow">BÀI HỌC · {lesson.level}</span><h1>{lesson.title}</h1><p>Học từ mới qua ba kỹ năng độc lập: nghĩa, chính tả và ngữ cảnh.</p><div className="sv-lesson-meta"><span>{total} từ vựng</span><span>{learned} từ đã học</span><span>{percent}% tiến độ</span></div></div><div className="sv-lesson-hero-progress"><strong>{percent}%</strong><span>Tiến độ bài học</span><div className="sv-lesson-meter"><div style={{width:`${percent}%`}}/></div></div></div>

    <SectionHeading eyebrow="RÈN LUYỆN MỖI KỸ NĂNG" title="Chọn một cách luyện tập" description="Kết quả được chấm tại backend và cập nhật Mastery riêng cho từng kỹ năng."/>
    <div className="sv-skill-grid">{SKILLS.map((skill) => <Link key={skill.id} to={`/lessons/${lessonId}/practice/${skill.id}`} className={`sv-skill-card sv-tone-${skill.tone}`}><span className="sv-skill-glyph">{skill.glyph}</span><span className="sv-skill-index">0{SKILLS.indexOf(skill)+1} / 03</span><h3>{skill.label}</h3><p>{skill.subtitle}</p><span className="sv-skill-action">Bắt đầu luyện →</span></Link>)}</div>

    <div className="sv-two-col sv-lesson-bottom-grid">
      <section className="sv-panel"><SectionHeading title="Kiểm tra cuối bài" description="Trắc nghiệm tổng hợp, tính điểm và XP qua backend."/><p className="sv-panel-help">{words.length < 2 ? "Cần thêm từ vựng để mở bài kiểm tra." : `Gồm tối đa ${Math.min(10, words.length)} câu hỏi theo nội dung bài học.`}</p><Link to={`/lessons/${lessonId}/quiz`} className={`sv-btn sv-btn-primary${words.length < 2 ? " sv-link-disabled" : ""}`} aria-disabled={words.length < 2} onClick={words.length < 2 ? (e) => e.preventDefault() : undefined}>Làm bài kiểm tra →</Link></section>
      <section className="sv-panel"><SectionHeading title="Thông tin bài học"/><div className="sv-detail-row"><span>Lĩnh vực</span><b>{domain?.label || lesson.topic}</b></div><div className="sv-detail-row"><span>Trình độ</span><b>{lesson.level}</b></div><div className="sv-detail-row"><span>Số từ</span><b>{total}</b></div><div className="sv-detail-row"><span>Tiến độ</span><b>{percent}%</b></div></section>
    </div>

    <SectionHeading eyebrow="TÀI LIỆU HỌC" title="Từ vựng trong bài" description="Danh sách từ và ví dụ để bạn xem trước khi luyện."/>
    {words.length ? <div className="sv-word-grid">{words.map((word, index) => <article className="sv-word-card" key={word.id}><div className="sv-word-count">{String(index+1).padStart(2,"0")}</div><h3>{word.word}</h3>{word.phonetic && <small>{word.phonetic}</small>}<p>{word.meaning}</p>{word.example && <blockquote>{word.example}</blockquote>}</article>)}</div> : <EmptyState title="Bài học chưa có từ vựng" description="Hãy bổ sung vocabulary trong database trước khi kiểm thử."/>}
  </div>;
}
