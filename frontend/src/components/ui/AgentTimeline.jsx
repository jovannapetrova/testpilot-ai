const defaultAgents = [
  "Project Detector Agent",
  "Dependency Analyzer Agent",
  "Code Analyzer Agent",
  "Security Agent",
  "Quality Agent",
  "Test Generator Agent",
  "Coverage Agent",
  "Recommendation Agent",
  "Report Agent",
];

export default function AgentTimeline({ logs = [], running = false }) {
  const normalizeStatus = (value) => String(value || "idle").split(".").pop().toLowerCase();
  const hasLiveAgent = logs.some((agent) => ["running", "pending", "queued"].includes(normalizeStatus(agent.status)));
  const isRunning = running || hasLiveAgent;
  const completed = logs.filter((agent) => normalizeStatus(agent.status) === "completed").length;
  const failed = logs.filter((agent) => normalizeStatus(agent.status) === "failed").length;
  const total = logs.length || defaultAgents.length;

  const getAgent = (name) => {
    return (
      logs.find((agent) => agent.name === name) || {
        name,
        status: isRunning ? "pending" : "idle",
        message: isRunning ? "Pending" : "Idle",
      }
    );
  };

  return (
    <div className="card agent-timeline">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Multi-agent orchestration</p>
          <h2>Agent Activity</h2>
        </div>

        <span className={`status-badge ${isRunning ? "running" : "idle"}`}>
          {isRunning ? "Analyzing" : "Ready"}
        </span>
      </div>

      {!isRunning ? (
        <div className="agent-idle-panel">
          <strong>System state: Ready</strong>
          {logs.length ? (
            <p>
              Last run: {completed}/{total} agents completed
              {failed ? `, ${failed} failed` : ""}.
            </p>
          ) : (
            <p>No analysis is currently running. Start a ZIP or GitHub analysis when ready.</p>
          )}
        </div>
      ) : (
        <div className="timeline-list">
          {defaultAgents.map((agentName, index) => {
            const agent = getAgent(agentName);
            const status = normalizeStatus(agent.status);

            return (
              <div className="timeline-item" key={agentName}>
                <div className="timeline-index">{index + 1}</div>

                <div>
                  <strong>{agentName}</strong>
                  <p>{agent.message || status}</p>
                </div>

                <span className={`agent-state ${status}`}>
                  {status}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
