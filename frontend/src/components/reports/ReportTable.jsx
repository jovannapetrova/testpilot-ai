import { Download, Eye, Trash2 } from "lucide-react";
import { useState } from "react";
import { downloadReportFile } from "../../api/client";

const exportFormats = [
  ["pdf", "PDF"],
  ["json", "JSON"],
  ["csv", "CSV"],
  ["markdown", "Markdown"],
];

export default function ReportTable({ reports = [], onOpen, onDelete, onExportSuccess, onExportError }) {
  const [openExportId, setOpenExportId] = useState("");
  const [downloading, setDownloading] = useState("");

  const handleExport = async (projectId, format) => {
    try {
      setDownloading(`${projectId}-${format}`);
      await downloadReportFile(projectId, format);
      setOpenExportId("");
      onExportSuccess?.(`${exportFormats.find(([value]) => value === format)?.[1] || format} report downloaded.`);
    } catch (error) {
      onExportError?.(error.userMessage || "Unable to download report. Try again.");
    } finally {
      setDownloading("");
    }
  };

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
              {report.source_type ? <p>{report.source_type === "github" ? "GitHub" : "ZIP Upload"}</p> : null}
            </div>

            <span>{report.overall_score}</span>
            <span>{report.quality_score}</span>
            <span>{report.security_score}</span>
            <span>{report.test_score}</span>

            <div className="report-actions">
              <button type="button" onClick={() => onOpen(report.project_id)} title="Open report">
                <Eye size={16} />
              </button>

              <div className="export-menu-wrapper">
                <button
                  type="button"
                  onClick={() => setOpenExportId(openExportId === report.project_id ? "" : report.project_id)}
                  title="Export report"
                >
                  <Download size={16} />
                </button>

                {openExportId === report.project_id ? (
                  <div className="export-menu" role="menu">
                    {exportFormats.map(([format, label]) => (
                      <button
                        key={format}
                        type="button"
                        onClick={() => handleExport(report.project_id, format)}
                        disabled={downloading === `${report.project_id}-${format}`}
                      >
                        {downloading === `${report.project_id}-${format}` ? "Downloading..." : label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              <button
                type="button"
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
