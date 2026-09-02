import { BarChart3 } from "lucide-react";

import AnalysisScoreGrid from "./AnalysisScoreGrid";
import AnalysisDetailsGrid from "./AnalysisDetailsGrid";
import AnalysisTabs from "./AnalysisTabs";
import AIInsightsPanel from "./AIInsightsPanel";
import ProjectIntelligencePanel from "./ProjectIntelligencePanel";

export default function AnalysisResultPanel({ report }) {
  if (!report) return null;
  const intelligence = report.metadata?.project_intelligence || {};
  const profile = report.metadata?.project_profile || {};
  const source = report.metadata?.source_url || profile.source_url || intelligence.repository_url;

  return (
    <div className="analysis-result">
      <div className="analysis-title">
        <BarChart3 size={20} />
        <div>
          <strong>{report.project_name || "Analysis Detail"}</strong>
          <span>
            {[source, intelligence.primary_language || profile.primary_language, intelligence.frameworks?.slice(0, 2).join(", ")]
              .filter(Boolean)
              .join(" | ")}
          </span>
        </div>
      </div>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Quality gate</p>
            <h2>Score Overview</h2>
          </div>
        </div>
        <AnalysisScoreGrid report={report} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Executive summary</p>
            <h2>AI Analysis Summary</h2>
          </div>
        </div>
        <AIInsightsPanel insights={report.metadata?.ai_insights} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Repository profile</p>
            <h2>Project Profile</h2>
          </div>
        </div>
        <ProjectIntelligencePanel intelligence={report.metadata?.project_intelligence} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project statistics</p>
            <h2>Codebase Summary</h2>
          </div>
        </div>
        <AnalysisDetailsGrid report={report} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Agent findings</p>
            <h2>Core Analysis Areas</h2>
          </div>
        </div>
        <AnalysisTabs report={report} />
      </section>

    </div>
  );
}
