export default function Skeleton({ rows = 3, className = "" }) {
  return (
    <div className={`skeleton-stack ${className}`} aria-label="Loading">
      {Array.from({ length: rows }).map((_, index) => (
        <div className="skeleton-row" key={index} />
      ))}
    </div>
  );
}
