import { Link } from "react-router-dom";

function wordsLabel(words) {
  const items = Array.isArray(words) ? words.filter((item) => item?.word).slice(0, 4) : [];
  return items;
}

export default function AIStudyCoachCard({ plan, nextLesson }) {
  if (!plan) return null;

  const dueCount = Number(plan.due_count) || 0;
  const remaining = Number(plan.remaining) || 0;
  const newCount = Number(plan.new_count) || 0;
  const streak = Number(plan.streak) || 0;
  const goalMet = Boolean(plan.goal_met);
  let coach;

  if (dueCount > 0) {
    coach = {
      tone: "review",
      icon: "↻",
      label: "ƯU TIÊN CỦA SMARTVOCAB AI",
      title: "Ôn tập trước để giữ từ trong trí nhớ",
      message: `Bạn có ${dueCount} từ đã đến hạn theo lịch FSRS. Ôn đúng lúc giúp giảm nguy cơ quên và giữ lộ trình nhẹ nhàng hơn.`,
      action: "Ôn ngay với FSRS",
      href: "/flashcards",
      facts: [`${dueCount} từ đến hạn`, `${plan.review_limit || dueCount} từ/lượt ôn`, streak ? `Chuỗi ${streak} ngày` : "Bắt đầu chuỗi hôm nay"],
      previewLabel: "Nên ôn trước",
      preview: wordsLabel(plan.due_preview),
    };
  } else if (!goalMet && newCount > 0) {
    coach = {
      tone: "learn",
      icon: "✦",
      label: "GỢI Ý HỌC HÔM NAY",
      title: "Hoàn thành một mục tiêu nhỏ hôm nay",
      message: `Bạn còn ${remaining} từ để đạt mục tiêu hôm nay. SmartVocab AI đã chọn ${newCount} từ mới phù hợp với lộ trình hiện tại của bạn.`,
      action: "Học từ mới",
      href: plan.next_lesson?.href || (nextLesson ? `/lessons/${nextLesson.slug || nextLesson.id}?unit=${nextLesson.next_unit || 1}` : "/learn"),
      facts: [`Còn ${remaining}/${plan.goal} từ`, `${newCount} từ mới phù hợp`, streak ? `Chuỗi ${streak} ngày` : "Học để bắt đầu chuỗi"],
      previewLabel: "Từ mới gợi ý",
      preview: wordsLabel(plan.new_preview),
    };
  } else if (goalMet) {
    coach = {
      tone: "complete",
      icon: "✓",
      label: "NHẬN XÉT TỪ SMARTVOCAB AI",
      title: "Bạn đang duy trì nhịp học rất tốt",
      message: streak > 1
        ? `Bạn đã hoàn thành mục tiêu hôm nay và duy trì chuỗi ${streak} ngày. Hãy xem lại tiến độ để chọn bước tiếp theo phù hợp.`
        : "Bạn đã hoàn thành mục tiêu hôm nay. Một nhịp học đều đặn sẽ hiệu quả hơn việc học dồn vào một ngày.",
      action: "Xem tiến độ học",
      href: "/progress",
      facts: [`Đã học ${plan.studied_today}/${plan.goal} từ`, `${plan.xp_today || 0} XP hôm nay`, streak ? `Chuỗi ${streak} ngày` : "Hoàn thành ngày đầu tiên"],
      previewLabel: "Bạn đã xử lý hôm nay",
      preview: [],
    };
  } else if (nextLesson) {
    coach = {
      tone: "continue",
      icon: "→",
      label: "GỢI Ý HỌC HÔM NAY",
      title: "Tiếp tục với bài học phù hợp nhất",
      message: `Hiện không có từ đến hạn. Hãy học một bài ngắn để xây nền từ vựng và giữ thói quen học đều đặn.`,
      action: "Mở bài học tiếp theo",
      href: `/lessons/${nextLesson.slug || nextLesson.id}?unit=${nextLesson.next_unit || 1}`,
      facts: [nextLesson.level ? `Cấp độ ${nextLesson.level}` : "Theo lộ trình của bạn", streak ? `Chuỗi ${streak} ngày` : "Bắt đầu học hôm nay", "Không có từ đến hạn"],
      previewLabel: "Bài học được đề xuất",
      preview: [],
    };
  } else {
    coach = {
      tone: "start",
      icon: "✦",
      label: "SMARTVOCAB AI ĐỒNG HÀNH",
      title: "Bắt đầu xây lộ trình học của bạn",
      message: "Hãy chọn một bài học để SmartVocab AI có dữ liệu cá nhân hóa kế hoạch ôn tập và gợi ý học cho bạn.",
      action: "Khám phá lộ trình",
      href: "/learn",
      facts: ["Chọn bài học đầu tiên", "Tạo lịch ôn FSRS", "Theo dõi tiến độ cá nhân"],
      previewLabel: "Bước đầu tiên",
      preview: [],
    };
  }

  return (
    <section className={`sv-ai-coach sv-ai-coach-${coach.tone}`} aria-labelledby="sv-ai-coach-title">
      <div className="sv-ai-coach-mark" aria-hidden="true">{coach.icon}</div>
      <div className="sv-ai-coach-main">
        <span className="sv-ai-coach-label">{coach.label}</span>
        <h2 id="sv-ai-coach-title">{coach.title}</h2>
        <p>{coach.message}</p>
        <div className="sv-ai-coach-facts" aria-label="Dữ liệu dùng để đưa ra gợi ý">
          {coach.facts.map((fact) => <span key={fact}>{fact}</span>)}
        </div>
        {coach.preview.length > 0 && (
          <div className="sv-ai-coach-preview">
            <span>{coach.previewLabel}</span>
            {coach.preview.map((word) => <b key={word.vocabulary_id || word.word}>{word.word}</b>)}
          </div>
        )}
      </div>
      <Link className="sv-btn sv-ai-coach-action" to={coach.href}>{coach.action} <span aria-hidden="true">→</span></Link>
    </section>
  );
}