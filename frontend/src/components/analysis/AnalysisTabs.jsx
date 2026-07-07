import { useState } from "react";
import SecurityFindingsList from "./SecurityFindingsList";
import GeneratedTestsList from "./GeneratedTestsList";
import QualityMetricsList from "./QualityMetricsList";
import RecommendationList from "./RecommendationList";
import AgentLogList from "./AgentLogList";

const tabs = ["Security", "Generated Tests", "Quality Metrics", "Recommendations", "Agent Log"];

function SummaryCards({ active, report, testMetadata }) {
  const findings = report.security_findings || [];
  const quality = report.quality_metrics || [];
  const recommendations = report.recommendations || [];
  const logs = report.agent_logs || [];

  if (active === "Security") {
    const grouped = new Set(findings.map((item) => item.fingerprint || `${item.issue}-${item.file}`));
    const count = (severity) => findings.filter((item) => item.severity === severity).length;
    return (
      <div className="tab-summary-grid">
        <div><span>Critical</span><strong>{count("critical")}</strong></div>
        <div><span>High</span><strong>{count("high")}</strong></div>
        <div><span>Medium</span><strong>{count("medium")}</strong></div>
        <div><span>Low</span><strong>{count("low")}</strong></div>
        <div><span>Grouped</span><strong>{grouped.size}</strong></div>
      </div>
    );
  }

  if (active === "Generated Tests") {
    const categories = testMetadata.by_category || {};
    const needsDesign = Array.isArray(testMetadata.needs_human_test_design)
      ? testMetadata.needs_human_test_design.length
      : Number(testMetadata.needs_human_test_design || 0);
    return (
      <div className="tab-summary-grid">
        <div><span>Executable</span><strong>{testMetadata.executable_tests ?? report.generated_tests?.length ?? 0}</strong></div>
        <div><span>Smoke</span><strong>{testMetadata.smoke_tests ?? 0}</strong></div>
        <div><span>Needs design</span><strong>{needsDesign}</strong></div>
        <div className="wide"><span>Categories</span><strong>{Object.entries(categories).map(([k, v]) => `${k}: ${v}`).join(" | ") || "None"}</strong></div>
      </div>
    );
  }

  if (active === "Quality Metrics") {
    const issueCount = quality.reduce((sum, item) => sum + ((item.quality_issues || item.issues || []).length), 0);
    const highestRisk = [...quality].sort((a, b) => ((b.quality_issues || b.issues || []).length) - ((a.quality_issues || a.issues || []).length))[0];
    return (
      <div className="tab-summary-grid">
        <div><span>Issues</span><strong>{issueCount}</strong></div>
        <div><span>Files</span><strong>{quality.length}</strong></div>
        <div className="wide"><span>Highest risk</span><strong>{highestRisk?.file || "None"}</strong></div>
      </div>
    );
  }

  if (active === "Recommendations") {
    return (
      <div className="tab-summary-grid">
        <div><span>Actions</span><strong>{recommendations.length}</strong></div>
        <div className="wide"><span>Top priority</span><strong>{recommendations[0]?.priority || recommendations[0]?.title || "None"}</strong></div>
      </div>
    );
  }

  return (
    <div className="tab-summary-grid">
      <div><span>Total agents</span><strong>{logs.length}</strong></div>
      <div><span>Completed</span><strong>{logs.filter((log) => log.status === "completed").length}</strong></div>
      <div><span>Failed</span><strong>{logs.filter((log) => log.status === "failed").length}</strong></div>
    </div>
  );
}

export default function AnalysisTabs({ report }) {
  const [active, setActive] = useState("Security");
  const testMetadata = {
    ...(report.metadata?.generated_tests_summary || {}),
    ...(report.metadata?.test_generation_metadata || {}),
  };

  return (
    <div className="analysis-tabs">
      <div className="tab-buttons">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={active === tab ? "tab-btn active" : "tab-btn"}
            onClick={() => setActive(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="tab-panel">
        <SummaryCards active={active} report={report} testMetadata={testMetadata} />

        {active === "Security" && (
          <SecurityFindingsList findings={report.security_findings} />
        )}

        {active === "Generated Tests" && (
          <GeneratedTestsList
            tests={report.generated_tests}
            metadata={testMetadata}
          />
        )}

        {active === "Quality Metrics" && (
          <QualityMetricsList
            metrics={report.quality_metrics}
            metadata={report.metadata?.quality_analysis_metadata || {}}
          />
        )}

        {active === "Recommendations" && (
          <RecommendationList recommendations={report.recommendations} />
        )}

        {active === "Agent Log" && (
          <AgentLogList logs={report.agent_logs} />
        )}
      </div>
    </div>
  );
}
