import { BarChart3 } from "lucide-react";

import AnalysisScoreGrid from "./AnalysisScoreGrid";
import AnalysisDetailsGrid from "./AnalysisDetailsGrid";
import AnalysisTabs from "./AnalysisTabs";
import AIInsightsPanel from "./AIInsightsPanel";
import ProjectIntelligencePanel from "./ProjectIntelligencePanel";

export default function AnalysisResultPanel({ report }) {
  if (!report) return null;

  return (
    <div className="analysis-result">
      <div className="analysis-title">
        <BarChart3 size={20} />
        <strong>Professional Analysis Report Preview</strong>
      </div>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Scores</p>
            <h2>Quality Gate Overview</h2>
          </div>
        </div>
        <AnalysisScoreGrid report={report} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Executive summary</p>
            <h2>AI Insights</h2>
          </div>
        </div>
        <AIInsightsPanel insights={report.metadata?.ai_insights} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project intelligence</p>
            <h2>Repository Profile</h2>
          </div>
        </div>
        <ProjectIntelligencePanel intelligence={report.metadata?.project_intelligence} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project statistics</p>
            <h2>Codebase Inventory</h2>
          </div>
        </div>
        <AnalysisDetailsGrid report={report} />
      </section>

      <section className="analysis-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Findings</p>
            <h2>Security, Tests and Quality</h2>
          </div>
        </div>
        <AnalysisTabs report={report} />
      </section>

    </div>
  );
}
