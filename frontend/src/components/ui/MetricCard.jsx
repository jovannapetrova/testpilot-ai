export default function MetricCard({ title, value, subtitle, icon: Icon, trend }) {
  return (
    <div className="metric-card card">
      <div className="metric-top">
        <div>
          <p>{title}</p>
          <h2>{value}</h2>
        </div>
        {Icon && (
          <div className="metric-icon">
            <Icon size={22} />
          </div>
        )}
      </div>

      <div className="metric-bottom">
        <span>{subtitle}</span>
        {trend && <strong>{trend}</strong>}
      </div>
    </div>
  );
}