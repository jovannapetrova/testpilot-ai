import { AlertCircle } from "lucide-react";

export default function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <div className="card error-state-panel" role="alert">
      <AlertCircle size={22} />
      <div>
        <strong>{title}</strong>
        {message ? <p>{message}</p> : null}
      </div>
      {onRetry ? (
        <button type="button" className="btn btn-ghost" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
