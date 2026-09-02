export default function AgentLogList({ logs = [] }) {
  if (!logs.length) {
    return <p className="muted-text">Agent execution details are not available for this report.</p>;
  }

  return (
    <div className="agent-log-list">
      {logs.map((log) => (
        <div className="agent-log-row" key={log.name}>
          <div>
            <strong>{log.name}</strong>
            <span>{log.message}</span>
            {log.duration_seconds !== undefined ? <span>{log.duration_seconds}s</span> : null}
          </div>

          <span className={`agent-log-status ${log.status}`}>
            {log.status}
          </span>
        </div>
      ))}
    </div>
  );
}
