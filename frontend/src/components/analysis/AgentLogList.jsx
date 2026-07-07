export default function AgentLogList({ logs = [] }) {
  return (
    <div className="agent-log-list">
      <h4>Agent Execution Log</h4>

      {logs.map((log) => (
        <div className="agent-log-row" key={log.name}>
          <div>
            <strong>{log.name}</strong>
            <span>{log.message}</span>
          </div>

          <span className={`agent-log-status ${log.status}`}>
            {log.status}
          </span>
        </div>
      ))}
    </div>
  );
}