export default function QualityMetricsList({ metrics = [], metadata = {} }) {
  if (!metrics.length) {
    return <p className="muted-text">No quality metrics available.</p>;
  }

  return (
    <div className="detail-list">
      {metadata.partial_analysis ? (
        <div className="detail-row">
          <div>
            <strong>Partial quality analysis</strong>
            {(metadata.warnings || []).map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
          <span className="severity medium">{metadata.analyzed_files}/{metadata.candidate_files}</span>
        </div>
      ) : null}

      {metrics.slice(0, 8).map((metric) => {
        const evidence = metric.quality_issues || [];
        const duplicatePairs = metric.duplicate_blocks_detail || [];

        return (
        <div className="detail-row" key={metric.file}>
          <div>
            <strong>{metric.file}</strong>
            <p>
              Complexity: {metric.complexity} | Maintainability: {metric.maintainability_index}
              {metric.max_nesting_depth ? ` | Nesting: ${metric.max_nesting_depth}` : ""}
              {` | ${metric.context || "production"}`}
            </p>
            {metric.smells?.length ? (
              <p>{metric.smells.slice(0, 3).join(" | ")}</p>
            ) : null}
            {evidence.slice(0, 3).map((issue) => (
              <p key={`${issue.type}-${issue.start_line}-${issue.end_line}`}>
                {(issue.issue_type || issue.type)} lines {issue.start_line}-{issue.end_line}
                {issue.symbol ? ` (${issue.symbol})` : ""}: {issue.remediation}
              </p>
            ))}
            {duplicatePairs.slice(0, 2).map((pair) => (
              <p key={`${pair.first_start}-${pair.second_start}`}>
                Duplicate block lines {pair.first_start}-{pair.first_end} matches {pair.second_start}-{pair.second_end}
              </p>
            ))}
            {metric.recommendations?.length ? (
              <p>{metric.recommendations[0]}</p>
            ) : null}
          </div>
          <span className="severity info">{evidence.length || metric.issues?.length || 0} issues</span>
        </div>
        );
      })}
    </div>
  );
}
