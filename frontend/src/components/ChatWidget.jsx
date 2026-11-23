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

const PAGE_LABEL = {
  flashcards: "Thẻ ghi nhớ",
  vocabulary: "Từ vựng",
  speaking: "Luyện nói",
  quiz: "Trắc nghiệm",
  lesson: "Bài học",
  progress: "Tiến độ",
  learn: "Học tập",
  dashboard: "Tổng quan",
};

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

function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

export default function ChatWidget() {
  const user = useAuth();
  const { pathname } = useLocation();
  const page = useMemo(() => pageFor(pathname), [pathname]);
  const pageLabel = PAGE_LABEL[page] || "Học tập";
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
      setError(formatApiError(err, "Trợ lý học tập tạm thời chưa phản hồi được. Vui lòng thử lại."));
    } finally {
      setLoading(false);
    }
  }

  const starters = page === "vocabulary"
    ? ["Giải thích một từ vựng", "Phân biệt hai từ dễ nhầm lẫn"]
    : page === "quiz"
      ? ["Giải thích cách làm dạng câu này", "Cho một ví dụ tương tự"]
      : ["Gợi ý lộ trình ôn tập hôm nay", "Sửa lỗi giúp mình câu tiếng Anh này"];

  return (
    <div className="sv-chat-widget">
      {open && (
        <section className="sv-chat-panel" aria-label="Trợ lý học tập SmartVocab">
          <header className="sv-chat-header">
            <div className="sv-chat-header-info">
              <span className="sv-chat-mark" aria-hidden="true">
                <ChatIcon />
              </span>
              <div>
                <b>Trợ lý học tập</b>
                <small>SmartVocab Assistant</small>
              </div>
            </div>
            <div className="sv-chat-header-actions">
              <span className="sv-chat-page-tag">{pageLabel}</span>
              <button
                type="button"
                className="sv-chat-close-btn"
                onClick={() => setOpen(false)}
                aria-label="Đóng trợ lý học tập"
              >
                <CloseIcon />
              </button>
            </div>
          </header>

          <div className="sv-chat-body" aria-live="polite">
            {!messages.length && (
              <div className="sv-chat-welcome">
                <div className="sv-chat-welcome-head">
                  <strong>Hỗ trợ học tập</strong>
                  <span className="sv-chat-welcome-user">{user?.username ? `@${user.username}` : "SmartVocab"}</span>
                </div>
                <p>Giải nghĩa từ vựng, phân tích ngữ pháp và gợi ý ôn tập theo ngữ cảnh hiện tại.</p>
                <div className="sv-chat-starters">
                  {starters.map((item) => (
                    <button key={item} type="button" onClick={() => send(item)} disabled={loading}>
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((item, index) => (
              <article
                className={`sv-chat-message ${item.role}`}
                key={`${item.role}-${index}-${item.content.slice(0, 20)}`}
              >
                <span>{item.content}</span>
              </article>
            ))}

            {loading && (
              <article className="sv-chat-message assistant sv-chat-typing">
                <span>
                  <i />
                  <i />
                  <i />
                </span>
              </article>
            )}

            {error && <div className="sv-chat-error" role="alert">{error}</div>}
            <div ref={bottomRef} />
          </div>

          <form
            className="sv-chat-input"
            onSubmit={(event) => {
              event.preventDefault();
              send();
            }}
          >
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
              placeholder="Nhập câu hỏi từ vựng, ngữ pháp..."
              maxLength={1200}
              rows={1}
              disabled={loading}
              aria-label="Tin nhắn cho trợ lý"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Gửi tin nhắn"
            >
              <SendIcon />
            </button>
          </form>

          <footer className="sv-chat-footer">Nội dung do AI tạo; đối chiếu với bài học khi cần.</footer>
        </section>
      )}

      <button
        type="button"
        className={`sv-chat-launcher ${open ? "is-open" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={open ? "Đóng trợ lý học tập" : "Mở trợ lý học tập"}
      >
        <span className="sv-chat-launcher-icon" aria-hidden="true">
          {open ? <CloseIcon /> : <ChatIcon />}
        </span>
        <span className="sv-chat-launcher-label">Trợ lý học tập</span>
      </button>
    </div>
  );
}
