export default function StatusBadge({ status = "success" }) {
  const normalized = String(status || "success").toLowerCase();
  const labels = {
    success: "Completed",
    completed: "Completed",
    queued: "Queued",
    analyzing: "Analyzing",
    running: "Running",
    warning: "Warning",
    failed: "Failed",
    idle: "Idle",
  };

  return (
    <span className={`status-badge ${normalized}`}>
      <span className="status-dot" />
      {labels[normalized] || status}
    </span>
  );
}
