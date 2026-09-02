import { useMemo, useState } from "react";
import { Bot, ClipboardCheck, Code2, ShieldAlert, WandSparkles } from "lucide-react";
import SecurityFindingsList from "./SecurityFindingsList";
import GeneratedTestsList from "./GeneratedTestsList";
import QualityMetricsList from "./QualityMetricsList";
import RecommendationList from "./RecommendationList";
import AgentLogList from "./AgentLogList";

const tabs = [
  { id: "security", label: "Security", icon: ShieldAlert },
  { id: "tests", label: "Generated Tests", icon: ClipboardCheck },
  { id: "quality", label: "Code Quality", icon: Code2 },
  { id: "recommendations", label: "Recommendations", icon: WandSparkles },
  { id: "agents", label: "AI Agents", icon: Bot },
];

function severityValue(value) {
  return String(value || "").split(".").pop().toLowerCase();
}

function SummaryCards({ active, report, testMetadata }) {
  const findings = report.security_findings || [];
  const quality = report.quality_metrics || [];
  const recommendations = report.recommendations || [];
  const logs = report.agent_logs || [];
  const qualitySummary = report.metadata?.quality_summary || {};

  if (active === "security") {
    const grouped = new Set(findings.map((item) => item.fingerprint || `${item.issue}-${item.file}`));
    const count = (severity) => findings.filter((item) => severityValue(item.severity) === severity).length;
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

  if (active === "tests") {
    const categories = testMetadata.by_category || {};
    const needsDesign = Array.isArray(testMetadata.needs_human_test_design)
      ? testMetadata.needs_human_test_design.length
      : Number(testMetadata.needs_human_test_design || 0);
    const generated = testMetadata.generated_candidates ?? testMetadata.total ?? report.generated_tests?.length ?? 0;
    const ready = testMetadata.ready_to_execute ?? testMetadata.executable_tests ?? generated;
    const executed = Number(testMetadata.executed_tests || 0);
    const passed = executed ? testMetadata.passed ?? 0 : "N/A";
    return (
      <div className="tab-summary-grid">
        <div><span>Generated candidates</span><strong>{generated}</strong></div>
        <div><span>Ready to execute</span><strong>{ready}</strong></div>
        <div><span>Executed</span><strong>{executed}</strong></div>
        <div><span>Passed</span><strong>{passed}</strong></div>
        <div><span>Needs human design</span><strong>{needsDesign}</strong></div>
        <div><span>Smoke checks</span><strong>{testMetadata.smoke_tests ?? 0}</strong></div>
        <div className="wide"><span>Categories</span><strong>{Object.entries(categories).map(([k, v]) => `${k}: ${v}`).join(" | ") || "None"}</strong></div>
        <div className="wide"><span>Execution state</span><strong>{testMetadata.not_executed_reason || testMetadata.execution_status || "Not executed"}</strong></div>
      </div>
    );
  }

  if (active === "quality") {
    const issueCount = quality.reduce((sum, item) => sum + ((item.quality_issues || item.issues || []).length), 0);
    const contextRank = (context) => ({
      production: 0,
      config: 1,
      ci: 2,
      test: 3,
      example: 4,
      docs: 5,
    }[String(context || "production").toLowerCase()] ?? 6);
    const fallbackHighestRisk = [...quality].sort((a, b) => {
      const rankDelta = contextRank(a.context) - contextRank(b.context);
      if (rankDelta !== 0) return rankDelta;
      return ((b.quality_issues || b.issues || []).length) - ((a.quality_issues || a.issues || []).length);
    })[0];
    const highestRisk = qualitySummary.highest_production_risk || fallbackHighestRisk;
    const testHotspot = qualitySummary.test_suite_hotspot;
    return (
      <div className="tab-summary-grid">
        <div><span>Issues</span><strong>{issueCount}</strong></div>
        <div><span>Files</span><strong>{quality.length}</strong></div>
        <div className="wide"><span>Highest production risk</span><strong>{highestRisk?.file || "None"}</strong></div>
        <div className="wide"><span>Test-suite hotspot</span><strong>{testHotspot?.file || "None"}</strong></div>
      </div>
    );
  }

  if (active === "recommendations") {
    const high = recommendations.filter((item) => String(item.priority || "").toLowerCase() === "high").length;
    return (
      <div className="tab-summary-grid">
        <div><span>Actions</span><strong>{recommendations.length}</strong></div>
        <div><span>High priority</span><strong>{high}</strong></div>
        <div className="wide"><span>Top action</span><strong>{recommendations[0]?.title || "None"}</strong></div>
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
  const [active, setActive] = useState("security");
  const testMetadata = useMemo(() => ({
    ...(report.metadata?.generated_tests_summary || {}),
    ...(report.metadata?.test_generation_metadata || {}),
  }), [report.metadata?.generated_tests_summary, report.metadata?.test_generation_metadata]);

  const nav = useMemo(() => {
    const testsNeedsDesign = Array.isArray(testMetadata.needs_human_test_design)
      ? testMetadata.needs_human_test_design.length
      : Number(testMetadata.needs_human_test_design || 0);
    const generated = testMetadata.generated_candidates ?? testMetadata.total ?? report.generated_tests?.length ?? 0;
    const ready = testMetadata.ready_to_execute ?? testMetadata.executable_tests ?? generated;
    const qualityIssues = (report.quality_metrics || []).reduce(
      (sum, metric) => sum + ((metric.quality_issues || metric.issues || []).length),
      0,
    );
    const completedAgents = (report.agent_logs || []).filter((log) => log.status === "completed").length;
    return {
      security: `${report.security_findings?.length || 0} findings`,
      tests: `${generated} generated, ${ready} ready, ${testsNeedsDesign} need design`,
      quality: `${qualityIssues} issues`,
      recommendations: `${report.recommendations?.length || 0} actions`,
      agents: `${completedAgents}/${report.agent_logs?.length || 0} completed`,
    };
  }, [report, testMetadata]);

  return (
    <div className="analysis-tabs">
      <div className="tab-buttons">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={active === tab.id ? "analysis-nav-card active" : "analysis-nav-card"}
              onClick={() => setActive(tab.id)}
            >
              <Icon size={18} />
              <strong>{tab.label}</strong>
              <span>{nav[tab.id]}</span>
            </button>
          );
        })}
      </div>

      <div className="tab-panel">
        <SummaryCards active={active} report={report} testMetadata={testMetadata} />

        {active === "security" && (
          <SecurityFindingsList findings={report.security_findings} />
        )}

        {active === "tests" && (
          <GeneratedTestsList
            tests={report.generated_tests}
            metadata={testMetadata}
          />
        )}

        {active === "quality" && (
          <QualityMetricsList
            metrics={report.quality_metrics}
            metadata={report.metadata?.quality_analysis_metadata || {}}
          />
        )}

        {active === "recommendations" && (
          <RecommendationList recommendations={report.recommendations} />
        )}

        {active === "agents" && (
          <AgentLogList logs={report.agent_logs} />
        )}
      </div>
    </div>
  );
}
