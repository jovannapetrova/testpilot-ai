export default function RecommendationList({ recommendations = [] }) {
  if (!recommendations.length) return null;

  return (
    <div className="recommendation-list">
      <h4>AI Recommendations</h4>

      {recommendations.slice(0, 3).map((rec) => (
        <div className="recommendation-row" key={rec.title}>
          <strong>{rec.title}</strong>
          <p>{rec.description}</p>
        </div>
      ))}
    </div>
  );
}