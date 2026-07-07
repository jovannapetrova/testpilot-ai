export default function StatusBadge({ status = "success" }) {
  const labels = {
    success: "Completed",
    running: "Running",
    warning: "Warning",
    failed: "Failed",
    idle: "Idle",
  };

  return (
    <span className={`status-badge ${status}`}>
      <span className="status-dot" />
      {labels[status] || status}
    </span>
  );
}