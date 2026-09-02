export default function AnalysisScoreGrid({ report }) {
  const coverage = report.coverage || {};
  const coverageAvailable = coverage.available || coverage.measured || (coverage.executed && !coverage.estimated);
  const coverageLabel = coverage.display_label || (
    coverageAvailable ? `${coverage.coverage_percent ?? 0}%` : "Coverage: Not measured"
  );

  return (
    <div className="analysis-grid">
      <div><span>Overall Score</span><strong>{report.overall_score}</strong></div>
      <div><span>Quality Score</span><strong>{report.quality_score}</strong></div>
      <div><span>Security Score</span><strong>{report.security_score}</strong></div>
      <div>
        <span>Testing Score</span>
        <strong>{report.test_score}</strong>
        <small>{coverageLabel}</small>
      </div>
    </div>
  );
}
