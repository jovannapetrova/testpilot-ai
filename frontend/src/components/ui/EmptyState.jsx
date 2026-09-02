export default function EmptyState({ icon: Icon, title, message, action }) {
  return (
    <div className="card empty-state-panel">
      {Icon ? (
        <div className="empty-state-icon">
          <Icon size={34} />
        </div>
      ) : null}
      <h3>{title}</h3>
      {message ? <p>{message}</p> : null}
      {action ? <div className="empty-state-action">{action}</div> : null}
    </div>
  );
}
