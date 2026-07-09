import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import {
  clearReports,
  deleteReport,
  getReport,
  getReports,
} from "../api/client";
import EmptyReports from "../components/reports/EmptyReports";
import ReportCard from "../components/reports/ReportCard";
import ReportTable from "../components/reports/ReportTable";
import ReportViewer from "../components/reports/ReportViewer";
import CompareReports from "../components/reports/CompareReports";

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const stats = useMemo(() => {
    if (!reports.length) return { count: 0, security: 0, testing: 0 };

    return {
      count: reports.length,
      security: Math.round(
        reports.reduce((s, r) => s + Number(r.security_score || 0), 0) /
          reports.length,
      ),
      testing: Math.round(
        reports.reduce((s, r) => s + Number(r.test_score || 0), 0) /
          reports.length,
      ),
    };
  }, [reports]);

  const loadReports = async () => {
    try {
      setLoading(true);
      setError("");
      const result = await getReports();
      setReports(result.reports || []);
    } catch (err) {
      setError(err.userMessage || "Reports could not be loaded.");
      setReports([]);
    } finally {
      setLoading(false);
    }
  };

  const openReport = async (projectId) => {
    try {
      setError("");
      const result = await getReport(projectId);
      setSelectedReport(result.report);
    } catch (err) {
      setSelectedReport(null);
      setError(err.userMessage || "This report is no longer available.");
    }
  };

  const handleDelete = async (projectId) => {
    const confirmed = window.confirm("Delete this report permanently?");
    if (!confirmed) return;

    await deleteReport(projectId);
    setSelectedReport(null);
    await loadReports();
  };

  const handleClearAll = async () => {
    const confirmed = window.confirm("Delete all generated reports permanently?");
    if (!confirmed) return;

    await clearReports();
    setSelectedReport(null);
    await loadReports();
  };

  useEffect(() => {
    loadReports();
  }, []);

  return (
    <div>
      <div className="page-header reports-header">
        <div>
          <p className="eyebrow">Audit-ready outputs</p>
          <h2>Reports Center</h2>
          <p>View, compare, export and manage generated TestPilot AI reports.</p>
        </div>

        <div className="reports-header-actions">
          <button className="btn btn-ghost" onClick={loadReports}>
            <RefreshCw size={17} />
            {loading ? "Refreshing..." : "Refresh"}
          </button>

          {!!reports.length && (
            <button className="btn btn-danger" onClick={handleClearAll}>
              <Trash2 size={17} />
              Clear All
            </button>
          )}
        </div>
      </div>

      <div className="reports-stats-grid">
        <ReportCard title="Generated Reports" value={stats.count} />
        <ReportCard title="Average Security" value={stats.security} />
        <ReportCard title="Average Testing" value={stats.testing} />
      </div>

      {error && (
        <div className="card error-state">
          <strong>{error}</strong>
          <button className="btn btn-ghost" onClick={loadReports}>
            Retry
          </button>
        </div>
      )}

      {!reports.length ? (
        <EmptyReports />
      ) : (
        <>
          <CompareReports reports={reports} />
          <ReportTable
            reports={reports}
            onOpen={openReport}
            onDelete={handleDelete}
          />
        </>
      )}

      <ReportViewer report={selectedReport} />
    </div>
  );
}
