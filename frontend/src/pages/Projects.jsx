import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import UploadPanel from "../components/projects/UploadPanel";
import GithubPanel from "../components/projects/GithubPanel";
import ProjectCard from "../components/projects/ProjectCard";
import AnalysisResultPanel from "../components/analysis/AnalysisResultPanel";

import { getReports, getReport } from "../api/client";

export default function Projects() {
  const location = useLocation();
  const isGithubRoute = location.pathname === "/github";
  const [projects, setProjects] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const buildProjectCards = (reports) => {
    return reports.map((report) => ({
      id: report.project_id,
      name: report.project_name,
      language:
        report.language === "python"
          ? "Python"
          : report.language || "Unknown",
      status: report.status === "completed" ? "Completed" : "Running",
      quality: Number(report.overall_score || 0),
      created_at: report.created_at,
    }));
  };

  const loadProjects = async () => {
    try {
      const response = await getReports();
      const reports = response.reports || [];
      const cards = buildProjectCards(reports);

      setProjects(cards);

      if (cards.length && !selectedReport) {
        await openReport(cards[0].id);
      }
    } catch {
      setProjects([]);
    }
  };

  const openReport = async (projectId) => {
    try {
      setLoadingReport(true);
      const response = await getReport(projectId);
      setSelectedReport(response.report);
    } finally {
      setLoadingReport(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  return (
    <>
      <div className="page-header">
        <p className="eyebrow">{isGithubRoute ? "Remote repository workflow" : "AI Project Workspace"}</p>

        <h2>{isGithubRoute ? "GitHub Analysis" : "Projects"}</h2>

        <p>
          {isGithubRoute
            ? "Analyze GitHub repositories with live agent progress, report generation and project intelligence."
            : "Upload software projects, analyze GitHub repositories and reopen stored project analysis details."}
        </p>
      </div>

      <div className="dashboard-grid">
        <UploadPanel />
        <GithubPanel />
      </div>

      <div className="section-heading" style={{ marginTop: "26px" }}>
        <div>
          <p className="eyebrow">Stored analyses</p>
          <h2>Project Archive</h2>
        </div>
      </div>

      <div className="grid-4" style={{ marginTop: "14px" }}>
        {projects.map((project) => (
          <button
            key={project.id}
            className="project-card-button"
            onClick={() => openReport(project.id)}
          >
            <ProjectCard project={project} />
          </button>
        ))}
      </div>

      {loadingReport && (
        <p className="muted-text" style={{ marginTop: "18px" }}>
          Loading stored analysis details...
        </p>
      )}

      {selectedReport && (
        <div style={{ marginTop: "28px" }}>
          <AnalysisResultPanel report={selectedReport} />
        </div>
      )}
    </>
  );
}
