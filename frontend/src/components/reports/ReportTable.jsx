import {
  Download,
  Eye,
  FileJson,
  FileText,
  Table,
  FileCode2,
  Trash2,
} from "lucide-react";
import {
  getReportJsonUrl,
  getReportPdfUrl,
  getReportCsvUrl,
  getReportMarkdownUrl,
} from "../../api/client";

export default function ReportTable({ reports = [], onOpen, onDelete }) {
  return (
    <div className="card report-table-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Analysis history</p>
          <h2>Recent Reports</h2>
        </div>
      </div>

      <div className="report-table">
        <div className="report-table-head">
          <span>Project</span>
          <span>Overall</span>
          <span>Quality</span>
          <span>Security</span>
          <span>Testing</span>
          <span>Actions</span>
        </div>

        {reports.map((report) => (
          <div className="report-table-row" key={report.project_id}>
            <div>
              <strong>{report.project_name}</strong>
              <p>{new Date(report.created_at).toLocaleString()}</p>
            </div>

            <span>{report.overall_score}</span>
            <span>{report.quality_score}</span>
            <span>{report.security_score}</span>
            <span>{report.test_score}</span>

            <div className="report-actions">
              <button onClick={() => onOpen(report.project_id)}>
                <Eye size={16} />
              </button>

              <a href={getReportPdfUrl(report.project_id)} target="_blank">
                <FileText size={16} />
              </a>

              <a href={getReportJsonUrl(report.project_id)} target="_blank">
                <FileJson size={16} />
              </a>

              <a href={getReportCsvUrl(report.project_id)} target="_blank">
                <Table size={16} />
              </a>

              <a href={getReportMarkdownUrl(report.project_id)} target="_blank">
                <FileCode2 size={16} />
              </a>

              <a href={getReportPdfUrl(report.project_id)} download>
                <Download size={16} />
              </a>

              <button
                className="danger-action"
                onClick={() => onDelete(report.project_id)}
                title="Delete report"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}