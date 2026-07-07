import { useEffect, useState } from "react";
import AgentTimeline from "../components/ui/AgentTimeline";
import { getReports, getReport } from "../api/client";

const agentCards = [
  ["Project Detector Agent", "Classifies repository shape, language, frameworks and architecture.", "Discovery"],
  ["Dependency Analyzer Agent", "Reviews dependency manifests and supply-chain risk signals.", "Risk"],
  ["Code Analyzer Agent", "Extracts files, functions, classes, imports and code statistics.", "Inventory"],
  ["Security Agent", "Groups security findings with confidence, context and remediation.", "Security"],
  ["Quality Agent", "Evaluates maintainability, complexity, duplication and code smells.", "Quality"],
  ["Test Generator Agent", "Creates executable tests and separates human-design targets.", "Testing"],
  ["Coverage Agent", "Runs or estimates coverage with clear execution notes.", "Coverage"],
  ["Recommendation Agent", "Turns findings into prioritized engineering actions.", "Insights"],
  ["Report Agent", "Builds audit-ready JSON, PDF, CSV and Markdown reports.", "Reporting"],
];

export default function Agents() {
  const [logs, setLogs] = useState([]);
  const [latestProject, setLatestProject] = useState("");

  const loadLatestAgentLogs = async () => {
    try {
      const reportsResponse = await getReports();
      const reports = reportsResponse.reports || [];

      if (!reports.length) {
        setLogs([]);
        return;
      }

      const latest = reports[0];
      const reportResponse = await getReport(latest.project_id);

      setLogs(reportResponse.report?.agent_logs || []);
      setLatestProject(latest.project_name || "");
    } catch {
      setLogs([]);
    }
  };

  useEffect(() => {
    loadLatestAgentLogs();
  }, []);

  return (
    <div>
      <div className="page-header">
        <p className="eyebrow">AI orchestration layer</p>
        <h2>Agent Center</h2>
        <p>
          TestPilot AI uses specialized agents coordinated through a central
          orchestrator to perform end-to-end software quality analysis.
        </p>

        {latestProject && (
          <p className="muted-text">
            Showing latest execution log for: <strong>{latestProject}</strong>
          </p>
        )}
      </div>

      <div className="agent-center-grid">
        {agentCards.map(([title, description, role]) => (
          <div className="card agent-center-card" key={title}>
            <span className="severity info">{role}</span>
            <h3>{title}</h3>
            <p>{description}</p>
            <span>Ready for orchestration</span>
          </div>
        ))}
      </div>

      <AgentTimeline logs={logs} running={false} />
    </div>
  );
}
