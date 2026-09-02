import { CheckCircle2, X } from "lucide-react";

export default function Toast({ message, tone = "success", onClose }) {
  if (!message) return null;

  return (
    <div className={`toast toast-${tone}`} role="status" aria-live="polite">
      <CheckCircle2 size={18} />
      <span>{message}</span>
      {onClose ? (
        <button type="button" className="toast-close" onClick={onClose} aria-label="Dismiss message">
          <X size={16} />
        </button>
      ) : null}
    </div>
  );
}
