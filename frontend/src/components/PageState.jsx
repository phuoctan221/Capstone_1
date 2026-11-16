export function PageLoading({ label = "Đang tải dữ liệu..." }) {
  return <div className="sv-center-state" role="status"><div className="sv-loader"/><p>{label}</p></div>;
}

export function PageError({ message, onRetry }) {
  return (
    <div className="sv-center-state sv-state-error" role="alert">
      <span className="sv-state-icon">!</span>
      <h2>Đã có sự cố</h2>
      <p>{message}</p>
      {onRetry && <button className="sv-btn sv-btn-primary" onClick={onRetry}>Thử lại</button>}
    </div>
  );
}

export function EmptyState({ title, description, children }) {
  return <div className="sv-empty-state"><span className="sv-empty-glyph" aria-hidden="true">✧</span><h3>{title}</h3><p>{description}</p>{children}</div>;
}

export function SectionHeading({ eyebrow, title, description, action }) {
  return <div className="sv-section-head"><div>{eyebrow && <span className="sv-eyebrow">{eyebrow}</span>}<h2>{title}</h2>{description && <p>{description}</p>}</div>{action && <div className="sv-section-action">{action}</div>}</div>;
}

export function StatTile({ label, value, note, icon, tone = "blue" }) {
  return <div className={`sv-stat sv-tone-${tone}`}><div className="sv-stat-top"><span>{label}</span><span className="sv-stat-glyph" aria-hidden="true">{icon}</span></div><div className="sv-stat-value">{value ?? "—"}</div>{note && <p>{note}</p>}</div>;
}
