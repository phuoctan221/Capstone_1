export const DOMAINS = [
  { id: "general", label: "General English", subtitle: "Tiếng Anh giao tiếp hằng ngày", glyph: "Aa", tone: "blue" },
  { id: "technology", label: "IT & Technology", subtitle: "Từ vựng công nghệ và kỹ thuật", glyph: "</>", tone: "violet" },
  { id: "business", label: "Business English", subtitle: "Tiếng Anh môi trường công việc", glyph: "↗", tone: "amber" },
];

export const SKILLS = [
  { id: "meaning", label: "Meaning", subtitle: "Nhận biết nghĩa", glyph: "◎", tone: "blue" },
  { id: "spelling", label: "Spelling", subtitle: "Viết chính xác", glyph: "⌨", tone: "violet" },
  { id: "context", label: "Context", subtitle: "Dùng từ trong câu", glyph: "▤", tone: "amber" },
];

export function domainOf(topic) {
  return DOMAINS.find((domain) => domain.id === String(topic || "").toLowerCase());
}

export function myDomains(user) {
  const interests = Array.isArray(user?.interests)
    ? user.interests.map((value) => String(value || "").toLowerCase())
    : [];
  return DOMAINS.filter((domain) => interests.includes(domain.id));
}

export function isAdmin(user) {
  return user?.role === "admin";
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatApiError(error, fallback = "Không thể tải dữ liệu. Vui lòng thử lại.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join("; ") || fallback;
  if (!error?.response) return "Không kết nối được backend. Kiểm tra FastAPI và kết nối mạng.";
  return fallback;
}

export function clampPercent(value) {
  return Math.min(100, Math.max(0, Number(value) || 0));
}

export function formatPercent(value) {
  return Math.round(clampPercent(value) * 10) / 10;
}
