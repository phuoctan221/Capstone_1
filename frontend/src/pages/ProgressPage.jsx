import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchProgress } from "../services/lessonService";
import { fetchMasterySummary, fetchProgressHistory } from "../services/progressService";
import { fetchStats } from "../services/learningService";
import { SKILLS, clampPercent, formatApiError } from "../constants/domains";
import { EmptyState, PageError, PageLoading, SectionHeading, StatTile } from "../components/PageState";
import { normalizeHistory, summarizeMastery } from "../services/masteryAdapters";

function dateText(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";
}

export default function ProgressPage() {
  const [data, setData] = useState({ loading: true, progress: null, stats: null, mastery: null, history: [], warning: "", error: "" });
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      setData((old) => ({ ...old, loading: true, error: "" }));
      const res = await Promise.allSettled([fetchProgress(), fetchStats(), fetchMasterySummary(), fetchProgressHistory()]);
      if (!active) return;
      const value = (i) => res[i].status === "fulfilled" ? res[i].value : null;
      const warning = res[2].status === "rejected" || res[3].status === "rejected" ? "API /progress/mastery hoặc /progress/history chưa khả dụng trên backend hiện tại. Không hiển thị dữ liệu ước lượng." : "";
      setData({ loading:false, progress:value(0), stats:value(1), mastery:summarizeMastery(value(2)), history:normalizeHistory(value(3)), warning, error:res[0].status === "rejected" ? formatApiError(res[0].reason) : "" });
    })();
    return () => { active = false; };
  }, [refresh]);

  if (data.loading) return <PageLoading label="Đang tổng hợp kết quả học tập..."/>;
  if (data.error) return <PageError message={data.error} onRetry={() => setRefresh((value)=>value+1)}/>;
  const progress = data.progress || {};
  return <div className="sv-page"><div className="sv-page-heading"><div><span className="sv-eyebrow">HÀNH TRÌNH HỌC TẬP</span><h1>Tiến độ của bạn</h1><p>Theo dõi sự tiến bộ và ba điểm kỹ năng của riêng bạn.</p></div><button className="sv-btn sv-btn-outline" onClick={() => setRefresh((value)=>value+1)}>↻ Làm mới</button></div>
    <div className="sv-stats-grid"><StatTile label="Đã học" value={progress.words_learned ?? "—"} icon="Aa" tone="blue"/><StatTile label="Thành thạo" value={progress.words_mastered ?? "—"} icon="✓" tone="green"/><StatTile label="Bài đã hoàn thành" value={progress.lessons_completed ?? "—"} icon="▤" tone="violet"/><StatTile label="Cần ôn" value={data.stats?.due_today ?? "—"} icon="↻" tone="amber"/></div>
    {data.warning && <div className="sv-notice" role="status">{data.warning}</div>}
    <div className="sv-two-col"><section className="sv-panel"><SectionHeading eyebrow="MULTI-SKILL MASTERY" title="Ba kỹ năng của bạn" description="Giá trị trung bình từ dữ liệu thật do backend trả về."/>
      {data.mastery ? <div className="sv-mastery-list">{SKILLS.map((skill) => <div key={skill.id} className="sv-mastery-row"><div className="sv-mastery-line"><strong>{skill.label}</strong><span>{Math.round(clampPercent(data.mastery[skill.id]))}/100</span></div><div className="sv-lesson-meter"><div style={{width:`${clampPercent(data.mastery[skill.id])}%`}}/></div></div>)}</div> : <EmptyState title="Chưa có dữ liệu Mastery" description="Hãy bắt đầu luyện tập. Nếu đã học, kiểm tra API /progress/mastery trên backend."/>}
    </section><section className="sv-panel"><SectionHeading eyebrow="THÀNH TÍCH" title="Hoạt động gần đây"/><div className="sv-detail-row"><span>Cấp độ hiện tại</span><b>Lv {progress.level ?? "—"}</b></div><div className="sv-detail-row"><span>Tổng XP</span><b>{progress.xp ?? "—"}</b></div><div className="sv-detail-row"><span>Chuỗi ngày học</span><b>{progress.streak ?? "—"}</b></div><div className="sv-detail-row"><span>Lần học gần nhất</span><b>{dateText(progress.last_study_date)}</b></div><Link className="sv-btn sv-btn-primary" style={{marginTop:18}} to="/learn">Tiếp tục học →</Link></section></div>
    <SectionHeading eyebrow="LỊCH SỬ" title="Những lần trả lời gần đây" description="Dữ liệu được lấy từ backend, không tạo lịch sử mẫu."/>
    {data.history.length ? <div className="sv-panel sv-history-table"><div className="sv-history-head"><b>Kỹ năng</b><b>Đáp án</b><b>Kết quả</b><b>Thời gian</b></div>{data.history.slice(0,20).map((item,i)=><div key={item.attempt_id || item.id || i} className="sv-history-row"><span>{item.skill || "—"}</span><span>{item.submitted_answer || item.user_answer || "—"}</span><span className={item.is_correct ?? item.correct ? "sv-text-success" : "sv-text-danger"}>{item.is_correct ?? item.correct ? "Đúng" : "Sai"}</span><span>{dateText(item.answered_at || item.created_at)}</span></div>)}</div> : <EmptyState title="Chưa có lịch sử để hiển thị" description="Làm một bài tập hoặc xác nhận backend cung cấp API /progress/history."/>}
  </div>;
}
