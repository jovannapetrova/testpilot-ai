import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, RefreshCw, Search, Trash2 } from "lucide-react";
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
import ConfirmDialog from "../components/ui/ConfirmDialog";
import ErrorState from "../components/ui/ErrorState";
import Skeleton from "../components/ui/Skeleton";
import Toast from "../components/ui/Toast";

function average(reports, key) {
  if (!reports.length) return 0;
  return Math.round(
    reports.reduce((sum, report) => sum + Number(report[key] || 0), 0) / reports.length,
  );
}

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [openingReport, setOpeningReport] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sort, setSort] = useState("newest");
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState("");
  const [toastTone, setToastTone] = useState("success");

  const stats = useMemo(() => ({
    count: reports.length,
    overall: average(reports, "overall_score"),
    security: average(reports, "security_score"),
    testing: average(reports, "test_score"),
  }), [reports]);

  const loadReports = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const params = {
        search: query.trim() || undefined,
        status_filter: statusFilter === "all" ? undefined : statusFilter,
        sort,
      };
      const result = await getReports(params);
      setReports(result.reports || []);
    } catch (err) {
      setError(err.userMessage || "Reports could not be loaded.");
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, [query, sort, statusFilter]);

  const openReport = async (projectId) => {
    try {
      setOpeningReport(true);
      setError("");
      const result = await getReport(projectId);
      setSelectedReport(result.report);
    } catch (err) {
      setSelectedReport(null);
      setError(err.userMessage || "This report is no longer available.");
    } finally {
      setOpeningReport(false);
    }
  };

  const showToast = (message, tone = "success") => {
    setToastTone(tone);
    setToast(message);
  };

  const confirmDelete = (projectId) => {
    setConfirm({
      kind: "one",
      projectId,
      title: "Delete this report?",
      message: "This removes the stored report and generated exports for this project.",
      confirmLabel: "Delete report",
    });
  };

  const confirmClearAll = () => {
    setConfirm({
      kind: "all",
      title: "Delete all reports?",
      message: "This removes all of your stored reports and generated exports. Projects tied to those reports are also removed.",
      confirmLabel: "Delete all reports",
    });
  };

  const runDelete = async () => {
    if (!confirm) return;

    try {
      setDeleting(true);
      if (confirm.kind === "all") {
        await clearReports();
        showToast("All reports deleted.");
      } else {
        await deleteReport(confirm.projectId);
        showToast("Report deleted.");
      }
      setSelectedReport(null);
      await loadReports();
    } catch (err) {
      showToast(err.userMessage || "Unable to delete report.", "error");
    } finally {
      setDeleting(false);
      setConfirm(null);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => loadReports(), 250);
    return () => clearTimeout(timer);
  }, [loadReports]);

  return (
    <div>
      <div className="page-header reports-header">
        <div>
          <p className="eyebrow">Completed analysis evidence</p>
          <h2>Reports</h2>
          <p>Search, compare, export and manage completed TestPilot AI analysis reports.</p>
        </div>

        <div className="reports-header-actions">
          <button className="btn btn-ghost" onClick={loadReports} disabled={loading}>
            <RefreshCw size={17} className={loading ? "spin" : ""} />
            {loading ? "Refreshing..." : "Refresh"}
          </button>

          {!!reports.length && (
            <button className="btn btn-danger" onClick={confirmClearAll}>
              <Trash2 size={17} />
              Clear All
            </button>
          )}
        </div>
      </div>

      <div className="reports-stats-grid">
        <ReportCard title="Reports" value={stats.count} icon={FileText} />
        <ReportCard title="Average Overall" value={stats.overall} />
        <ReportCard title="Average Security" value={stats.security} />
        <ReportCard title="Average Testing" value={stats.testing} />
      </div>

      <div className="reports-toolbar">
        <div className="report-search">
          <Search size={17} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search reports by project, source, language or framework"
          />
        </div>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">All statuses</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>

      {error ? <ErrorState title="Reports unavailable" message={error} onRetry={loadReports} /> : null}

      {loading && !reports.length ? (
        <Skeleton rows={4} />
      ) : !reports.length ? (
        <EmptyReports />
      ) : (
        <>
          <CompareReports reports={reports} onMessage={showToast} />
          <ReportTable
            reports={reports}
            onOpen={openReport}
            onDelete={confirmDelete}
            onExportSuccess={showToast}
            onExportError={(message) => showToast(message, "error")}
          />
        </>
      )}

      {openingReport ? <p className="muted-text report-opening">Opening report...</p> : null}
      <ReportViewer report={selectedReport} />

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title}
        message={confirm?.message}
        confirmLabel={confirm?.confirmLabel}
        danger
        loading={deleting}
        onCancel={() => setConfirm(null)}
        onConfirm={runDelete}
      />

      <Toast message={toast} tone={toastTone} onClose={() => setToast("")} />
    </div>
  );
}
