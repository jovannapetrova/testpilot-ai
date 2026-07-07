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
  const getAgent = (name) => {
    return (
      logs.find((agent) => agent.name === name) || {
        name,
        status: running ? "pending" : "idle",
        message: running ? "Pending" : "Idle",
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

        <span className={`status-badge ${running ? "running" : "success"}`}>
          {running ? "Running" : "Ready"}
        </span>
      </div>

      <div className="timeline-list">
        {defaultAgents.map((agentName, index) => {
          const agent = getAgent(agentName);

          return (
            <div className="timeline-item" key={agentName}>
              <div className="timeline-index">{index + 1}</div>

              <div>
                <strong>{agentName}</strong>
                <p>{agent.message || agent.status}</p>
              </div>

              <span className={`agent-state ${agent.status}`}>
                {agent.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}