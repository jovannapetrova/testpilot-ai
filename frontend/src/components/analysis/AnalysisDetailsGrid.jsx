export default function AnalysisDetailsGrid({ report }) {
  const code = report?.code_analysis;

  return (
    <div className="analysis-details-grid">
      <div><span>Analyzed files</span><strong>{code?.total_files ?? 0}</strong></div>
      <div><span>Total lines</span><strong>{code?.total_lines ?? 0}</strong></div>
      <div><span>Functions</span><strong>{code?.total_functions ?? 0}</strong></div>
      <div><span>Classes</span><strong>{code?.total_classes ?? 0}</strong></div>
    </div>
  );
}
