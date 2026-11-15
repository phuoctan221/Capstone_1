import { useEffect, useRef } from "react";
import "./ConfirmDialog.css";

const POWER_ICON = (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <path d="M12 3v8" />
    <path d="M6.6 6.6a8 8 0 1 0 10.8 0" />
  </svg>
);

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "Xác nhận",
  cancelText = "Hủy",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    confirmRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") onCancel?.();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="sv-confirm-overlay" onClick={onCancel} role="presentation">
      <div
        className="sv-confirm-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sv-confirm-title"
        aria-describedby="sv-confirm-message"
        onClick={(event) => event.stopPropagation()}
      >
        <span className={`sv-confirm-icon${danger ? " danger" : ""}`} aria-hidden="true">
          {POWER_ICON}
        </span>
        <h2 id="sv-confirm-title">{title}</h2>
        <p id="sv-confirm-message">{message}</p>
        <div className="sv-confirm-actions">
          <button type="button" className="sv-btn sv-btn-outline" onClick={onCancel} disabled={busy}>
            {cancelText}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`sv-confirm-submit${danger ? " danger" : ""}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Đang xử lý..." : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
