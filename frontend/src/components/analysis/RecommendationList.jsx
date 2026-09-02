const priorityRank = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function uniqueRecommendations(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = [
      item.title,
      item.category,
      item.why || item.description,
      item.suggested_action,
    ].join("|").toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function RecommendationList({ recommendations = [] }) {
  const items = uniqueRecommendations(recommendations)
    .sort((a, b) => (priorityRank[String(a.priority || "").toLowerCase()] ?? 9) - (priorityRank[String(b.priority || "").toLowerCase()] ?? 9));

  if (!items.length) return <p className="muted-text">No recommendations generated for this report.</p>;

  return (
    <div className="recommendation-list">
      {items.map((rec) => {
        const priority = String(rec.priority || "medium").toLowerCase();
        return (
          <div className="recommendation-row" key={`${rec.title}-${rec.category}`}>
            <div className="recommendation-meta">
              <span className={`severity ${priority}`}>{priority}</span>
              {rec.category ? <span className="severity info">{rec.category}</span> : null}
              {rec.estimated_effort ? <span className="severity low">{rec.estimated_effort}</span> : null}
            </div>

            <strong>{rec.title}</strong>
            <p>{rec.why || rec.description}</p>
            {rec.suggested_action ? <p><strong>Suggested action:</strong> {rec.suggested_action}</p> : null}
            {rec.business_impact ? <p><strong>Business impact:</strong> {rec.business_impact}</p> : null}
            {rec.evidence ? <p><strong>Evidence:</strong> {rec.evidence}</p> : null}
            {rec.affected_files?.length ? (
              <span className="recommendation-files">
                Affected files: {rec.affected_files.slice(0, 5).join(", ")}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
