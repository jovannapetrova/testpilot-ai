import { useEffect, useMemo, useState } from "react";
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
import { getDashboardSummary, getReport } from "../api/client";

function average(items, key) {
  if (!items.length) return 0;

  const total = items.reduce((sum, item) => {
    return sum + Number(item[key] || 0);
  }, 0);

  return Math.round((total / items.length) * 100) / 100;
}

function trendDirection(items, key) {
  if (items.length < 2) return "Stable";

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
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadDashboard = async () => {
    setLoading(true);

    try {
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
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();

    const timer = setInterval(() => {
      loadDashboard();
    }, 15000);

    return () => clearInterval(timer);
  }, []);

  const latest = summary?.latest_reports || [];

  const topRisk = useMemo(() => {
    return [...latest]
      .sort((a, b) => Number(a.overall_score) - Number(b.overall_score))
      .slice(0, 3);
  }, [latest]);

  const metrics = [
    {
      title: "Generated Reports",
      value: summary?.total_reports ?? 0,
      subtitle: "Audit-ready outputs",
      icon: FileText,
    },
    {
      title: "Average Overall",
      value: summary?.avg_overall ?? average(latest, "overall_score"),
      subtitle: "Average platform score",
      icon: Activity,
    },
    {
      title: "Security Score",
      value: summary?.avg_security ?? average(latest, "security_score"),
      subtitle: "Average security score",
      icon: ShieldCheck,
    },
    {
      title: "Testing Score",
      value: summary?.avg_testing ?? average(latest, "test_score"),
      subtitle: "Average testing score",
      icon: TestTube2,
    },
    {
      title: "Quality Score",
      value: summary?.avg_quality ?? average(latest, "quality_score"),
      subtitle: "Maintainability average",
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

        <div className="score-orb">
          <span>Average</span>
          <strong>{summary?.avg_overall ?? 0}</strong>
          <small>/100</small>
        </div>
      </div>

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
              <p className="muted-text">No reports generated yet.</p>
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
              <p className="muted-text">Risk data will appear after reports.</p>
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

        <AgentTimeline logs={latestLogs} />
      </section>
    </div>
  );
}
