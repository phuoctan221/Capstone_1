import PronunciationPreview from "./PronunciationPreview";

const validScore = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
const level = score => score < 60 ? "Cần luyện thêm" : score < 80 ? "Cần đọc rõ hơn" : "Đọc tốt";
const soundKey = value => typeof value === "string" ? value.trim().toLowerCase().replace(/[012]$/, "") : "";
const phonetics = { ih: "ɪ", iy: "iː", eh: "ɛ", ae: "æ", ah: "ʌ", ax: "ə", aa: "ɑ", ao: "ɔ", uh: "ʊ", uw: "uː", er: "ɝ", ey: "eɪ", ay: "aɪ", oy: "ɔɪ", aw: "aʊ", ow: "oʊ", sh: "ʃ", zh: "ʒ", th: "θ", dh: "ð", ch: "tʃ", jh: "dʒ", ng: "ŋ", hh: "h" };
const soundLabel = value => phonetics[soundKey(value)] || value;

function phoneFeedback(phone) {
  const expected = soundKey(phone.phone);
  const heard = soundKey(phone.recognized_phone);
  const scored = validScore(phone.quality_score);
  const compared = Boolean(expected && heard);
  const differs = compared && expected !== heard;
  return { ...phone, compared, differs, scored, weak: differs || (scored && phone.quality_score < 80) };
}

export default function SpeakingFeedback({ result, disabled }) {
  if (result.status === "retry") {
    return <div className="speaking-feedback">
      <h4>Cách luyện lại</h4>
      <p>Chưa xác định được âm nào cần sửa trong lần đọc này.</p>
      <ol><li>Nghe mẫu và nhìn kỹ từ/cụm từ cần đọc.</li><li>Đọc chậm từng từ, chú ý đọc đủ âm đầu và âm cuối.</li><li>Thu âm lại toàn bộ nội dung ở nơi yên tĩnh.</li></ol>
    </div>;
  }
  const words = Array.isArray(result.words) ? result.words : [];
  const metrics = result.assessment_details || {};
  const dimensions = [
    ["Độ chính xác", metrics.accuracy, "Nghe mẫu rồi đọc chậm, tập trung vào từng âm."],
    ["Đọc đủ nội dung", metrics.integrity, "Đọc đủ các từ theo đúng thứ tự, tránh bỏ sót từ."],
    ["Độ trôi chảy", metrics.fluency, "Luyện từng cụm ngắn, sau đó nối lại và hạn chế ngập ngừng."],
  ].filter(([, score]) => validScore(score));
  return <section className="speaking-feedback" aria-label="Nhận xét phát âm">
    <h4>Nhận xét và cách cải thiện</h4>
    {dimensions.length > 0 && <div className="speaking-metrics">{dimensions.map(([label, score, tip]) => <div key={label}>
      <strong>{label}: {Math.round(score)}/100</strong>
      <p>{score < 80 ? tip : "Bạn đang làm tốt phần này."}</p>
    </div>)}</div>}
    {words.length === 0 && <p>Chưa có nhận xét chi tiết từng âm cho lần đọc này. Bạn hãy nghe mẫu, đọc chậm và thu âm lại để so sánh.</p>}
    {words.map((word, index) => {
      const phones = (Array.isArray(word.phone_score_list) ? word.phone_score_list : []).filter(p => p.phone).map(phoneFeedback);
      const weak = phones.filter(p => p.weak);
      const allMatched = phones.length > 0 && phones.every(p => p.compared && !p.differs && !p.weak);
      const score = validScore(word.quality_score) ? word.quality_score : null;
      return <article className="speaking-word-feedback" key={`${word.word}-${index}`}>
        <div className="speaking-word-heading"><strong>{word.word}</strong><span>{score !== null ? `${Math.round(score)}/100 · ${level(score)}` : weak.length ? `${weak.length} âm cần luyện lại` : allMatched ? "Các âm đã khớp với từ cần đọc" : "Nhận xét từng âm"}</span></div>
        {phones.length > 0 && <ul className="speaking-phones" aria-label={`Các âm trong từ ${word.word}`}>{phones.map((phone, i) => <li key={i} className={phone.weak ? "needs-practice" : phone.scored || phone.compared ? "good" : "unrated"}>
          <strong>/{soundLabel(phone.phone)}/</strong>: {phone.scored ? `${Math.round(phone.quality_score)}/100 · ${level(phone.quality_score)}` : phone.compared ? phone.differs ? `Cần luyện lại · nghe gần /${soundLabel(phone.recognized_phone)}/` : "Đã đọc khớp" : "Chưa nghe rõ âm này"}
          {phone.scored && phone.differs && <span> · Nghe gần /{soundLabel(phone.recognized_phone)}/</span>}
        </li>)}</ul>}
        {weak.length > 0 ? <p><strong>Ưu tiên luyện: {weak.map(p => `/${soundLabel(p.phone)}/`).join(", ")}.</strong> Nghe mẫu của từ “{word.word}”, tập chậm các âm này rồi đọc lại cả từ.</p>
          : score !== null && score < 80 ? <p>Từ “{word.word}” cần đọc rõ hơn. Chưa có đủ nhận xét để chỉ ra âm sai cụ thể; hãy nghe mẫu và đọc lại từng âm chậm hơn.</p>
          : allMatched ? <p>Bạn đã đọc khớp các âm trong từ “{word.word}”. Chưa ghi nhận âm cần sửa trong lần đọc này. Hãy luyện nói cả từ liền mạch rồi đặt vào một cụm ngắn.</p>
          : score !== null && score >= 80 ? <p>Tiếp tục giữ cách đọc rõ ràng và luyện từ này trong một cụm ngắn.</p>
          : <p>Chưa có đủ nhận xét từng âm. Hãy nghe mẫu rồi đọc lại để so sánh.</p>}
        {(weak.length > 0 || (score !== null && score < 80)) && <PronunciationPreview text={word.word} disabled={disabled} />}
      </article>;
    })}
    {words.some(w => validScore(w.quality_score) || w.phone_score_list?.some(p => validScore(p.quality_score))) && <p className="speaking-feedback-note">Gợi ý luyện tập: dưới 60 điểm cần luyện thêm; 60–79 cần đọc rõ hơn; từ 80 là đọc tốt.</p>}
  </section>;
}
