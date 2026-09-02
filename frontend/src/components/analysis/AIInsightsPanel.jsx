export default function AIInsightsPanel({ insights }) {
  if (!insights) return null;

  const normalize = (value) =>
    String(value || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .replace(/[^\w\s]/g, "")
      .trim();

  const seen = new Set();
  const nextActions = (insights.next_best_actions || []).filter((action) => {
    const key = normalize(action);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  const priorityActions = (insights.priority_actions || []).filter((action) => {
    const key = normalize(`${action.what} ${action.why} ${action.how_to_fix}`);
    const titleKey = normalize(action.what);
    if (!key || seen.has(key) || seen.has(titleKey)) return false;
    seen.add(key);
    seen.add(titleKey);
    return true;
  });

  return (
    <div className="ai-insights-panel">
      <div className="insight-grid">
        <div>
          <span>Risk Level</span>
          <strong>{insights.risk_level}</strong>
        </div>
        <div>
          <span>Main Weakness</span>
          <strong>{insights.main_weakness}</strong>
        </div>
        {insights.primary_strength ? (
          <div>
            <span>Primary Strength</span>
            <strong>{insights.primary_strength}</strong>
          </div>
        ) : null}
      </div>

      <p>{insights.summary}</p>

      {insights.executive_summary ? (
        <p>{insights.executive_summary.why_it_matters}</p>
      ) : null}

      {nextActions.length ? (
      <ul>
        {nextActions.map((action) => (
          <li key={action}>{action}</li>
        ))}
      </ul>
      ) : null}

      {priorityActions.length ? (
        <div className="detail-list">
          {priorityActions.slice(0, 3).map((action) => (
            <div className="detail-row" key={`${action.priority}-${action.what}`}>
              <div>
                <strong>{action.what}</strong>
                <p>{action.why}</p>
                <p>{action.how_to_fix}</p>
              </div>
              <span className={`severity ${action.priority}`}>{action.estimated_effort}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
