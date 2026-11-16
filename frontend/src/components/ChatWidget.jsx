import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { sendChatMessage } from "../services/chatService";
import { formatApiError } from "../constants/domains";

const STORAGE_KEY = "sv_learning_assistant_history";
const MAX_HISTORY = 8;

const PAGE_BY_PATH = [
  ["/flashcards", "flashcards"],
  ["/vocabulary", "vocabulary"],
  ["/speaking", "speaking"],
  ["/quiz", "quiz"],
  ["/lessons", "lesson"],
  ["/progress", "progress"],
  ["/learn", "learn"],
  ["/dashboard", "dashboard"],
];

function pageFor(pathname) {
  return PAGE_BY_PATH.find(([path]) => pathname.includes(path))?.[1] || "dashboard";
}

function loadHistory() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((item) => item?.role && item?.content).slice(-MAX_HISTORY)
      : [];
  } catch {
    return [];
  }
}

export default function ChatWidget() {
  const user = useAuth();
  const { pathname } = useLocation();
  const page = useMemo(() => pageFor(pathname), [pathname]);
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState(loadHistory);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-MAX_HISTORY)));
    } catch {
      // Session persistence is optional.
    }
  }, [messages]);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading, open]);

  async function send(text = input) {
    const message = String(text || "").trim();
    if (!message || loading) return;
    const nextMessages = [...messages, { role: "user", content: message }].slice(-MAX_HISTORY);
    setMessages(nextMessages);
    setInput("");
    setError("");
    setLoading(true);
    try {
      const result = await sendChatMessage({
        message,
        history: messages.slice(-MAX_HISTORY),
        context: { page },
      });
      setMessages((current) => [...current, { role: "assistant", content: result.message }].slice(-MAX_HISTORY));
    } catch (err) {
      setError(formatApiError(err, "Trợ lý AI tạm thời chưa phản hồi được. Vui lòng thử lại."));
    } finally {
      setLoading(false);
    }
  }

  const starters = page === "vocabulary"
    ? ["Giải thích một từ tiếng Anh", "Phân biệt hai từ"]
    : page === "quiz"
      ? ["Giải thích cách làm dạng câu này", "Cho một ví dụ tương tự"]
      : ["Hôm nay nên ôn gì?", "Giúp mình sửa một câu"];

  return (
    <div className="sv-chat-widget">
      {open && (
        <section className="sv-chat-panel" aria-label="Trợ lý học tập AI">
          <header className="sv-chat-header">
            <div><span className="sv-chat-mark" aria-hidden="true">✦</span><div><b>Trợ lý SmartVocab</b><small>Hỗ trợ học tiếng Anh</small></div></div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Đóng trợ lý học tập">×</button>
          </header>
          <div className="sv-chat-body" aria-live="polite">
            {!messages.length && (
              <div className="sv-chat-welcome">
                <strong>Chào {user?.username || "bạn"}! 👋</strong>
                <p>Mình có thể giải thích từ vựng, ngữ pháp và gợi ý cách ôn tập.</p>
                <div className="sv-chat-starters">{starters.map((item) => <button key={item} type="button" onClick={() => send(item)} disabled={loading}>{item}</button>)}</div>
              </div>
            )}
            {messages.map((item, index) => <article className={`sv-chat-message ${item.role}`} key={`${item.role}-${index}-${item.content.slice(0, 20)}`}><span>{item.content}</span></article>)}
            {loading && <article className="sv-chat-message assistant sv-chat-typing"><span><i /> <i /> <i /></span></article>}
            {error && <div className="sv-chat-error" role="alert">{error}</div>}
            <div ref={bottomRef} />
          </div>
          <form className="sv-chat-input" onSubmit={(event) => { event.preventDefault(); send(); }}>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Nhập câu hỏi về tiếng Anh..." maxLength={1200} rows={1} disabled={loading} aria-label="Tin nhắn cho trợ lý" />
            <button type="submit" disabled={!input.trim() || loading} aria-label="Gửi tin nhắn">➤</button>
          </form>
          <footer>AI có thể sai; hãy đối chiếu với bài học khi cần.</footer>
        </section>
      )}
      <button type="button" className="sv-chat-launcher" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-label={open ? "Đóng trợ lý học tập" : "Mở trợ lý học tập"}>
        {open ? "×" : "✦"}<span>Trợ lý học tập</span>
      </button>
    </div>
  );
}