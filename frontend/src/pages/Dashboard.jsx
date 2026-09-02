import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Code2,
  FileText,
  RefreshCw,
  ShieldCheck,
  TestTube2,
} from "lucide-react";
import MetricCard from "../components/ui/MetricCard";
import AgentTimeline from "../components/ui/AgentTimeline";
import StatusBadge from "../components/ui/StatusBadge";
import ErrorState from "../components/ui/ErrorState";
import Skeleton from "../components/ui/Skeleton";
import { getDashboardSummary, getReport } from "../api/client";

function average(items, key) {
  if (!items.length) return 0;

  const total = items.reduce((sum, item) => {
    return sum + Number(item[key] || 0);
  }, 0);

  return Math.round((total / items.length) * 100) / 100;
}

function trendDirection(items, key) {
  if (items.length < 2) return "More history needed";

  const newest = Number(items[0]?.[key] || 0);
  const oldest = Number(items[items.length - 1]?.[key] || 0);
  const diff = Math.round((newest - oldest) * 100) / 100;

  if (diff > 0) return `Improved by ${diff}`;
  if (diff < 0) return `Dropped by ${Math.abs(diff)}`;
  return "Stable";
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [latestLogs, setLatestLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);

    try {
      setError("");
      const response = await getDashboardSummary();
      const nextSummary = response.summary || {};
      const latestReports = nextSummary.latest_reports || [];

      setSummary(nextSummary);
      setLastUpdated(new Date());

      const latest = latestReports[0];

      if (latest?.project_id) {
        const reportResponse = await getReport(latest.project_id);
        setLatestLogs(reportResponse.report?.agent_logs || []);
      } else {
        setLatestLogs([]);
      }
    } catch (err) {
      setError(err.userMessage || "Dashboard data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();

    const handleDataChange = () => loadDashboard();
    window.addEventListener("testpilot:data-changed", handleDataChange);

    const timer = setInterval(() => {
      loadDashboard();
    }, 15000);

    return () => {
      window.removeEventListener("testpilot:data-changed", handleDataChange);
      clearInterval(timer);
    };
  }, [loadDashboard]);

  const latest = useMemo(() => summary?.latest_reports || [], [summary]);

  const topRisk = useMemo(() => {
    return [...latest]
      .sort((a, b) => Number(a.overall_score) - Number(b.overall_score))
      .slice(0, 3);
  }, [latest]);

  const metrics = [
    {
      title: "Completed Analyses",
      value: summary?.total_completed_reports ?? summary?.total_reports ?? 0,
      subtitle: "Audit-ready outputs",
      icon: FileText,
    },
    {
      title: "Average Overall Score",
      value: summary?.avg_overall ?? average(latest, "overall_score"),
      subtitle: "Completed reports only",
      icon: Activity,
    },
    {
      title: "Security Findings",
      value: summary?.security_findings ?? 0,
      subtitle: "Across stored reports",
      icon: ShieldCheck,
    },
    {
      title: "Generated Test Candidates",
      value: summary?.generated_tests ?? 0,
      subtitle: "Generated, not executed evidence",
      icon: TestTube2,
    },
    {
      title: "Average Quality Score",
      value: summary?.avg_quality ?? average(latest, "quality_score"),
      subtitle: "Completed reports only",
      icon: Code2,
    },
    {
      title: "Risk Level",
      value:
        Number(summary?.avg_overall ?? average(latest, "overall_score")) < 60
          ? "Elevated"
          : "Managed",
      subtitle: "Portfolio posture",
      icon: AlertTriangle,
    },
  ];

  return (
    <div>
      <div className="dashboard-hero card">
        <div>
          <p className="eyebrow">Software quality intelligence</p>
          <h2>AI Software Quality Intelligence</h2>
          <p>
            Monitor software risk, generated tests, security findings and
            quality trends across analyzed repositories.
          </p>

          <div className="dashboard-refresh-row">
            <button className="btn btn-ghost" onClick={loadDashboard}>
              <RefreshCw size={17} className={loading ? "spin" : ""} />
              {loading ? "Refreshing..." : "Refresh"}
            </button>

            {lastUpdated && (
              <span>
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        <div className="score-panel">
          <span>Average Overall Score</span>
          <strong>{summary?.avg_overall ?? 0}</strong>
          <small>/100</small>
        </div>
      </div>

      {error ? <ErrorState title="Dashboard unavailable" message={error} onRetry={loadDashboard} /> : null}

      {loading && !summary ? <Skeleton rows={3} className="dashboard-skeleton" /> : null}

      <section className="grid-4 metrics-section">
        {metrics.map((metric) => (
          <MetricCard key={metric.title} {...metric} />
        ))}
      </section>

      <section className="dashboard-grid">
        <div className="card recent-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Latest reports</p>
              <h2>Recent Analyses</h2>
            </div>
          </div>

          <div className="project-list">
            {latest.length ? (
              latest.map((report) => (
                <div className="project-row" key={report.project_id}>
                  <div>
                    <h3>{report.project_name}</h3>
                    <p>{new Date(report.created_at).toLocaleString()}</p>
                  </div>

                  <div className="project-meta">
                    <strong>{report.overall_score}</strong>
                    <StatusBadge
                      status={
                        Number(report.overall_score) < 60
                          ? "warning"
                          : "success"
                      }
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-inline">
                <FileText size={28} />
                <strong>No completed analyses yet</strong>
                <p>Run a ZIP or GitHub analysis from Projects to create your first persisted report.</p>
              </div>
            )}
          </div>
        </div>

        <div className="card recent-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Risk intelligence</p>
              <h2>Top Risky Projects</h2>
            </div>
          </div>

          <div className="project-list">
            {topRisk.length ? (
              topRisk.map((report) => (
                <div className="project-row" key={report.project_id}>
                  <div>
                    <h3>{report.project_name}</h3>
                    <p>Lowest overall score</p>
                  </div>

                  <div className="project-meta">
                    <strong>{report.overall_score}</strong>
                    <StatusBadge
                      status={
                        Number(report.overall_score) < 60
                          ? "warning"
                          : "success"
                      }
                    />
                  </div>
                </div>
              ))
            ) : (
              <p className="muted-text">Risk data will appear after reports are generated.</p>
            )}
          </div>
        </div>
      </section>

      <section className="dashboard-grid bottom">
        <div className="card insight-card">
          <h3>Quality Trend</h3>
          <p>Average quality score: {summary?.avg_quality ?? 0}</p>
          <span className="trend-note">
            {trendDirection(latest, "quality_score")}
          </span>
        </div>

        <div className="card insight-card">
          <h3>Security Trend</h3>
          <p>Average security score: {summary?.avg_security ?? 0}</p>
          <span className="trend-note">
            {trendDirection(latest, "security_score")}
          </span>
        </div>

        <div className="card insight-card">
          <h3>Testing Trend</h3>
          <p>Average testing score: {summary?.avg_testing ?? 0}</p>
          <span className="trend-note">
            {trendDirection(latest, "test_score")}
          </span>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="card recent-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Framework distribution</p>
              <h2>Detected Technology Mix</h2>
            </div>
          </div>
          <div className="project-list">
            {latest.length ? (
              latest.slice(0, 5).map((report) => (
                <div className="project-row" key={`${report.project_id}-framework`}>
                  <div>
                    <h3>{report.project_name}</h3>
                    <p>{report.language || "Metadata available in full report"}</p>
                  </div>
                  <span className="severity info">analyzed</span>
                </div>
              ))
            ) : (
              <p className="muted-text">Framework data appears after reports are generated.</p>
            )}
          </div>
        </div>

        <AgentTimeline logs={latestLogs} running={Boolean(summary?.running_projects)} />
      </section>
    </div>
  );
}
