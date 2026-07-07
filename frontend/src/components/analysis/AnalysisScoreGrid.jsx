export default function AnalysisScoreGrid({ report }) {
  return (
    <div className="analysis-grid">
      <div><span>Overall</span><strong>{report.overall_score}</strong></div>
      <div><span>Quality</span><strong>{report.quality_score}</strong></div>
      <div><span>Security</span><strong>{report.security_score}</strong></div>
      <div><span>Testing</span><strong>{report.test_score}</strong></div>
    </div>
  );
}