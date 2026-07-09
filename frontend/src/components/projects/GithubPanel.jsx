import { useState } from "react";
import { GitBranch, Loader2, Play } from "lucide-react";
import {
  analyzeGithubRepository,
  getAnalysisProgress,
  getReport,
} from "../../api/client";
import AnalysisResultPanel from "../analysis/AnalysisResultPanel";
import AgentTimeline from "../ui/AgentTimeline";

function formatSeconds(value) {
  if (value === null || value === undefined) return "Calculating...";
  if (value <= 0) return "Done";

  const minutes = Math.floor(value / 60);
  const seconds = value % 60;

  if (minutes <= 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

export default function GithubPanel({ onAnalysisComplete }) {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");
  const [summary, setSummary] = useState(null);
  const [report, setReport] = useState(null);

  const [progress, setProgress] = useState(0);
  const [currentAgent, setCurrentAgent] = useState("");
  const [logs, setLogs] = useState([]);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [etaSeconds, setEtaSeconds] = useState(null);
  const [completedAgents, setCompletedAgents] = useState(0);
  const [totalAgents, setTotalAgents] = useState(9);

  const hydrateProgress = (data) => {
    setProgress(data.progress || 0);
    setCurrentAgent(data.current_agent || "Analyzing...");
    setLogs(data.agents || []);
    setElapsedSeconds(data.elapsed_seconds || 0);
    setEtaSeconds(data.eta_seconds);
    setCompletedAgents(data.completed_agents || 0);
    setTotalAgents(data.total_agents || 9);
  };

  const buildSummaryFromReport = (projectId, projectName, finalReport) => {
    const intelligence = finalReport?.metadata?.project_intelligence;
    const profile = finalReport?.metadata?.project_profile;
    const analysis = finalReport?.code_analysis;

    return {
      project_id: projectId,
      project_name: projectName,
      language:
        intelligence?.primary_language === "python"
          ? "Python"
          : intelligence?.primary_language || "Unknown",
      total_files: analysis?.total_files ?? profile?.total_files ?? "-",
      python_files: profile?.languages?.python ?? "-",
    };
  };

  const pollProgress = (projectId, projectName) => {
    const timer = setInterval(async () => {
      try {
        const data = await getAnalysisProgress(projectId);
        hydrateProgress(data);

        if (data.status === "completed") {
          clearInterval(timer);

          const reportResponse = await getReport(projectId);
          const finalReport = reportResponse.report;

          setReport(finalReport);
          setStatus("success");
          setMessage("GitHub repository analyzed successfully.");
          setProgress(100);
          setCurrentAgent("Completed");
          setLogs(finalReport?.agent_logs || []);
          setSummary(buildSummaryFromReport(projectId, projectName, finalReport));
          onAnalysisComplete?.();
        }

        if (data.status === "failed") {
          clearInterval(timer);
          setStatus("error");
          setMessage(data.error || "Analysis failed.");
          setCurrentAgent("Failed");
        }
      } catch (error) {
        clearInterval(timer);
        setStatus("error");
        setMessage(error.userMessage || "Progress tracking failed.");
      }
    }, 900);
  };

  const handleAnalyze = async () => {
    if (!url.trim()) {
      setStatus("error");
      setMessage("Enter a GitHub repository URL.");
      return;
    }

    try {
      setStatus("running");
      setMessage("GitHub analysis started. Tracking live progress...");
      setSummary(null);
      setReport(null);
      setProgress(0);
      setCurrentAgent("Preparing analysis...");
      setLogs([]);
      setElapsedSeconds(0);
      setEtaSeconds(null);
      setCompletedAgents(0);

      const result = await analyzeGithubRepository(url);

      setSummary({
        project_id: result.project_id,
        project_name: result.project_name,
        language: "Detecting...",
        total_files: "-",
        python_files: "-",
      });

      pollProgress(result.project_id, result.project_name);
    } catch (error) {
      setStatus("error");
      setMessage(error.userMessage || "GitHub analysis failed.");
      setCurrentAgent("Failed");
    }
  };

  return (
    <div className="card upload-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Remote Repository</p>
          <h2>GitHub Analysis</h2>
        </div>
      </div>

      <div className={`github-form ${status}`}>
        {status === "running" ? (
          <Loader2 className="spin" size={42} />
        ) : (
          <GitBranch size={42} />
        )}

        <input
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://github.com/username/repository"
        />

        <button
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={status === "running"}
        >
          {status === "running" ? (
            <>
              <Loader2 className="spin" size={17} />
              Running Analysis...
            </>
          ) : (
            <>
              <Play size={17} />
              Analyze Repository
            </>
          )}
        </button>

        {status === "running" && (
          <div className="analysis-progress">
            <div className="progress-header">
              <span>{progress}% completed</span>
              <strong>{currentAgent || "Preparing analysis..."}</strong>
            </div>

            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>

            <div className="progress-meta">
              <span>Agents: {completedAgents}/{totalAgents}</span>
              <span>Elapsed: {formatSeconds(elapsedSeconds)}</span>
              <span>ETA: {formatSeconds(etaSeconds)}</span>
            </div>
          </div>
        )}

        {message && (
          <p className={status === "error" ? "upload-error" : ""}>{message}</p>
        )}

        {summary && (
          <div className="upload-summary">
            <div>
              <span>Project</span>
              <strong>{summary.project_name}</strong>
            </div>
            <div>
              <span>Language</span>
              <strong>{summary.language}</strong>
            </div>
            <div>
              <span>Total files</span>
              <strong>{summary.total_files}</strong>
            </div>
            <div>
              <span>Python</span>
              <strong>{summary.python_files}</strong>
            </div>
          </div>
        )}

        {(status === "running" || report) && (
          <AgentTimeline logs={logs} running={status === "running"} />
        )}

        <AnalysisResultPanel report={report} />
      </div>
    </div>
  );
}
