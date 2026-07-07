import { FileText } from "lucide-react";

export default function EmptyReports() {
  return (
    <div className="card empty-reports">
      <FileText size={44} />
      <h3>No reports generated yet</h3>
      <p>Run a multi-agent analysis from the Projects page to create your first report.</p>
    </div>
  );
}