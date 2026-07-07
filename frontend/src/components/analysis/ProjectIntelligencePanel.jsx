export default function ProjectIntelligencePanel({ intelligence }) {
  if (!intelligence) return null;

  return (
    <div className="project-intelligence-panel">
      <h4>Project Intelligence</h4>
      <p>{intelligence.summary}</p>

      <div className="intelligence-grid">
        <div><span>Project Type</span><strong>{intelligence.project_type}</strong></div>
        <div><span>Language</span><strong>{intelligence.primary_language}</strong></div>
        <div><span>Frameworks</span><strong>{intelligence.frameworks?.join(", ") || "None"}</strong></div>
        <div><span>Dependencies</span><strong>{intelligence.dependency_count}</strong></div>
        <div><span>Docker</span><strong>{intelligence.has_docker ? "Yes" : "No"}</strong></div>
        <div><span>README</span><strong>{intelligence.has_readme ? "Yes" : "No"}</strong></div>
        <div><span>Tests</span><strong>{intelligence.has_tests ? "Yes" : "No"}</strong></div>
        <div><span>Dependency Risk</span><strong>{intelligence.dependency_risk_level}</strong></div>
        <div><span>CI</span><strong>{intelligence.architecture_signals?.has_ci ? "Yes" : "No"}</strong></div>
        <div><span>Monorepo</span><strong>{intelligence.architecture_signals?.is_monorepo ? "Yes" : "No"}</strong></div>
      </div>

      {intelligence.entrypoints?.length ? (
        <p>Entrypoints: {intelligence.entrypoints.slice(0, 5).join(", ")}</p>
      ) : null}

      <div className="intelligence-lists">
        <div>
          <h5>Strengths</h5>
          <ul>{intelligence.strengths?.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h5>Risks</h5>
          <ul>{intelligence.risks?.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
    </div>
  );
}
