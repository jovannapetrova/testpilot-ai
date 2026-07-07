import { Activity } from "lucide-react";

export default function ReportCard({ title, value, icon: Icon = Activity }) {
  return (
    <div className="card report-stat-card">
      <div>
        <p>{title}</p>
        <h3>{value}</h3>
      </div>
      <Icon size={24} />
    </div>
  );
}