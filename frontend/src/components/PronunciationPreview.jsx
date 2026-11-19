import { useEffect, useId, useRef, useState } from "react";

export default function PronunciationPreview({ text, disabled }) {
  const [voices, setVoices] = useState([]);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [volume, setVolume] = useState(100);
  const volumeId = useId();
  const previousVolume = useRef(100);
  const active = useRef(null);
  const pending = useRef(null);
  const [playbackRate, setPlaybackRate] = useState(1);
  const supported = typeof window.speechSynthesis !== "undefined" && typeof window.SpeechSynthesisUtterance !== "undefined";

  function stop() {
    clearTimeout(pending.current);
    pending.current = null;
    if (active.current) {
      active.current = null;
      window.speechSynthesis.cancel();
    }
    setPlaying(false);
  }

  useEffect(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const refresh = () => setVoices(synth.getVoices().filter(v => /^en([-_]|$)/i.test(v.lang)));
    refresh();
    synth.addEventListener("voiceschanged", refresh);
    return () => {
      synth.removeEventListener("voiceschanged", refresh);
      clearTimeout(pending.current);
      if (active.current) { active.current = null; synth.cancel(); }
    };
  }, [supported]);

  useEffect(() => {
    stop();
    setError("");
  }, [text, disabled]);

  function play(rate, playbackVolume = volume) {
    stop();
    setError("");
    if (!supported || disabled) return;
    // Re-read because some browsers load installed voices only after interaction.
    const available = window.speechSynthesis.getVoices().filter(v => /^en([-_]|$)/i.test(v.lang));
    const voice = available.find(v => v.localService && /^en[-_]US$/i.test(v.lang))
      || available.find(v => /^en[-_]US$/i.test(v.lang)) || available[0];
    if (!voice) {
      setError("Chưa tìm thấy giọng tiếng Anh. Hãy bật/cài giọng English trong thiết bị hoặc thử trình duyệt khác.");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.rate = rate;
    utterance.volume = playbackVolume / 100;
    active.current = utterance;
    setPlaybackRate(rate);
    setPlaying(true);
    utterance.onend = () => {
      if (active.current === utterance) { active.current = null; setPlaying(false); }
    };
    utterance.onerror = event => {
      if (active.current !== utterance) return;
      active.current = null; setPlaying(false);
      if (!["canceled", "interrupted"].includes(event.error)) setError("Không phát được âm mẫu. Kiểm tra âm lượng và thử lại.");
    };
    window.speechSynthesis.cancel();
    // Let cancellation finish before switching speed or replaying a sample.
    pending.current = setTimeout(() => {
      pending.current = null;
      if (active.current !== utterance) return;
      window.speechSynthesis.resume();
      window.speechSynthesis.speak(utterance);
    }, 100);
  }

  function changeVolume(value) {
    const next = Math.max(0, Math.min(100, Number(value)));
    const rate = active.current?.rate;
    setVolume(next);
    if (next > 0) previousVolume.current = next;
    // Restart the short sample: changing an active utterance is not reliable across browsers.
    if (rate != null) {
      if (next === 0) stop();
      else play(rate, next);
    }
  }

  return <div className="pronunciation-preview">
    <h3>Nghe phát âm mẫu</h3>
    <p>Nghe từ/cụm từ trên bằng giọng tiếng Anh trước khi luyện nói.</p>
    <div className="speaking-actions">
      <button type="button" className="btn" disabled={disabled || !supported} onClick={() => play(1)}>▶ Nghe mẫu</button>
      <button type="button" className="btn" disabled={disabled || !supported} aria-pressed={playing && playbackRate < 1} onClick={() => play(0.55)}>Nghe chậm (0,55×)</button>
      {playing && <button type="button" className="btn" onClick={stop}>Dừng nghe</button>}
    </div>
    <div className="pronunciation-volume">
      <button type="button" className="btn" disabled={disabled || !supported} onClick={() => changeVolume(volume === 0 ? previousVolume.current : 0)} aria-label={volume === 0 ? "Bật âm mẫu" : "Tắt âm mẫu"} aria-pressed={volume === 0}>
        {volume === 0 ? "Bật âm" : "Tắt âm"}
      </button>
      <label htmlFor={volumeId}>Âm lượng</label>
      <input id={volumeId} type="range" min="0" max="100" step="5" value={volume} onChange={e => changeVolume(e.target.value)} disabled={disabled || !supported} aria-valuetext={`${volume}%`} />
      <output htmlFor={volumeId}>{volume}%</output>
    </div>
    {playing && <p role="status">{playbackRate < 1 ? "Đang phát âm chậm…" : "Đang phát âm mẫu…"}</p>}
    {!supported && <p role="status">Trình duyệt chưa hỗ trợ đọc mẫu. Hãy thử Chrome, Edge hoặc Safari.</p>}
    {supported && <small>Giọng đọc tổng hợp của thiết bị · {voices.some(v => /^en[-_]US$/i.test(v.lang)) ? "Tiếng Anh Mỹ" : "Tiếng Anh"}</small>}
    {error && <p role="alert" className="speaking-error">{error}</p>}
  </div>;
}
