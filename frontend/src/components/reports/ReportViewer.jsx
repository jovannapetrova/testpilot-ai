import AnalysisResultPanel from "../analysis/AnalysisResultPanel";

export default function ReportViewer({ report }) {
  if (!report) return null;

  return (
    <div className="report-viewer">
      <div className="page-header">
        <p className="eyebrow">Opened report</p>
        <h2>{report.project_name}</h2>
        <p>Full multi-agent analysis report loaded from backend storage.</p>
      </div>

      <AnalysisResultPanel report={report} />
    </div>
  );
}